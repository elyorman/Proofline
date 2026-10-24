import pytest

from contracts.eval_run import MatchOutcome
from eval.metrics import (
    ALL_PLANTED_RECALL,
    PLANTED_RECALL,
    estimate,
    interval,
    metrics,
    reconcile,
    wilson,
)


def test_proportions_are_reproducible_and_handle_undefined_denominators():
    rows = [(1, 1), (0, 1), (1, 1), (0, 0)]
    first = estimate("test", "planted", rows, seed=7, resamples=300)
    assert first == estimate("test", "planted", rows, seed=7, resamples=300)
    assert first.value == pytest.approx(2 / 3)
    assert first.ci_low <= first.value <= first.ci_high
    assert estimate("test", "planted", [(0, 0)], seed=7, resamples=100) is None


def test_exclusions_change_recall_but_never_remove_precision():
    rows = [
        MatchOutcome(match_id="a", suite="planted", correct=True, reason="matched"),
        MatchOutcome(
            match_id="b",
            suite="planted",
            correct=False,
            reason="missed",
            excluded=True,
            cards=[
                dict(
                    card_id="c",
                    revision=1,
                    outcome="explained",
                    correct=False,
                    holds=False,
                    reason="class mismatch",
                )
            ],
        ),
    ]
    result = {m.name: m for m in metrics(rows, seed=3, resamples=100)}
    assert result[PLANTED_RECALL].value == 1
    assert result[ALL_PLANTED_RECALL].value == 0.5
    assert result["cause_precision"].value == 0
    assert result["cause_precision"].n == 1
    reconcile(rows, ["a", "b"], ["b"])
    with pytest.raises(ValueError, match="reconcile"):
        reconcile(rows, ["a", "b", "missing"], ["b"])


def test_precision_pools_explained_cards_and_leaves_other_out():
    rows = [
        MatchOutcome(
            match_id="a",
            suite="planted",
            correct=True,
            reason="matched",
            cards=[
                dict(
                    card_id="a",
                    revision=1,
                    outcome="explained",
                    correct=True,
                    holds=True,
                    reason="matched",
                )
            ],
        ),
        MatchOutcome(
            match_id="b",
            suite="decoys",
            correct=False,
            reason="explanation on decoy",
            cards=[
                dict(
                    card_id=str(i),
                    revision=1,
                    outcome="other",
                    correct=False,
                    holds=False,
                    reason="wrong",
                )
                for i in range(3)
            ],
        ),
    ]
    precision = next(m for m in metrics(rows, resamples=100) if m.name == "cause_precision")
    assert precision.value == 1.0
    assert precision.n == 1
    assert precision.suite == "combined"


def test_a_bootstrap_with_no_defined_resamples_does_not_invent_an_interval():
    with pytest.raises(ValueError, match="no defined bootstrap resamples"):
        interval([], 1.0)


def test_wilson_keeps_uncertainty_at_both_boundaries():
    low, high = wilson(4, 4)
    assert low == pytest.approx(0.5101091635) and high == 1
    low, high = wilson(0, 4)
    assert low == 0 and high == pytest.approx(0.4898908365)
    metric = estimate("test", "decoys", [(1, 1)] * 4)
    assert metric.ci_method == "wilson" and metric.n == 4
    assert metric.ci_low == pytest.approx(0.5101091635) and metric.ci_high == 1
    assert estimate("test", "decoys", [(0, 0), (4, 4)], resamples=1) == metric
    with pytest.raises(ValueError):
        wilson(0, 0)
