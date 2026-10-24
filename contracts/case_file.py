"""The case file (spec §12.2): everything one investigation did, as the Analyst Console shows
it. Who registered which hypothesis and why code refused or judged it; who cross-examined
whom, with which test, and what code measured; how the case was ranked; every tool call and
checkpoint. Only numbers code measured appear here; no agent wrote one.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.case import Case, CaseStage
from contracts.clock import Window
from contracts.eval_run import Variant
from contracts.prediction import CrossExamination, Direction, Hypothesis, HypothesisTest
from contracts.taxonomy import AgentRole, CaseOutcome, Metric


class RefusedProposal(BaseModel):
    """A hypothesis the orchestrator refused before testing, with the reason."""

    agent: AgentRole
    cause: str
    metric: str
    subject: str
    reason: str


class ToolCall(BaseModel):
    """One call to the State Builder over MCP, as logged."""

    tool: str
    arguments: dict[str, Any]
    tool_call_id: str | None = Field(default=None, description="None when the call was refused")
    value: float | None = None
    baseline: float | None = None
    n_events: int | None = Field(default=None, ge=0)
    values: dict[str, float] = Field(default_factory=dict, description="game_state's score")
    insufficient_data: str | None = None
    error: str | None = None


class Persistence(BaseModel):
    """A change the detector saw, re-measured by code over the minutes after it fired, events
    the detector never read, in standard deviations of normal variation (spec §9.1)."""

    model_config = ConfigDict(allow_inf_nan=False)

    metric: Metric
    subject: str
    direction: Direction
    window: Window
    value: float | None = None
    baseline: float | None = None
    n_events: int | None = Field(default=None, ge=0)
    sigmas: float | None = None
    holds: bool
    reason: str
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def _held_means_measured(self) -> "Persistence":
        if self.holds and self.sigmas is None:
            raise ValueError("a change holds only on a measured change")
        return self


class CaseRanking(BaseModel):
    outcome: CaseOutcome
    primary: str | None
    secondary: list[str]
    why: str


class CaseFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case: Case
    variant: Variant
    confirmation: list[Persistence] = Field(
        default_factory=list, description="each detected change re-measured after it fired"
    )
    agents: list[AgentRole]
    hypotheses: list[Hypothesis]
    refused: list[RefusedProposal]
    tests: list[HypothesisTest]
    cross_examinations: list[CrossExamination]
    unrun: list[str] = Field(description="counter-tests refused or not measurable, with why")
    ranking: CaseRanking
    tool_calls: list[ToolCall]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _one_story(self) -> "CaseFile":
        ids = [h.hypothesis_id for h in self.hypotheses]
        if self.case.hypothesis_ids != ids:
            raise ValueError("the case names the hypotheses its file holds")
        if {t.hypothesis_id for t in self.tests} - set(ids):
            raise ValueError("a test names a hypothesis the case does not hold")
        if {e.hypothesis_id for e in self.cross_examinations} - set(ids):
            raise ValueError("a counter-test names a hypothesis the case does not hold")
        named = [self.ranking.primary, *self.ranking.secondary] if self.ranking.primary else []
        if set(named) - set(ids):
            raise ValueError("the ranking names a hypothesis the case does not hold")
        if self.case.stage != CaseStage.CLOSED or self.case.outcome != self.ranking.outcome:
            raise ValueError("a case file is written once the case closes, with its outcome")
        if self.confirmation and not any(p.holds for p in self.confirmation) and ids:
            raise ValueError("a change that faded is not investigated")
        return self
