"""Insight Card: the single unit of truth every surface renders.

The primary cause lives in exactly one place: the attribution proposition
with role "primary". The Evaluator, Verifier and Narrator all read it there.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from contracts.clock import MatchClock, Window
from contracts.prediction import Direction
from contracts.taxonomy import (
    LANGUAGE_FOR_SUPPORT,
    AgentRole,
    BaselineScope,
    CardStatus,
    CaseOutcome,
    Cause,
    LanguageLevel,
    Metric,
    MomentType,
    OverlayTemplate,
    SupportLevel,
)


class ChangeProposition(BaseModel):
    id: str
    type: Literal["change"] = "change"
    metric: Metric
    subject: str
    direction: Direction
    window: Window
    baseline: BaselineScope


class AttributionProposition(BaseModel):
    id: str
    type: Literal["attribution"] = "attribution"
    cause: Cause
    effect: str = Field(description="id of the change proposition this cause explains")
    role: Literal["primary", "secondary"]
    hypothesis_id: str
    agent: AgentRole


Proposition = ChangeProposition | AttributionProposition


class Baseline(BaseModel):
    window: BaselineScope
    value: float


class Evidence(BaseModel):
    metric: Metric
    subject: str
    window: Window
    value: float
    baseline: Baseline
    n_events: int = Field(ge=0)
    tool_call_id: str


class DependsOn(BaseModel):
    evidence_sets: list[str]
    data_version: str


class RejectedAlternative(BaseModel):
    hypothesis_id: str
    taxonomy: Cause
    agent: AgentRole
    reason: str
    rejected_by: Literal["test", "cross_examination", "verifier"]
    tool_call_id: str | None = None


class Investigation(BaseModel):
    agents: list[AgentRole]
    preregistered_predictions: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    budget: int = Field(ge=0)
    cross_examination: str = ""
    recovered_from_checkpoint: bool = False


class CheckResult(StrEnum):
    PASSED = "passed"
    CORRECTED = "corrected"
    FAILED = "failed"
    SKIPPED = "skipped"


class Verification(BaseModel):
    status: Literal["passed", "corrected", "rejected"]
    recompute: Literal["match", "mismatch"]
    baseline_check: CheckResult
    sample_size_check: CheckResult
    contradiction_check: CheckResult
    number_check: CheckResult = Field(description="every number in every variant matches evidence")
    semantic_check: CheckResult
    verifier_model_family: str
    support_level: SupportLevel | None = None
    language_level: LanguageLevel | None = None
    rejection_reason: str | None = None

    @property
    def checks(self) -> list[CheckResult]:
        return [
            self.baseline_check,
            self.sample_size_check,
            self.contradiction_check,
            self.number_check,
            self.semantic_check,
        ]

    @model_validator(mode="after")
    def _consistent(self) -> "Verification":
        if self.status == "passed":
            if self.recompute != "match" or any(c != CheckResult.PASSED for c in self.checks):
                raise ValueError("status 'passed' requires recompute match and all checks passed")
            if self.support_level is None:
                raise ValueError("a passed verification carries a support level")
        elif self.status == "corrected":
            if self.recompute != "match" or any(c == CheckResult.FAILED for c in self.checks):
                raise ValueError("status 'corrected' allows no failed check and no mismatch")
            if self.support_level is None:
                raise ValueError("a corrected verification carries a support level")
        else:
            if not self.rejection_reason:
                raise ValueError("status 'rejected' requires a rejection_reason")
            if self.support_level is not None:
                raise ValueError("a rejected verification has no support level")
        if self.support_level is not None:
            expected = LANGUAGE_FOR_SUPPORT[self.support_level]
            if self.language_level is None:
                self.language_level = expected
            elif self.language_level != expected:
                raise ValueError(
                    f"language_level {self.language_level} does not match "
                    f"support_level {self.support_level}"
                )
        return self


class Timing(BaseModel):
    change_window: Window
    detected_at: MatchClock
    verified_at: MatchClock | None = None
    published_at: MatchClock | None = None


class Subject(BaseModel):
    team: str
    players: list[str] = Field(default_factory=list)


class BroadcastCueSpec(BaseModel):
    template: OverlayTemplate
    priority: Literal["low", "normal", "high"] = "normal"
    show_at: Literal["immediate", "next_dead_ball"] = "next_dead_ball"
    max_delay_s: int = Field(default=45, ge=0)
    duration_s: int = Field(default=8, ge=1)
    fields: dict[str, str | float | int]


class Provenance(BaseModel):
    trace_id: str
    foundry_eval_run: str | None = None


class Revision(BaseModel):
    revision: int
    at: MatchClock
    reason: str
    amendment_ids: list[str] = Field(default_factory=list)


class InsightCard(BaseModel):
    id: str
    revision: int = Field(default=1, ge=1)
    match_id: str
    case_id: str
    origin: Literal["auto", "on_demand"] = "auto"
    lane: Literal["fast", "full"] = "full"
    status: CardStatus = CardStatus.PROPOSED
    case_outcome: CaseOutcome
    moment_type: MomentType
    subject: Subject
    timing: Timing
    propositions: list[Proposition] = Field(min_length=1)
    claim: str
    evidence: list[Evidence] = Field(default_factory=list)
    depends_on: DependsOn
    rejected_alternatives: list[RejectedAlternative] = Field(default_factory=list)
    investigation: Investigation | None = None
    verification: Verification | None = None
    salience: Literal["low", "medium", "high"] = "medium"
    variants: dict[str, dict[str, str]] = Field(
        default_factory=dict, description="audience -> locale -> text"
    )
    broadcast_cue: BroadcastCueSpec | None = None
    revisions: list[Revision] = Field(default_factory=list)
    supersedes: str | None = None
    superseded_by: str | None = None
    provenance: Provenance

    @property
    def attributions(self) -> list[AttributionProposition]:
        return [p for p in self.propositions if p.type == "attribution"]

    @property
    def primary_cause(self) -> AttributionProposition | None:
        return next((a for a in self.attributions if a.role == "primary"), None)

    @model_validator(mode="after")
    def _consistent(self) -> "InsightCard":
        change_ids = {p.id for p in self.propositions if p.type == "change"}
        for a in self.attributions:
            if a.effect not in change_ids:
                raise ValueError(f"attribution {a.id} references unknown effect {a.effect}")
        primaries = [a for a in self.attributions if a.role == "primary"]
        if len(primaries) > 1:
            raise ValueError("at most one primary cause")
        if self.case_outcome == CaseOutcome.NONE and self.attributions:
            raise ValueError("a 'none' outcome carries no attributions")
        if self.case_outcome == CaseOutcome.EXPLAINED:
            if not primaries or primaries[0].cause in (Cause.OTHER, Cause.NONE):
                raise ValueError("an 'explained' outcome needs a primary cause in the taxonomy")
        if self.case_outcome == CaseOutcome.OTHER:
            if not primaries or primaries[0].cause != Cause.OTHER:
                raise ValueError("an 'other' outcome needs a primary attribution to 'other'")
        return self
