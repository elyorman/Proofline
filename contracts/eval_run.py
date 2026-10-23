"""Evaluation run record. Every number in the README comes from one of these."""

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from contracts.prediction import Direction
from contracts.taxonomy import Cause, Metric

VISIBILITY_SDS = 2.0  # spec §7.2: separation a script needs on at least one observable
MIN_SEED_PAIRS = 20  # spec §7.2: each script is estimated over 20-30 seed pairs


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


# Spec §11.1: the seeds each split's suites and paired runs are drawn from.
SEED_RANGES = {Split.DEV: range(1000, 2000), Split.HELDOUT: range(2000, 3000)}


class MetricEstimate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

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

    NO_PAIRED_EFFECT = "no_paired_effect"  # no observable's paired CI clears zero its way
    NO_SEPARATION = "no_separation"  # one does, but none separates by VISIBILITY_SDS its way


class ObservableCheck(BaseModel):
    """One observable of an excluded script, with the numbers spec §7.2 judges it by.

    `separation` is signed like the engine's (engine/visibility.py) and like the
    paired-effect interval: positive when the observable rose. Both are judged in
    `direction`, the way the observable moves when the class is present.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    metric: Metric
    subject: str = Field(min_length=1)
    direction: Direction
    separation: float = Field(description="natural sds, signed: positive when it rose")
    ci_low: float
    ci_high: float

    @model_validator(mode="after")
    def _checkable(self) -> "ObservableCheck":
        if self.direction == Direction.FLAT:
            raise ValueError("an observable of a cause moves up or down")
        if self.ci_low > self.ci_high:
            raise ValueError("ci_low is above ci_high")
        if (self.ci_low > 0 and self.separation < 0) or (self.ci_high < 0 and self.separation > 0):
            raise ValueError("separation points against the paired-effect interval")
        return self

    @property
    def clears_zero(self) -> bool:
        return self.ci_low > 0 if self.direction == Direction.UP else self.ci_high < 0

    @property
    def separates(self) -> bool:
        """Visible in one match: VISIBILITY_SDS or more in the observable's direction."""
        way = self.separation if self.direction == Direction.UP else -self.separation
        return way >= VISIBILITY_SDS


class Exclusion(BaseModel):
    """A planted match left out of recall as not_observable, with the numbers why."""

    match_id: str
    cause: Cause
    rule: ExclusionRule
    observables: list[ObservableCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def _rule_fits_numbers(self) -> "Exclusion":
        if self.cause.domain == "fallback":
            raise ValueError("'other' and 'none' are outcomes, never planted causes")
        cleared = any(o.clears_zero for o in self.observables)
        if self.rule == ExclusionRule.NO_PAIRED_EFFECT and cleared:
            raise ValueError(f"{self.match_id}: an observable's CI clears zero its way")
        if self.rule == ExclusionRule.NO_SEPARATION:
            if not cleared:
                raise ValueError(f"{self.match_id}: the paired-effect rule applies first")
            if any(o.separates for o in self.observables):
                raise ValueError(f"{self.match_id}: an observable separates enough to count")
        return self


class FlagSet(BaseModel):
    """The frozen not_observable flags of one planted suite split, with their provenance.

    Every planted EvalRun embeds the same flag set, frozen before either variant ran, so
    both variants exclude the same matches and the scoreboard can show why.
    """

    split: Split
    match_ids: list[str] = Field(min_length=1, description="every planted match considered")
    paired_seeds: dict[str, list[int]] = Field(description="per match, the seeds measured")
    frozen_at_ms: int = Field(ge=0, description="epoch milliseconds")
    exclusions: list[Exclusion] = Field(default_factory=list)

    @computed_field
    @property
    def flag_set_id(self) -> str:
        content = self.model_dump(
            mode="json", include={"split", "match_ids", "paired_seeds", "exclusions"}
        )
        digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        return f"flags-{digest[:16]}"

    @model_validator(mode="after")
    def _covers_its_matches(self) -> "FlagSet":
        if len(self.match_ids) != len(set(self.match_ids)):
            raise ValueError("each planted match is listed once")
        if set(self.paired_seeds) != set(self.match_ids):
            raise ValueError("every planted match, and only those, has its paired seeds")
        for m, seeds in self.paired_seeds.items():
            if len(seeds) != len(set(seeds)):
                raise ValueError(f"{m}: a seed is measured once")
            if len(seeds) < MIN_SEED_PAIRS:
                raise ValueError(f"fewer than {MIN_SEED_PAIRS} seed pairs for {m}")
            if not set(seeds) <= set(SEED_RANGES[self.split]):
                raise ValueError(f"{m}: paired seeds outside the {self.split} range")
        excluded = [x.match_id for x in self.exclusions]
        if len(excluded) != len(set(excluded)):
            raise ValueError("each excluded match is listed once")
        unknown = sorted(set(excluded) - set(self.match_ids))
        if unknown:
            raise ValueError(f"exclusions name matches outside the set: {unknown}")
        return self


class EvalRun(BaseModel):
    run_id: str
    variant: Variant
    suites: list[Suite] = Field(min_length=1)
    split: Split
    model_tier: str = Field(description="dev | final")
    match_ids: list[str] = Field(min_length=1)
    metrics: list[MetricEstimate] = Field(min_length=1)
    started_at_ms: int = Field(ge=0, description="epoch milliseconds")
    finished_at_ms: int = Field(ge=0, description="epoch milliseconds")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    foundry_eval_run: str | None = None
    flags: FlagSet | None = Field(
        default=None, description="the planted suite's frozen not_observable flags (spec §7.2)"
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
    def _planted_runs_carry_frozen_flags(self) -> "EvalRun":
        planted = Suite.PLANTED in self.suites
        if planted != (self.flags is not None):
            raise ValueError("a planted-suite run carries its flag set, and only such a run")
        if self.flags is not None:
            if self.flags.split != self.split:
                raise ValueError("the flag set is for another split")
            if self.flags.frozen_at_ms > self.started_at_ms:
                raise ValueError("flags must be frozen before the run starts")
            missing = sorted(set(self.flags.match_ids) - set(self.match_ids))
            if missing:
                raise ValueError(f"a planted run scores every flagged match; missing {missing}")
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
