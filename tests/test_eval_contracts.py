from pathlib import Path

import pytest

from contracts.eval_run import EvalRun, Exclusion, FlagSet

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("change", ["missing", "duplicate", "metric", "direction", "unplantable"])
def test_exclusions_require_every_observable_of_their_class(change):
    flags = FlagSet.model_validate_json(
        (ROOT / "engine/suites/planted/dev/ground_truth_flags.json").read_text()
    )
    raw = flags.exclusions[0].model_dump(mode="json")
    if change == "missing":
        raw["observables"].pop()
    elif change == "duplicate":
        raw["observables"][1] = raw["observables"][0]
    elif change == "metric":
        raw["observables"][1]["metric"] = "long_ball_share"
    elif change == "direction":
        raw["observables"][1]["direction"] = "up"
    else:
        raw["cause"] = "tactical.block_deeper"
    with pytest.raises(ValueError, match="observables|cannot be planted"):
        Exclusion.model_validate(raw)


@pytest.fixture
def run_record():
    flags = FlagSet.model_validate_json(
        (ROOT / "engine/suites/planted/dev/ground_truth_flags.json").read_text()
    )
    excluded = {e.match_id for e in flags.exclusions}
    return EvalRun(
        run_id="fixture",
        variant="A",
        suites=["planted"],
        split="dev",
        model_tier="dev",
        model_id="fixture",
        tool_call_budget=16,
        wall_time_budget_s=20,
        suite_digest="a" * 64,
        match_ids=flags.match_ids,
        flags=flags,
        started_at_ms=flags.frozen_at_ms,
        finished_at_ms=flags.frozen_at_ms,
        metrics=[dict(name="all_planted_recall", suite="planted", value=0, n=len(flags.match_ids))],
        outcomes=[
            dict(
                match_id=m,
                suite="planted",
                correct=False,
                reason="no published card",
                excluded=m in excluded,
            )
            for m in flags.match_ids
        ],
    )


@pytest.mark.parametrize(
    "field", ["suite_digest", "model_id", "tool_call_budget", "wall_time_budget_s"]
)
def test_scored_runs_require_provenance(run_record, field):
    raw = run_record.model_dump(mode="json")
    raw[field] = None
    with pytest.raises(ValueError, match="provenance"):
        EvalRun.model_validate(raw)


def test_duplicate_and_contradictory_metric_records_are_refused(run_record):
    raw = run_record.model_dump(mode="json")
    raw["metrics"].append(raw["metrics"][0])
    with pytest.raises(ValueError, match="metric"):
        EvalRun.model_validate(raw)
    raw = run_record.model_dump(mode="json")
    raw["undefined_metrics"].append(raw["metrics"][0]["name"])
    with pytest.raises(ValueError, match="metric"):
        EvalRun.model_validate(raw)


def test_batch_records_keep_missing_configuration_explicit(run_record):
    raw = run_record.model_dump(mode="json")
    raw.update(batch_digest="b" * 64, model_id=None, tool_call_budget=None, wall_time_budget_s=None)
    run = EvalRun.model_validate(raw)
    assert run.batch_digest == "b" * 64 and run.model_id is None
    raw["suite_digest"] = None
    with pytest.raises(ValueError, match="provenance"):
        EvalRun.model_validate(raw)


def test_failure_counts_must_reconcile_with_case_errors(run_record):
    raw = run_record.model_dump(mode="json")
    raw["outcomes"][0]["case_errors"] = {"failed": "timeout"}
    with pytest.raises(ValueError, match="failed_cases"):
        EvalRun.model_validate(raw)
    raw["outcomes"][0]["failed_cases"] = 1
    with pytest.raises(ValueError, match="failed_cases"):
        EvalRun.model_validate(raw)
    raw["failed_cases"] = 1
    assert EvalRun.model_validate(raw).failed_cases == 1
