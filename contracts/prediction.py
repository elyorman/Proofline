"""Structured pre-registration: what an agent commits to before calling any tool.

The orchestrator validates these mechanically and rejects vague predictions.
The outcome is judged against the ToolResult by code, never by the agent.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator

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

MIN_CLAIM_SD = 1.0  # the smallest change in sigmas a hypothesis may claim


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"  # no change beyond min_change either way; predictions only


class Prediction(BaseModel):
    metric: Metric
    subject: str = Field(min_length=1, description="team, team.unit, or player id")
    window: Window
    compare_to: BaselineScope
    direction: Direction
    threshold_kind: ThresholdKind | None = Field(
        default=None, description="defaults to the metric's pinned kind"
    )
    min_change: float = Field(
        gt=0,
        allow_inf_nan=False,
        description="relative fraction, absolute units, or sigmas; for flat, the tolerance",
    )

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

    def supported_by(self, observed_change: float, share: float = 1.0) -> bool:
        """Mechanical verdict on a signed change.

        Up or down: the change points the predicted way by at least `share` of min_change.
        Flat: the change stays within min_change / share either way.
        """
        if not 0 < share <= 1:
            raise ValueError(f"share must be in (0, 1], got {share}")
        if self.direction == Direction.FLAT:
            return abs(observed_change) <= self.min_change / share
        signed = observed_change if self.direction == Direction.UP else -observed_change
        return signed >= share * self.min_change


class Hypothesis(BaseModel):
    hypothesis_id: str
    case_id: str
    agent: AgentRole
    taxonomy: Cause
    prediction: Prediction

    @model_validator(mode="after")
    def _agent_owns_cause(self) -> "Hypothesis":
        if self.agent in (AgentRole.SYNTHESIS, AgentRole.LEAD):
            raise ValueError(f"{self.agent} frames or ranks hypotheses; it does not register them")
        if self.taxonomy.domain == "fallback":
            raise ValueError("'other' and 'none' are synthesis outcomes, not hypotheses")
        if self.agent != AgentRole.SINGLE and self.taxonomy.domain != DOMAIN_OF_AGENT[self.agent]:
            raise ValueError(f"{self.agent} cannot register a {self.taxonomy.domain} cause")
        if self.prediction.direction == Direction.FLAT:
            raise ValueError("a hypothesis predicts a change; flat is for counter-tests")
        p = self.prediction
        if p.threshold_kind == ThresholdKind.SIGMA and p.min_change < MIN_CLAIM_SD:
            raise ValueError(
                f"a claim under {MIN_CLAIM_SD:g} sd is within ordinary play, not a change"
            )
        return self


class TestOutcome(StrEnum):
    SUPPORTED = "supported"
    FAILED = "failed"


class HypothesisTest(BaseModel):
    hypothesis_id: str
    tool_call_id: str
    observed_change: float = Field(
        allow_inf_nan=False, description="signed, in the prediction's threshold units"
    )
    outcome: TestOutcome
    reason: str


class CrossExamResult(StrEnum):
    HOLDS = "holds"
    WEAKENED = "weakened"
    REFUTED = "refuted"


class CrossExamination(BaseModel):
    """A challenger's counter-test, scored by code: if the counter-prediction holds, the
    hypothesis is refuted; if it reaches half its threshold, weakened; otherwise it holds.

    A control (the claim repeated on another subject) is scored on what it leaves of the
    hypothesis's own change: another team tiring too does not rule out a unit tiring more.
    The hypothesis holds if its claim still holds beyond the control's change, is weakened
    if half of it does, and is refuted otherwise.

    A corollary is something else the hypothesis's cause would move if it were real, on
    another metric: the hypothesis holds if the corollary moved as predicted, is refuted if
    it moved the other way by as much, and is weakened in between.
    """

    hypothesis_id: str
    challenger: AgentRole
    counter_prediction: Prediction
    tool_call_id: str
    observed_change: float = Field(
        allow_inf_nan=False, description="signed, in the counter-prediction's units"
    )
    hypothesis_change: float | None = Field(
        default=None,
        allow_inf_nan=False,
        description="controls only: the hypothesis subject's own change over the same window "
        "and baseline, filled by code from the hypothesis's test",
    )
    corollary: bool = Field(
        default=False,
        description="the counter-prediction is what the hypothesis implies on another metric, "
        "so it holds when the hypothesis does",
    )
    reason: str

    @model_validator(mode="wrap")
    @classmethod
    def _stored_result_agrees(cls, data: Any, handler: Any) -> "CrossExamination":
        """A stored record's result must be the one the counter-test computes."""
        stored = data.get("result") if isinstance(data, dict) else None
        exam = handler(data)
        if stored is not None and stored != exam.result:
            raise ValueError(f"stored result {stored!r} disagrees with the counter-test")
        return exam

    @model_validator(mode="after")
    def _challenger_investigates(self) -> "CrossExamination":
        if self.challenger in (AgentRole.SYNTHESIS, AgentRole.LEAD):
            raise ValueError(f"{self.challenger} frames or ranks; it does not cross-examine")
        return self

    @computed_field
    @property
    def result(self) -> CrossExamResult:
        if self.corollary:
            if self.counter_prediction.supported_by(self.observed_change):
                return CrossExamResult.HOLDS
            if self.counter_prediction.supported_by(-self.observed_change):
                return CrossExamResult.REFUTED
            return CrossExamResult.WEAKENED
        if self.hypothesis_change is not None:
            excess = self.hypothesis_change - self.observed_change
            if self.counter_prediction.supported_by(excess):
                return CrossExamResult.HOLDS
            if self.counter_prediction.supported_by(excess, share=0.5):
                return CrossExamResult.WEAKENED
            return CrossExamResult.REFUTED
        if self.counter_prediction.supported_by(self.observed_change):
            return CrossExamResult.REFUTED
        if self.counter_prediction.supported_by(self.observed_change, share=0.5):
            return CrossExamResult.WEAKENED
        return CrossExamResult.HOLDS


def _same_family(a: str, b: str) -> bool:
    """One subject is the other, or a unit of it: "Northvale" and "Northvale.defence"."""
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def check_counter_test(hypothesis: Hypothesis, exam: CrossExamination) -> None:
    """Refuse a counter-test that cannot fairly contradict `hypothesis` (spec §9.1).

    The orchestrator calls this before running the counter-test. Every rule compares with
    the hypothesis's own claim, so a challenger who has seen the data cannot pick a counter
    that is sure to refute it. A counter on the hypothesis's metric uses its threshold kind
    and, if it predicts a move, a move at least as large. A flat counter asks whether the
    hypothesis's own change is normal: same subject and window, another baseline, a tolerance
    tighter than the claim. A counter that moves the other way keeps the hypothesis's subject
    and window too. A counter that moves the same way is a control: the claim itself on
    another subject, same window, baseline and threshold, carrying the hypothesis's own change
    to be scored against. A counter on another metric is a corollary: a move the hypothesis's
    cause implies there, over the same window and baseline, scored as holding when it happens.
    """
    claim, counter = hypothesis.prediction, exam.counter_prediction
    if exam.hypothesis_id != hypothesis.hypothesis_id:
        raise ValueError("the counter-test names a different hypothesis")
    if exam.challenger == hypothesis.agent and hypothesis.agent != AgentRole.SINGLE:
        raise ValueError("an agent does not cross-examine its own hypothesis")  # one agent may
    if exam.corollary:
        if exam.hypothesis_change is not None:
            raise ValueError("only a control carries the hypothesis's own change")
        if counter.metric == claim.metric:
            raise ValueError("a corollary is on another metric; on the claim's own, use a control")
        if counter.direction == Direction.FLAT:
            raise ValueError("a corollary predicts a move")
        if counter.threshold_kind == ThresholdKind.SIGMA and counter.min_change < MIN_CLAIM_SD:
            # Under 1 sd either way is ordinary play: it would refute or corroborate by noise.
            raise ValueError(f"a corollary under {MIN_CLAIM_SD:g} sd is within ordinary play")
        if (counter.window, counter.compare_to) != (claim.window, claim.compare_to):
            raise ValueError("a corollary keeps the hypothesis's window and baseline")
        return
    if counter.metric != claim.metric:
        raise ValueError("a counter-test on another metric is a corollary")
    control = counter.direction == claim.direction
    if control != (exam.hypothesis_change is not None):
        raise ValueError(
            "a same-way counter-test is a control and carries the hypothesis's own change; "
            "no other counter-test does"
        )
    if counter.threshold_kind != claim.threshold_kind:
        raise ValueError("a counter-test on the hypothesis's metric uses its threshold kind")
    if counter.direction == Direction.FLAT:
        if (
            not _same_family(counter.subject, claim.subject)
            or counter.window != claim.window
            or counter.compare_to == claim.compare_to
        ):
            raise ValueError(
                "a flat counter-test keeps the hypothesis's subject and window "
                "and changes only the baseline"
            )
        if counter.min_change >= claim.min_change:
            raise ValueError(
                "a flat tolerance must be tighter than the change the hypothesis claims"
            )
        return
    if counter.min_change < claim.min_change:
        raise ValueError(
            "a counter-test on the hypothesis's metric claims at least as large a move"
        )
    if control and (
        _same_family(counter.subject, claim.subject)
        or (counter.window, counter.compare_to, counter.min_change)
        != (claim.window, claim.compare_to, claim.min_change)
    ):
        raise ValueError(
            "a control is the claim on another subject: same window, baseline and threshold"
        )
    if counter.direction != claim.direction and (
        not _same_family(counter.subject, claim.subject) or counter.window != claim.window
    ):
        raise ValueError(
            "an opposite-way counter-test keeps the hypothesis's subject and window "
            "and may change only the baseline"
        )
