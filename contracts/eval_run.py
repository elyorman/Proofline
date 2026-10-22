"""Evaluation run record. Every number in the README comes from one of these."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from contracts.prediction import Direction
from contracts.taxonomy import Cause, Metric

VISIBILITY_SDS = 2.0  # spec §7.2: separation a script needs on at least one observable


class Variant(StrEnum):
    A_PROOFLINE = "A"
    B_SINGLE_AGENT = "B"
    C_NO_CROSS_EXAM = "C"  # stretch


class Suite(StrEnum):
    PLANTED = "planted"
    DECOYS = "decoys"
    CORRECTIONS = "corrections"
    CONFOUNDED = "confounded"  # stretch
    SEEDED_FALSE_CLAIMS = "seeded_false_claims"


class Split(StrEnum):
    DEV = "dev"
    HELDOUT = "heldout"


class MetricEstimate(BaseModel):
    name: str
    suite: Suite
    value: float
    ci_low: float | None = None
    ci_high: float | None = None
    n: int = Field(ge=0)

    @model_validator(mode="after")
    def _ci_brackets_value(self) -> "MetricEstimate":
        if (self.ci_low is None) != (self.ci_high is None):
            raise ValueError("ci_low and ci_high come together")
        if self.ci_low is not None and not (self.ci_low <= self.value <= self.ci_high):
            raise ValueError("confidence interval must contain the point estimate")
        return self


class ExclusionRule(StrEnum):
    """Spec §7.2. Each excluded script is counted once, under the first rule it meets."""

    PAIRED_EFFECT = "paired_effect"  # no observable's paired CI clears zero its way
    SINGLE_MATCH = "single_match"  # one does, but none separates by VISIBILITY_SDS


class ObservableCheck(BaseModel):
    metric: Metric
    subject: str
    direction: Direction
    separation: float = Field(description="natural sds, positive when it moves `direction`")
    ci_low: float
    ci_high: float

    @model_validator(mode="after")
    def _checkable(self) -> "ObservableCheck":
        if self.direction == Direction.FLAT:
            raise ValueError("an observable of a cause moves up or down")
        if self.ci_low > self.ci_high:
            raise ValueError("ci_low is above ci_high")
        return self

    @property
    def clears_zero(self) -> bool:
        return self.ci_low > 0 if self.direction == Direction.UP else self.ci_high < 0


class Exclusion(BaseModel):
    """A planted script left out of recall as not_observable, with the numbers why."""

    script_id: str
    cause: Cause
    rule: ExclusionRule
    observables: list[ObservableCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def _rule_fits_numbers(self) -> "Exclusion":
        cleared = any(o.clears_zero for o in self.observables)
        if self.rule == ExclusionRule.PAIRED_EFFECT and cleared:
            raise ValueError(f"{self.script_id}: an observable's CI clears zero its way")
        if self.rule == ExclusionRule.SINGLE_MATCH:
            if not cleared:
                raise ValueError(f"{self.script_id}: the paired-effect rule applies first")
            if any(o.separation >= VISIBILITY_SDS for o in self.observables):
                raise ValueError(f"{self.script_id}: an observable separates enough to count")
        return self


class EvalRun(BaseModel):
    run_id: str
    variant: Variant
    suites: list[Suite] = Field(min_length=1)
    split: Split
    model_tier: str = Field(description="dev | final")
    match_ids: list[str] = Field(min_length=1)
    metrics: list[MetricEstimate] = Field(min_length=1)
    started_at_ms: int = Field(ge=0)
    finished_at_ms: int = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    foundry_eval_run: str | None = None
    not_observable: list[Exclusion] = Field(
        default_factory=list, description="planted scripts excluded from recall (spec §7.2)"
    )
    notes: str = ""

    @model_validator(mode="after")
    def _timing(self) -> "EvalRun":
        if self.finished_at_ms < self.started_at_ms:
            raise ValueError("finished before started")
        return self

    @model_validator(mode="after")
    def _metrics_from_run_suites(self) -> "EvalRun":
        for m in self.metrics:
            if m.suite not in self.suites:
                raise ValueError(f"metric {m.name} is from {m.suite}, a suite this run did not run")
        return self

    @model_validator(mode="after")
    def _exclusions_from_planted_runs(self) -> "EvalRun":
        if self.not_observable and Suite.PLANTED not in self.suites:
            raise ValueError("only a run of the planted suite excludes scripts")
        ids = [x.script_id for x in self.not_observable]
        if len(ids) != len(set(ids)):
            raise ValueError("each excluded script is listed once")
        return self


class VariantComparison(BaseModel):
    """Paired comparison of two runs on the same cases, e.g. Proofline vs single agent.

    `difference` is variant_a minus variant_b, with a paired bootstrap CI over the
    cases both runs scored; never derived from the two runs' separate CIs. Stored in
    eval_runs beside the runs it compares, so the README's A-vs-B number has a record.
    """

    comparison_id: str
    run_a: str = Field(description="run_id of variant_a's EvalRun")
    run_b: str = Field(description="run_id of variant_b's EvalRun")
    variant_a: Variant
    variant_b: Variant
    split: Split
    difference: MetricEstimate

    @model_validator(mode="after")
    def _two_variants(self) -> "VariantComparison":
        if self.variant_a == self.variant_b:
            raise ValueError("a comparison needs two different variants")
        return self
