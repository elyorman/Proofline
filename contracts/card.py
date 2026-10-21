"""Insight Card: the single unit of truth every surface renders."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from contracts.prediction import Direction, Window
from contracts.taxonomy import (
    LANGUAGE_FOR_SUPPORT,
    AgentRole,
    BaselineScope,
    CardStatus,
    Cause,
    LanguageLevel,
    Metric,
    MomentType,
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


Proposition = ChangeProposition | AttributionProposition


class CauseRef(BaseModel):
    hypothesis_id: str
    taxonomy: Cause
    agent: AgentRole
    role: Literal["primary", "secondary"]


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
    semantic_check: CheckResult
    verifier_model_family: str
    support_level: SupportLevel | None = None
    language_level: LanguageLevel | None = None

    @model_validator(mode="after")
    def _language_follows_support(self) -> "Verification":
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
    detected_at: str
    verified_at: str | None = None
    published_at: str | None = None


class Subject(BaseModel):
    team: str
    players: list[str] = Field(default_factory=list)


class BroadcastCueSpec(BaseModel):
    template: str
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
    at: str
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
    moment_type: MomentType
    subject: Subject
    timing: Timing
    propositions: list[Proposition] = Field(min_length=1)
    claim: str
    causes: list[CauseRef] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def _attributions_reference_changes(self) -> "InsightCard":
        change_ids = {p.id for p in self.propositions if p.type == "change"}
        for p in self.propositions:
            if p.type == "attribution" and p.effect not in change_ids:
                raise ValueError(f"attribution {p.id} references unknown effect {p.effect}")
        primaries = [c for c in self.causes if c.role == "primary"]
        if len(primaries) > 1:
            raise ValueError("at most one primary cause")
        return self
