"""Score a complete frozen cohort without agent or cloud calls."""

import hashlib
import time
from collections.abc import Iterable, Sequence

from contracts.card import InsightCard
from contracts.eval_run import EvalRun, Variant
from eval.matching import final_cards, score_match
from eval.metrics import METRIC_NAMES, metrics, reconcile
from eval.suites import SuiteBundle


def evaluate(
    suites: Sequence[SuiteBundle],
    cards: Iterable[InsightCard],
    *,
    run_id: str,
    variant: Variant | str,
    model_id: str | None,
    model_tier: str = "dev",
    tool_call_budget: int | None = 16,
    wall_time_budget_s: float | None = 20,
    seed: int = 0,
    resamples: int = 2000,
    started_at_ms: int | None = None,
    finished_at_ms: int | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    batch_digest: str | None = None,
    case_errors: dict[str, dict[str, str]] | None = None,
) -> EvalRun:
    if not suites or len({s.truth.suite for s in suites}) != len(suites):
        raise ValueError("provide distinct suites")
    if len({s.truth.split for s in suites}) != 1:
        raise ValueError("all suites must use the same split")
    started = int(time.time() * 1000) if started_at_ms is None else started_at_ms
    flags = next((s.flags for s in suites if s.flags is not None), None)
    excluded = {e.match_id for e in flags.exclusions} if flags else set()
    cohort = [e.match_id for s in suites for e in s.truth.entries]
    if len(set(cohort)) != len(cohort):
        raise ValueError("suite match ids must be unique")
    cards = list(cards)
    if any(c.match_id not in cohort for c in cards):
        raise ValueError("a card belongs to a match outside the cohort")
    cards = final_cards(cards, batch_published=batch_digest is not None)
    outcomes = [
        score_match(
            e,
            cards,
            s.truth.suite,
            excluded=e.match_id in excluded,
            batch_published=batch_digest is not None,
        )
        for s in suites
        for e in s.truth.entries
    ]
    if case_errors:
        if set(case_errors) - set(cohort):
            raise ValueError("case errors belong to a match outside the cohort")
        for outcome in outcomes:
            outcome.case_errors = case_errors.get(outcome.match_id, {})
            outcome.failed_cases = len(outcome.case_errors)
    if flags:
        reconcile(outcomes, flags.match_ids, list(excluded))
    estimates = metrics(outcomes, seed=seed, resamples=resamples)
    digest = hashlib.sha256(
        "\n".join(
            f"{s.truth.suite}:{s.digest}" for s in sorted(suites, key=lambda s: s.truth.suite)
        ).encode()
    ).hexdigest()
    return EvalRun(
        run_id=run_id,
        variant=variant,
        suites=[s.truth.suite for s in suites],
        split=suites[0].truth.split,
        model_tier=model_tier,
        match_ids=cohort,
        metrics=estimates,
        started_at_ms=started,
        finished_at_ms=int(time.time() * 1000) if finished_at_ms is None else finished_at_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        batch_digest=batch_digest,
        failed_cases=sum(o.failed_cases for o in outcomes),
        flags=flags,
        outcomes=outcomes,
        suite_digest=digest,
        model_id=model_id,
        tool_call_budget=tool_call_budget,
        wall_time_budget_s=wall_time_budget_s,
        bootstrap_seed=seed,
        bootstrap_resamples=resamples,
        undefined_metrics=[n for n in METRIC_NAMES if n not in {m.name for m in estimates}],
    )
