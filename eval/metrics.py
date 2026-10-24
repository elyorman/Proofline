"""Match-cluster bootstrap estimates, including pooled card precision."""

import random
from collections.abc import Sequence

from contracts.eval_run import MatchOutcome, MetricEstimate, Suite
from contracts.taxonomy import CaseOutcome

PLANTED_RECALL = "planted_recall"
ALL_PLANTED_RECALL = "all_planted_recall"
CAUSE_PRECISION = "cause_precision"
DECOY_RESTRAINT = "decoy_restraint"
METRIC_NAMES = (PLANTED_RECALL, ALL_PLANTED_RECALL, CAUSE_PRECISION, DECOY_RESTRAINT)


def samples(outcomes: Sequence[MatchOutcome], name: str) -> list[tuple[int, int]]:
    if name == CAUSE_PRECISION:
        return [
            (
                sum(c.holds for c in o.cards if c.outcome == CaseOutcome.EXPLAINED),
                sum(c.outcome == CaseOutcome.EXPLAINED for c in o.cards),
            )
            for o in outcomes
        ]
    if name not in METRIC_NAMES:
        raise ValueError(f"unknown metric {name}")
    suite = Suite.DECOYS if name == DECOY_RESTRAINT else Suite.PLANTED
    return [
        (int(o.correct), 1)
        for o in outcomes
        if o.suite == suite and not (name == PLANTED_RECALL and o.excluded)
    ]


def metric_suite(outcomes: Sequence[MatchOutcome], name: str) -> Suite | str:
    if name == CAUSE_PRECISION:
        suites = {o.suite for o in outcomes}
        return "combined" if len(suites) > 1 else next(iter(suites))
    return Suite.DECOYS if name == DECOY_RESTRAINT else Suite.PLANTED


def ratio(rows: Sequence[tuple[int, int]]) -> float | None:
    denominator = sum(d for _, d in rows)
    return sum(n for n, _ in rows) / denominator if denominator else None


def interval(values: list[float], point: float) -> tuple[float, float]:
    if not values:
        raise ValueError("no defined bootstrap resamples; increase resamples")
    values.sort()
    return min(point, values[int(0.025 * (len(values) - 1))]), max(
        point, values[int(0.975 * (len(values) - 1))]
    )


def estimate(
    name: str,
    suite: Suite | str,
    rows: Sequence[tuple[int, int]],
    *,
    seed: int = 0,
    resamples: int = 2000,
) -> MetricEstimate | None:
    if resamples < 1:
        raise ValueError("resamples must be positive")
    point = ratio(rows)
    if point is None:
        return None
    rng = random.Random(seed)
    values = []
    for _ in range(resamples):
        value = ratio(rng.choices(rows, k=len(rows)))
        if value is not None:
            values.append(value)
    low, high = interval(values, point)
    return MetricEstimate(
        name=name, suite=suite, value=point, ci_low=low, ci_high=high, n=sum(d for _, d in rows)
    )


def metrics(
    outcomes: Sequence[MatchOutcome], *, seed: int = 0, resamples: int = 2000
) -> list[MetricEstimate]:
    suites = {o.suite for o in outcomes}
    if not suites:
        return []
    result = []
    for name in METRIC_NAMES:
        scope = metric_suite(outcomes, name)
        metric = estimate(name, scope, samples(outcomes, name), seed=seed, resamples=resamples)
        if metric is not None:
            result.append(metric)
    return result


def reconcile(
    outcomes: Sequence[MatchOutcome], planted: Sequence[str], exclusions: Sequence[str]
) -> None:
    rows = [o for o in outcomes if o.suite == Suite.PLANTED]
    all_ids = {o.match_id for o in rows}
    excluded = {o.match_id for o in rows if o.excluded}
    eligible = {o.match_id for o in rows if not o.excluded}
    if (
        len(rows) != len(all_ids)
        or all_ids != set(planted)
        or excluded != set(exclusions)
        or eligible & excluded
        or len(eligible) + len(excluded) != len(planted)
    ):
        raise ValueError("headline, exclusions and all-script matches do not reconcile")
