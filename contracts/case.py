"""A case: one investigation of one detected moment, with stage checkpoints.

Each stage writes a checkpoint before the next starts, so a failed agent
resumes without redoing the case. `recovered_from_checkpoint` is set when
that path was taken and is shown on the Analyst Console.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.clock import Window
from contracts.taxonomy import AgentRole, CaseOutcome, Metric, MomentType


class CaseStage(StrEnum):
    OPEN = "open"
    PREREGISTERED = "preregistered"
    TESTED = "tested"
    CROSS_EXAMINED = "cross_examined"
    SYNTHESIZED = "synthesized"
    PROPOSED = "proposed"
    CLOSED = "closed"


STAGE_ORDER: list[CaseStage] = list(CaseStage)


class Checkpoint(BaseModel):
    stage: CaseStage
    wall_clock_ms: int = Field(ge=0)
    agents_completed: list[AgentRole] = Field(default_factory=list)
    agents_failed: list[AgentRole] = Field(default_factory=list)
    note: str = ""


class TriggerMetric(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: Metric
    subject: str
    value: float
    baseline_value: float
    n_events: int = Field(ge=0)


class Case(BaseModel):
    case_id: str
    match_id: str
    moment_type: MomentType
    origin: Literal["auto", "on_demand"] = "auto"
    window: Window
    triggers: list[TriggerMetric] = Field(min_length=1)
    stage: CaseStage = CaseStage.OPEN
    outcome: CaseOutcome | None = None
    hypothesis_ids: list[str] = Field(default_factory=list)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    recovered_from_checkpoint: bool = False
    tool_calls_used: int = Field(default=0, ge=0)
    tool_call_budget: int = Field(default=16, ge=1)
    card_id: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "Case":
        stages = [c.stage for c in self.checkpoints]
        if stages != sorted(stages, key=STAGE_ORDER.index):
            raise ValueError("checkpoints must be in stage order")
        if self.stage == CaseStage.CLOSED and self.outcome is None:
            raise ValueError("a closed case has an outcome")
        if self.tool_calls_used > self.tool_call_budget:
            raise ValueError("tool calls exceed the case budget")
        return self
