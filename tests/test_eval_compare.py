from pathlib import Path

import pytest

from contracts.eval_run import CardOutcome, Split
from eval.compare import compare
from eval.runner import evaluate
from eval.suites import load_suite

ROOT = Path(__file__).resolve().parents[1]


def run(run_id, variant):
    suites = [load_suite(ROOT / "engine/suites", suite, "dev") for suite in ("planted", "decoys")]
    return evaluate(
        suites,
        [],
        run_id=run_id,
        variant=variant,
        model_id="fixture-model",
        tool_call_budget=16,
        wall_time_budget_s=20,
        resamples=100,
    )


def test_comparison_is_paired_and_round_trips_recorded_outcomes():
    a, b = run("a", "A"), run("b", "B")
    a = type(a).model_validate_json(a.model_dump_json())
    comparison = compare(a, b, resamples=100)
    assert comparison.difference.value == 0
    assert comparison.difference.n == 11
    assert comparison.flag_set_id == a.flags.flag_set_id


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", "a"),
        ("model_id", "another"),
        ("model_tier", "final"),
        ("tool_call_budget", 17),
        ("wall_time_budget_s", 21),
        ("suite_digest", "changed"),
        ("outcomes", []),
        ("match_ids", ["different"]),
        ("split", Split.HELDOUT),
    ],
)
def test_refuses_unpaired_runs(field, value):
    a, b = run("a", "A"), run("b", "B")
    b = b.model_copy(update={field: value})
    with pytest.raises(ValueError):
        compare(a, b, resamples=100)


def test_flags_and_identical_run_ids_cannot_be_swapped():
    a, b = run("a", "A"), run("b", "B")
    b.flags.exclusions = []
    with pytest.raises(ValueError):
        compare(a, b, resamples=100)
    from contracts.eval_run import VariantComparison

    with pytest.raises(ValueError, match="different runs"):
        VariantComparison(
            comparison_id="bad",
            run_a="same",
            run_b="same",
            variant_a="A",
            variant_b="B",
            split="dev",
            difference=a.metrics[0],
        )


@pytest.mark.parametrize("side", ["a", "b"])
@pytest.mark.parametrize("change", ["missing", "value", "n", "suite"])
def test_compared_metric_must_agree_with_each_runs_outcomes(side, change):
    a, b = run("a", "A"), run("b", "B")
    target = a if side == "a" else b
    metric = target.metrics[0]
    if change == "missing":
        target.metrics.remove(metric)
    elif change == "value":
        metric.value = metric.ci_low = metric.ci_high = 1
    elif change == "n":
        metric.n = 999
    else:
        metric.suite = "combined"
    with pytest.raises(ValueError, match="metric"):
        compare(a, b, resamples=100)


def test_paired_bootstrap_uses_aligned_matches_with_nonzero_difference():
    a, b = run("a", "A"), run("b", "B")
    # Different variants succeed on complementary halves of the eligible planted matches.
    eligible = [o for o in a.outcomes if o.suite == "planted" and not o.excluded]
    for i, outcome in enumerate(eligible):
        outcome.correct = i < 7
    for i, outcome in enumerate(o for o in b.outcomes if o.suite == "planted" and not o.excluded):
        outcome.correct = i >= 7
    from eval.metrics import metrics

    a.metrics, b.metrics = metrics(a.outcomes), metrics(b.outcomes)
    comparison = compare(a, b, seed=7, resamples=500)
    assert comparison.difference.value == pytest.approx(3 / 11)
    assert comparison == compare(a, b, seed=7, resamples=500)
    assert comparison.difference.ci_low < 0 < comparison.difference.ci_high
    # Row order never changes which cases are paired.
    b.outcomes.reverse()
    assert comparison == compare(a, b, seed=7, resamples=500)


def test_precision_comparison_resamples_matches_with_all_their_cards():
    from eval.metrics import metrics

    a, b = run("a", "A"), run("b", "B")
    for target, count, correct in [(a, 2, True), (b, 3, False)]:
        target.outcomes[0].cards = [
            CardOutcome(
                card_id=str(i), revision=1, outcome="explained", correct=correct, reason="fixture"
            )
            for i in range(count)
        ]
        target.metrics = metrics(target.outcomes)
        target.undefined_metrics = []
    result = compare(a, b, metric="cause_precision", seed=7, resamples=100)
    assert result.difference.value == 1
    assert result.difference.n == len(a.outcomes)


def test_precision_comparison_refuses_a_bootstrap_with_no_defined_pairs():
    from eval.metrics import metrics

    a, b = run("a", "A"), run("b", "B")
    for target in (a, b):
        outcome = min(target.outcomes, key=lambda o: o.match_id)
        outcome.cards = [
            CardOutcome(
                card_id="fixture", revision=1, outcome="explained", correct=True, reason="fixture"
            )
        ]
        target.metrics = metrics(target.outcomes)
        target.undefined_metrics = []
    with pytest.raises(ValueError, match="no defined bootstrap resamples"):
        compare(a, b, metric="cause_precision", seed=0, resamples=1)
