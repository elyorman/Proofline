"""Structured pre-registration: what an agent commits to before calling any tool.

The orchestrator validates these mechanically and rejects vague predictions.
The outcome is judged against the tool result by code, never by the agent.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from contracts.taxonomy import AgentRole, BaselineScope, Cause, Metric


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"


class Window(BaseModel):
    """Inclusive match-clock window as mm:ss strings, e.g. 58:00-63:00."""

    start: str = Field(pattern=r"^\d{2,3}:\d{2}$")
    end: str = Field(pattern=r"^\d{2,3}:\d{2}$")

    def __str__(self) -> str:
        return f"{self.start}-{self.end}"


class Prediction(BaseModel):
    metric: Metric
    subject: str = Field(min_length=1, description="team, team.unit, or player id")
    window: Window
    compare_to: BaselineScope
    direction: Direction
    min_relative_change: float = Field(gt=0, le=5)


class Hypothesis(BaseModel):
    hypothesis_id: str
    case_id: str
    agent: AgentRole
    taxonomy: Cause
    prediction: Prediction


class TestOutcome(StrEnum):
    SUPPORTED = "supported"
    FAILED = "failed"


class HypothesisTest(BaseModel):
    hypothesis_id: str
    tool_call_id: str
    observed_relative_change: float
    outcome: TestOutcome
    reason: str


class CrossExamResult(StrEnum):
    HOLDS = "holds"
    WEAKENED = "weakened"
    REFUTED = "refuted"


class CrossExamination(BaseModel):
    hypothesis_id: str
    challenger: AgentRole
    counter_prediction: Prediction
    tool_call_id: str
    result: CrossExamResult
    reason: str
