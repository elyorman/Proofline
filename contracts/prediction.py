"""Structured pre-registration: what an agent commits to before calling any tool.

The orchestrator validates these mechanically and rejects vague predictions.
The outcome is judged against the ToolResult by code, never by the agent.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from contracts.clock import Window
from contracts.taxonomy import (
    DEFAULT_THRESHOLD_KIND,
    DOMAIN_OF_AGENT,
    AgentRole,
    BaselineScope,
    Cause,
    Metric,
    ThresholdKind,
)


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"


class Prediction(BaseModel):
    metric: Metric
    subject: str = Field(min_length=1, description="team, team.unit, or player id")
    window: Window
    compare_to: BaselineScope
    direction: Direction
    threshold_kind: ThresholdKind | None = Field(
        default=None, description="defaults to the metric's pinned kind"
    )
    min_change: float = Field(gt=0, description="relative fraction, absolute units, or sigmas")

    @model_validator(mode="after")
    def _default_threshold(self) -> "Prediction":
        if self.threshold_kind is None:
            self.threshold_kind = DEFAULT_THRESHOLD_KIND[self.metric]
        if self.threshold_kind == ThresholdKind.RELATIVE:
            if DEFAULT_THRESHOLD_KIND[self.metric] != ThresholdKind.RELATIVE:
                raise ValueError(f"{self.metric} is not pinned relative; use absolute or sigma")
            if self.min_change > 5:
                raise ValueError("relative min_change above 500% is not a real prediction")
        return self

    def supported_by(self, observed_change: float) -> bool:
        """Mechanical verdict: the signed change must point the predicted way, far enough."""
        signed = observed_change if self.direction == Direction.UP else -observed_change
        return signed >= self.min_change


class Hypothesis(BaseModel):
    hypothesis_id: str
    case_id: str
    agent: AgentRole
    taxonomy: Cause
    prediction: Prediction

    @model_validator(mode="after")
    def _agent_owns_cause(self) -> "Hypothesis":
        if self.agent == AgentRole.SYNTHESIS:
            raise ValueError("synthesis ranks hypotheses; it does not register them")
        if self.taxonomy.domain == "fallback":
            raise ValueError("'other' and 'none' are synthesis outcomes, not hypotheses")
        if self.agent != AgentRole.SINGLE and self.taxonomy.domain != DOMAIN_OF_AGENT[self.agent]:
            raise ValueError(f"{self.agent} cannot register a {self.taxonomy.domain} cause")
        return self


class TestOutcome(StrEnum):
    SUPPORTED = "supported"
    FAILED = "failed"


class HypothesisTest(BaseModel):
    hypothesis_id: str
    tool_call_id: str
    observed_change: float = Field(description="signed, in the prediction's threshold units")
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
