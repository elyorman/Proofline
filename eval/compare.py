"""Validate provenance and bootstrap A-minus-B over identical sampled matches."""

import random

from contracts.eval_run import EvalRun, MetricEstimate, VariantComparison
from eval.metrics import PLANTED_RECALL, interval, metric_suite, ratio, samples


def compare(
    a: EvalRun, b: EvalRun, *, metric: str = PLANTED_RECALL, seed: int = 0, resamples: int = 2000
) -> VariantComparison:
    a = EvalRun.model_validate_json(a.model_dump_json())
    b = EvalRun.model_validate_json(b.model_dump_json())
    if a.run_id == b.run_id or a.variant == b.variant:
        raise ValueError("a comparison needs different runs and variants")
    if resamples < 1:
        raise ValueError("resamples must be positive")
    batch = a.batch_digest is not None and b.batch_digest is not None
    if (a.batch_digest is None) != (b.batch_digest is None):
        raise ValueError("paired runs must use the same publication convention")
    unverified = []
    for field in (
        "split",
        "model_tier",
        "suite_digest",
        "model_id",
        "tool_call_budget",
        "wall_time_budget_s",
    ):
        if getattr(a, field) != getattr(b, field):
            raise ValueError(f"paired runs need identical {field}")
        if getattr(a, field) is None:
            if not batch or field not in ("model_id", "tool_call_budget", "wall_time_budget_s"):
                raise ValueError(f"paired runs need identical {field}")
            unverified.append(field)
    if set(a.match_ids) != set(b.match_ids) or set(a.suites) != set(b.suites):
        raise ValueError("paired runs need the same cohort and suites")
    flag_a = a.flags.flag_set_id if a.flags else None
    flag_b = b.flags.flag_set_id if b.flags else None
    if flag_a != flag_b:
        raise ValueError("paired runs need the same frozen flag set")
    if not a.outcomes or not b.outcomes:
        raise ValueError("paired runs need recorded per-match outcomes")
    by_a = {o.match_id: o for o in a.outcomes}
    by_b = {o.match_id: o for o in b.outcomes}
    ids = sorted(by_a)
    if any((by_a[i].suite, by_a[i].excluded) != (by_b[i].suite, by_b[i].excluded) for i in ids):
        raise ValueError("paired outcomes disagree on suite or exclusions")
    rows_a = samples([by_a[i] for i in ids], metric)
    rows_b = samples([by_b[i] for i in ids], metric)
    point_a, point_b = ratio(rows_a), ratio(rows_b)
    if point_a is None or point_b is None:
        raise ValueError("the comparison metric is undefined")
    scope = metric_suite(a.outcomes, metric)
    for run, rows, point in ((a, rows_a, point_a), (b, rows_b, point_b)):
        recorded = [m for m in run.metrics if m.name == metric]
        if len(recorded) != 1:
            raise ValueError("the comparison metric must be recorded once in each run")
        estimate = recorded[0]
        if (estimate.value, estimate.n, estimate.suite) != (point, sum(d for _, d in rows), scope):
            raise ValueError("the recorded metric disagrees with per-match outcomes")
    point = point_a - point_b
    paired = list(zip(rows_a, rows_b, strict=True))
    rng, values = random.Random(seed), []
    for _ in range(resamples):
        drawn = rng.choices(paired, k=len(paired))
        x, y = ratio([r[0] for r in drawn]), ratio([r[1] for r in drawn])
        if x is not None and y is not None:
            values.append(x - y)
    low, high = interval(values, point)
    return VariantComparison(
        comparison_id=f"{a.run_id}-vs-{b.run_id}-{metric}",
        run_a=a.run_id,
        run_b=b.run_id,
        variant_a=a.variant,
        variant_b=b.variant,
        split=a.split,
        difference=MetricEstimate(
            name=metric, suite=scope, value=point, ci_low=low, ci_high=high, n=len(paired)
        ),
        flag_set_id=flag_a,
        suite_digest=a.suite_digest,
        match_ids=ids,
        bootstrap_seed=seed,
        bootstrap_resamples=resamples,
        unverified_configuration=unverified,
        failed_cases_a=a.failed_cases,
        failed_cases_b=b.failed_cases,
    )
