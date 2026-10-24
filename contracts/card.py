"""Insight Card: the single unit of truth every surface renders.

The primary cause lives in exactly one place: the attribution proposition
with role "primary". The Evaluator, Verifier and Narrator all read it there.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.clock import MatchClock, Window
from contracts.prediction import MIN_CLAIM_SD, Direction
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

    @model_validator(mode="after")
    def _moves(self) -> "ChangeProposition":
        if self.direction == Direction.FLAT:
            raise ValueError("a change proposition moves up or down")
        return self


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
    model_config = ConfigDict(allow_inf_nan=False)

    window: BaselineScope
    value: float


class Evidence(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

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
    team: str | None = Field(default=None, description="the team the ruled-out cause is about")
    reason: str
    rejected_by: Literal["test", "cross_examination", "verifier", "follow_up"]
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
            allowed = (CheckResult.PASSED, CheckResult.CORRECTED)
            if self.recompute != "match" or any(c not in allowed for c in self.checks):
                raise ValueError("status 'corrected' allows no failed, skipped or mismatched check")
            if CheckResult.CORRECTED not in self.checks:
                raise ValueError("status 'corrected' needs at least one corrected check")
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
    model_config = ConfigDict(allow_inf_nan=False)

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


# A follow-up's bars (spec §9.1, "Keep watching"), fixed by code so no side picks its own: a
# predicted move must clear what a confirmed change clears, and a number left at ordinary
# play stays inside what a claim may not be.
MOVE_SD = 1.5
STILL_SD = MIN_CLAIM_SD


class DecisiveTest(BaseModel):
    """One side's prediction for minutes nobody had seen when it was made: a move its cause
    implies and the rival's would not cause (up or down), or a number its cause leaves at
    ordinary play where the rival's would move it (flat). Code measures it once the minutes
    are played; a reading too thin to measure does not hold."""

    model_config = ConfigDict(allow_inf_nan=False)

    side: Literal["primary", "rival"]
    hypothesis_id: str
    cause: Cause
    agent: AgentRole
    metric: Metric
    subject: str
    direction: Direction
    reason: str
    sigmas: float | None = Field(
        default=None, description="measured, signed, against the first half"
    )
    holds: bool | None = None
    measured: str | None = Field(default=None, description="what code read, or why it could not")
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def _judged(self) -> "DecisiveTest":
        if self.sigmas is not None:
            way = {Direction.UP: 1, Direction.DOWN: -1}.get(self.direction)
            expected = abs(self.sigmas) < STILL_SD if way is None else way * self.sigmas >= MOVE_SD
            if self.holds != expected:
                raise ValueError("a decisive test holds exactly when its reading clears its bar")
        elif self.holds:
            raise ValueError("a decisive test that was not measured does not hold")
        return self


class Rival(BaseModel):
    """A cause that survived beside the primary, on its own team's side."""

    hypothesis_id: str
    cause: Cause
    agent: AgentRole
    team: str


class FollowUp(BaseModel):
    """Keep watching: causes survived beside the primary and the data could not tell them
    apart, so each side pre-registered a decisive test for the minutes after the card. Only
    the primary's holding confirms it; only one rival's overturns it to that rival; anything
    else leaves it open."""

    window: Window = Field(description="the minutes not yet played when the tests were made")
    rivals: list[Rival] = Field(min_length=1, max_length=2)
    tests: list[DecisiveTest] = Field(min_length=1, max_length=3)
    status: Literal["pending", "confirmed", "overturned", "unresolved"] = "pending"

    @property
    def overturned_to(self) -> Rival | None:
        """The rival a settled follow-up names instead of the primary, if any."""
        if self.status != "overturned":
            return None
        (won,) = [t for t in self.tests if t.side == "rival" and t.holds]
        return next(r for r in self.rivals if r.hypothesis_id == won.hypothesis_id)

    @model_validator(mode="after")
    def _settled(self) -> "FollowUp":
        ids = [t.hypothesis_id for t in self.tests]
        if len(ids) != len(set(ids)) or sum(t.side == "primary" for t in self.tests) > 1:
            raise ValueError("one decisive test per side")
        rivals = {r.hypothesis_id for r in self.rivals}
        if any((t.side == "rival") != (t.hypothesis_id in rivals) for t in self.tests):
            raise ValueError("a rival's test is one of the follow-up's rivals'")
        if self.status == "pending":
            if any(t.holds is not None for t in self.tests):
                raise ValueError("a pending follow-up has measured nothing")
            return self
        if any(t.holds is None for t in self.tests):
            raise ValueError("a settled follow-up has judged every test")
        primary = any(t.holds for t in self.tests if t.side == "primary")
        held = sum(bool(t.holds) for t in self.tests if t.side == "rival")
        expected = (
            "confirmed"
            if primary and not held
            else "overturned"
            if held == 1 and not primary
            else "unresolved"
        )
        if self.status != expected:
            raise ValueError(f"tests that held say {expected}, not {self.status}")
        return self


# What a full-lane card's verification must say at each lifecycle status (CLAUDE.md rule 6,
# spec §5 and §10). Every status from `verified` on has passed the Verifier, including a card
# that expired to the recap or that a producer killed; rejected and withdrawn ones failed it.
NEEDS_PASSING = frozenset(
    {
        CardStatus.VERIFIED,
        CardStatus.SCHEDULED,
        CardStatus.SHOWN,
        CardStatus.REVISED,
        CardStatus.EXPIRED,
        CardStatus.KILLED,
    }
)
NEEDS_REJECTED = frozenset({CardStatus.REJECTED, CardStatus.WITHDRAWN})


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
    follow_up: FollowUp | None = None
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
        ids = [p.id for p in self.propositions]
        if len(ids) != len(set(ids)):
            raise ValueError("each proposition id is used once")
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
        verdict = self.verification.status if self.verification else None
        if self.lane == "fast":
            # Rule 6's only exception: key events stated from deterministic facts.
            if self.moment_type != MomentType.KEY_EVENT or self.attributions or verdict:
                raise ValueError("a fast-lane card is a key event with no causes and no verifier")
        elif self.status in NEEDS_PASSING and verdict not in ("passed", "corrected"):
            raise ValueError(f"a {self.status} card needs a passed or corrected verification")
        elif self.status in NEEDS_REJECTED and verdict != "rejected":
            raise ValueError(f"a {self.status} card carries the rejected verification")
        surfaced = self.status in NEEDS_PASSING or self.status == CardStatus.WITHDRAWN
        if (
            self.lane == "full"
            and surfaced
            and not (self.evidence and self.depends_on.evidence_sets)
        ):
            # A correction finds a card through what it depends on, and the analyst view shows
            # its evidence, so a card that reached a surface carries both.
            raise ValueError(f"a {self.status} card carries its evidence and what it depends on")
        listed = [r.revision for r in self.revisions]
        if listed != list(range(2, self.revision + 1)):
            raise ValueError(
                f"revisions must number 2 up to revision {self.revision}; got {listed}"
            )
        if self.status == CardStatus.REVISED and self.revision < 2:
            raise ValueError("a revised card is at revision 2 or later")
        if self.follow_up and self.primary_cause:
            won = self.follow_up.overturned_to
            names = self.primary_cause.hypothesis_id
            if names in {r.hypothesis_id for r in self.follow_up.rivals} and names != (
                won.hypothesis_id if won else None
            ):
                raise ValueError("a card names a rival as primary only when overturned to it")
            if won and names != won.hypothesis_id:
                raise ValueError("an overturned card names the rival that came true")
        return self
