"""Paired question differences, resampling both variants' complete match clusters."""

import random

from contracts.eval_run import (
    QUESTION_METRICS,
    MetricEstimate,
    QuestionRun,
    Suite,
    VariantComparison,
)
from eval.metrics import interval, ratio
from eval.questions import question_samples


def compare_questions(
    a: QuestionRun,
    b: QuestionRun,
    *,
    metric: str = QUESTION_METRICS[0],
    seed: int = 0,
    resamples: int = 2000,
) -> VariantComparison:
    a = QuestionRun.model_validate_json(a.model_dump_json())
    b = QuestionRun.model_validate_json(b.model_dump_json())
    if metric not in QUESTION_METRICS or resamples < 1:
        raise ValueError("provide a known question metric and positive resamples")
    if a.run_id == b.run_id or a.variant == b.variant:
        raise ValueError("a paired question comparison needs different runs and variants")
    for name in ("split", "question_set_digest", "suite_digest", "model_id", "tool_call_budget"):
        if getattr(a, name) != getattr(b, name):
            raise ValueError(f"paired question runs need identical {name}")
    by_a, by_b = ({r.question_id: r for r in run.rows} for run in (a, b))
    if set(by_a) != set(by_b):
        raise ValueError("paired runs need the same question set")
    for identity in by_a:
        left, right = by_a[identity], by_b[identity]
        if (left.match_id, left.premise_true, left.expected_cause, left.expected_team) != (
            right.match_id,
            right.premise_true,
            right.expected_cause,
            right.expected_team,
        ):
            raise ValueError("paired question truth differs")
    common = sorted(q for q in by_a if by_a[q].answered and by_b[q].answered)
    if not common:
        raise ValueError("no questions were answered by both variants")
    rows_a = question_samples([by_a[q] for q in common], metric)
    rows_b = question_samples([by_b[q] for q in common], metric)
    point_a, point_b = ratio(rows_a), ratio(rows_b)
    if point_a is None or point_b is None:
        raise ValueError("comparison metric is undefined over paired answered questions")
    point = point_a - point_b
    pairs = list(zip(rows_a, rows_b, strict=True))
    values, rng = [], random.Random(seed)
    for _ in range(resamples):
        draw = rng.choices(pairs, k=len(pairs))
        left, right = ratio([x for x, _ in draw]), ratio([y for _, y in draw])
        if left is not None and right is not None:
            values.append(left - right)
    low, high = interval(values, point)
    n = len(common) if metric == "claim_precision" else sum(d for _, d in rows_a)
    return VariantComparison(
        comparison_id=f"{a.run_id}-vs-{b.run_id}-{metric}",
        run_a=a.run_id,
        run_b=b.run_id,
        variant_a=a.variant,
        variant_b=b.variant,
        split=a.split,
        comparison_type="questions",
        question_set_digest=a.question_set_digest,
        suite_digest=a.suite_digest,
        question_ids=common,
        unpaired_question_ids=sorted(set(by_a) - set(common)),
        match_ids=sorted({by_a[q].match_id for q in common}),
        model_id=a.model_id,
        tool_call_budget=a.tool_call_budget,
        unverified_configuration=[
            name for name in ("model_id", "tool_call_budget") if getattr(a, name) is None
        ],
        difference=MetricEstimate(
            name=metric, suite=Suite.QUESTIONS, value=point, ci_low=low, ci_high=high, n=n
        ),
        bootstrap_seed=seed,
        bootstrap_resamples=resamples,
    )
