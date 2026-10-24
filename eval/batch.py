"""Read the product's per-match batch records without importing product or engine code."""

import hashlib
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, Field, NonNegativeInt, StrictBool, model_validator

from contracts.card import InsightCard
from contracts.clock import Window
from contracts.eval_run import EvalRun, Variant
from contracts.taxonomy import CaseOutcome, MomentType
from eval.runner import evaluate
from eval.suites import SuiteBundle


class BatchCase(BaseModel):
    case_id: str = Field(min_length=1)
    moment: MomentType
    window: Window
    outcome: CaseOutcome
    card: InsightCard | None
    published: StrictBool
    tool_calls: NonNegativeInt
    tokens: tuple[NonNegativeInt, NonNegativeInt]
    recovered: StrictBool
    hypotheses: NonNegativeInt
    counter_tests: NonNegativeInt
    final: InsightCard | None = None  # the card's revision once its follow-up settled
    error: None = None


class BatchFailure(BaseModel):
    case_id: str = Field(min_length=1)
    moment: MomentType
    window: Window
    error: str = Field(min_length=1)
    tokens: tuple[NonNegativeInt, NonNegativeInt] | None = None


class BatchMatch(BaseModel):
    match_id: str = Field(min_length=1)
    variant: Variant
    started_at_ms: NonNegativeInt | None = None
    cases: list[BatchCase | BatchFailure]

    @model_validator(mode="after")
    def _identities(self) -> "BatchMatch":
        ids = [c.case_id for c in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("each batch case is listed once")
        for case in self.cases:
            if isinstance(case, BatchFailure):
                continue
            if case.published and case.card is None:
                raise ValueError("a published case must carry its card")
            if case.card is not None:
                if (case.card.match_id, case.card.case_id) != (self.match_id, case.case_id):
                    raise ValueError("card identity must match its batch match and case")
                if case.outcome != case.card.case_outcome:
                    raise ValueError("card outcome must match its batch case")
            if case.final is not None and (case.card is None or case.final.id != case.card.id):
                raise ValueError("a settled follow-up is a later revision of the case's card")
        return self


def evaluate_batch(
    root: str | Path,
    suites: Sequence[SuiteBundle],
    *,
    variant: Variant | str,
    run_id: str | None = None,
    model_id: str | None = None,
    model_tier: str = "dev",
    tool_call_budget: int | None = None,
    wall_time_budget_s: float | None = None,
    started_at_ms: int | None = None,
    finished_at_ms: int | None = None,
    seed: int = 0,
    resamples: int = 2000,
    after_follow_up: bool = False,
) -> EvalRun:
    """Score a batch's published cards; `after_follow_up` scores each card as its follow-up
    left it, where an unresolved follow-up claims no cause."""
    variant = Variant(variant)
    folder = Path(root) / variant.value
    cohort = {entry.match_id for suite in suites for entry in suite.truth.entries}
    paths = sorted(p for p in folder.glob("*.json") if p.stem in cohort)
    if {p.stem for p in paths} != cohort:
        missing = sorted(cohort - {p.stem for p in paths})
        raise ValueError(f"batch files must cover the selected cohort exactly; missing={missing}")
    cards, errors = [], {}
    input_tokens = output_tokens = 0
    starts = [] if started_at_ms is None else [started_at_ms]
    digest = hashlib.sha256()
    for path in paths:
        data = path.read_bytes()
        try:
            match = BatchMatch.model_validate_json(data)
            if match.match_id != path.stem or match.variant != variant:
                raise ValueError("batch match_id or variant does not match its file")
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        digest.update(path.name.encode() + b"\0" + data + b"\0")
        if match.started_at_ms is not None:
            starts.append(match.started_at_ms)
        errors[match.match_id] = {}
        for case in match.cases:
            if case.tokens is not None:
                input_tokens += case.tokens[0]
                output_tokens += case.tokens[1]
            if isinstance(case, BatchFailure):
                errors[match.match_id][case.case_id] = case.error
            elif case.published:
                last = case.final if after_follow_up and case.final else case.card
                if not (last.follow_up and last.follow_up.status == "unresolved"):
                    cards.append(last)
    batch_digest = digest.hexdigest()
    settled = "-after-follow-up" if after_follow_up else ""
    run = evaluate(
        suites,
        cards,
        run_id=run_id or f"batch-{variant}-{batch_digest[:16]}{settled}",
        variant=variant,
        model_id=model_id,
        model_tier=model_tier,
        tool_call_budget=tool_call_budget,
        wall_time_budget_s=wall_time_budget_s,
        seed=seed,
        resamples=resamples,
        started_at_ms=min(starts) if starts else None,
        finished_at_ms=finished_at_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        batch_digest=batch_digest,
        case_errors=errors,
    )
    if run.failed_cases:
        run.notes = "Token totals include recorded usage only; failed cases may omit tokens."
    return run
