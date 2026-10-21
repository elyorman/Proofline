"""Evaluation run record. Every number in the README comes from one of these."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


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
    notes: str = ""

    @model_validator(mode="after")
    def _timing(self) -> "EvalRun":
        if self.finished_at_ms < self.started_at_ms:
            raise ValueError("finished before started")
        return self
