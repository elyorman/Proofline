import json
import re
import time
from pathlib import Path

import pytest

from contracts.eval_run import EvalRun, VariantComparison
from eval.__main__ import main
from eval.batch import evaluate_batch
from eval.suites import load_suite

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def batch(tmp_path):
    suites = [load_suite(ROOT / "engine/suites", name, "dev") for name in ("planted", "decoys")]
    started_at_ms = int(time.time() * 1000)
    for variant in ("A", "B"):
        (tmp_path / variant).mkdir()
        for suite in suites:
            for truth in suite.truth.entries:
                (tmp_path / variant / f"{truth.match_id}.json").write_text(
                    json.dumps(
                        dict(
                            match_id=truth.match_id,
                            variant=variant,
                            started_at_ms=started_at_ms,
                            cases=[],
                        )
                    )
                )
    excluded = {e.match_id for e in suites[0].flags.exclusions}
    truth = next(t for t in suites[0].truth.entries if t.match_id not in excluded)
    example = re.search(
        r"## 5\. Insight Card.*?```json\n(.*?)```", (ROOT / "docs/spec.md").read_text(), re.S
    )[1]
    card = json.loads(example)
    card.update(id="batch-card", match_id=truth.match_id, case_id="found", status="verified")
    card["subject"]["team"] = truth.team
    observable = truth.observables[0]
    card["propositions"] = [
        dict(
            id="change",
            type="change",
            metric=observable.metric,
            subject=observable.subject,
            direction=observable.direction,
            window=str(truth.window),
            baseline="first_half",
        ),
        dict(
            id="primary",
            type="attribution",
            cause=truth.cause,
            effect="change",
            role="primary",
            hypothesis_id="h1",
            agent="single",
        ),
    ]
    case = dict(
        case_id="found",
        moment="pressure_shift",
        window=str(truth.window),
        outcome="explained",
        card=card,
        published=True,
        tool_calls=9,
        tokens=[20, 10],
        recovered=False,
        hypotheses=4,
        counter_tests=3,
    )
    return tmp_path, suites, truth, case


def write_cases(batch, variant, match_id, cases):
    root = batch[0]
    path = root / variant / f"{match_id}.json"
    raw = json.loads(path.read_text())
    path.write_text(json.dumps(raw | dict(cases=cases)))


def test_batch_uses_publication_flags_and_keeps_errors_tokens_and_run_times(batch):
    root, suites, truth, case = batch
    unpublished = dict(case, case_id="rejected", published=False, card=None, tokens=[7, 4])
    failed = dict(case_id="failed", moment="pressure_shift", window="58:00-63:00", error="timeout")
    write_cases(batch, "A", truth.match_id, [case, unpublished, failed])
    start = json.loads((root / "A" / f"{truth.match_id}.json").read_text())["started_at_ms"]
    run = evaluate_batch(
        root, suites, variant="A", started_at_ms=start, finished_at_ms=start + 200, resamples=100
    )
    assert len(run.outcomes) == 16
    assert run.input_tokens == 27 and run.output_tokens == 14
    assert (run.started_at_ms, run.finished_at_ms) == (start, start + 200)
    assert run.failed_cases == 1
    result = next(o for o in run.outcomes if o.match_id == truth.match_id)
    assert result.correct and result.failed_cases == 1
    assert result.case_errors == {"failed": "timeout"}
    assert len(result.cards) == 1
    assert EvalRun.model_validate_json(run.model_dump_json()) == run


def test_a_decoy_closed_as_none_is_restraint_and_a_claimed_cause_is_not(batch):
    root, suites, _, case = batch
    decoy = suites[1].truth.entries[0]
    card = dict(case["card"], match_id=decoy.match_id, case_outcome="none")
    card["propositions"] = card["propositions"][:1]
    write_cases(batch, "A", decoy.match_id, [dict(case, outcome="none", card=card)])
    run = evaluate_batch(root, suites, variant="A", resamples=100)
    assert next(o for o in run.outcomes if o.match_id == decoy.match_id).correct
    claimed = dict(case["card"], match_id=decoy.match_id)
    write_cases(batch, "A", decoy.match_id, [dict(case, card=claimed)])
    run = evaluate_batch(root, suites, variant="A", resamples=100)
    assert not next(o for o in run.outcomes if o.match_id == decoy.match_id).correct


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "variant",
        "match_id",
        "card_match",
        "card_case",
        "tokens",
        "duplicate",
        "unverified",
    ],
)
def test_batch_refuses_incomplete_or_inconsistent_inputs(batch, change):
    root, suites, truth, case = batch
    if change == "missing":
        (root / "A" / f"{truth.match_id}.json").unlink()
    else:
        if change == "card_match":
            case["card"]["match_id"] = "unrelated"
        elif change == "card_case":
            case["card"]["case_id"] = "unrelated"
        elif change == "tokens":
            case["tokens"] = [-1, 10]
        elif change == "unverified":
            case["card"]["verification"] = None
            case["card"]["status"] = "proposed"
        write_cases(batch, "A", truth.match_id, [case, case] if change == "duplicate" else [case])
        path = root / "A" / f"{truth.match_id}.json"
        if change in ("variant", "match_id"):
            raw = json.loads(path.read_text())
            raw[change] = "B" if change == "variant" else "unrelated"
            path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        evaluate_batch(root, suites, variant="A", resamples=100)


def test_cli_scores_batch_to_json_stdout(batch, capsys):
    root, _, truth, case = batch
    write_cases(batch, "A", truth.match_id, [case])
    start = json.loads((root / "A" / f"{truth.match_id}.json").read_text())["started_at_ms"]
    assert (
        main(
            [
                "--runs",
                str(root),
                "--split",
                "dev",
                "--variant",
                "A",
                "--started-at-ms",
                str(start),
                "--finished-at-ms",
                str(start + 100),
                "--resamples",
                "100",
            ]
        )
        == 0
    )
    run = EvalRun.model_validate_json(capsys.readouterr().out)
    assert run.input_tokens == 20 and run.output_tokens == 10
    assert run.started_at_ms == start
    assert run.failed_cases == 0 and len(run.outcomes) == 16


def test_cli_compares_batch_variants_with_paired_outcomes(batch, capsys):
    root, _, truth, case = batch
    write_cases(batch, "A", truth.match_id, [case])
    write_cases(
        batch,
        "B",
        truth.match_id,
        [dict(case_id="failed", moment="pressure_shift", window="58:00-63:00", error="timeout")],
    )
    assert (
        main(["--runs", str(root), "--split", "dev", "--compare", "A", "B", "--resamples", "100"])
        == 0
    )
    comparison = VariantComparison.model_validate_json(capsys.readouterr().out)
    assert comparison.difference.value == pytest.approx(1 / 11)
    assert comparison.difference.n == 11
    assert comparison.failed_cases_a == 0 and comparison.failed_cases_b == 1
    assert comparison.run_a.startswith("batch-A-") and comparison.run_b.startswith("batch-B-")
    assert comparison.unverified_configuration == [
        "model_id",
        "tool_call_budget",
        "wall_time_budget_s",
    ]


def test_batch_inputs_have_stable_content_provenance(batch):
    root, suites, truth, case = batch
    first = evaluate_batch(root, suites, variant="A", resamples=100)
    repeated = evaluate_batch(root, suites, variant="A", resamples=100)
    assert first.batch_digest == repeated.batch_digest and first.run_id == repeated.run_id
    write_cases(batch, "A", truth.match_id, [case])
    changed = evaluate_batch(root, suites, variant="A", resamples=100)
    assert changed.batch_digest != first.batch_digest and changed.run_id != first.run_id


@pytest.mark.parametrize("index,count", [(0, 12), (1, 4)])
def test_a_selected_suite_ignores_other_suite_files(batch, index, count):
    root, suites, _, _ = batch
    for truth in suites[1 - index].truth.entries:
        path = root / "A" / f"{truth.match_id}.json"
        raw = json.loads(path.read_text())
        del raw["started_at_ms"]
        path.write_text(json.dumps(raw))
    run = evaluate_batch(root, [suites[index]], variant="A", resamples=100)
    assert len(run.outcomes) == count
    assert run.suites == [suites[index].truth.suite]


def test_batch_start_is_the_earliest_recorded_start_and_cannot_bypass_freeze(batch):
    root, suites, truth, _ = batch
    path = root / "A" / f"{truth.match_id}.json"
    raw = json.loads(path.read_text())
    frozen = suites[0].flags.frozen_at_ms
    raw["started_at_ms"] = frozen + 10
    path.write_text(json.dumps(raw))
    run = evaluate_batch(root, suites, variant="A", resamples=100)
    assert run.started_at_ms == frozen + 10
    raw["started_at_ms"] = frozen - 1
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="frozen before"):
        evaluate_batch(root, suites, variant="A", started_at_ms=frozen + 20, resamples=100)


def test_comparison_records_supplied_configuration_and_failed_case_usage(batch, capsys):
    root, _, truth, _ = batch
    write_cases(
        batch,
        "A",
        truth.match_id,
        [
            dict(
                case_id="failed",
                moment="pressure_shift",
                window="58:00-63:00",
                error="timeout",
                tokens=[3, 2],
            )
        ],
    )
    assert (
        main(
            [
                "--runs",
                str(root),
                "--split",
                "dev",
                "--variant",
                "A",
                "--model-id",
                "fixture",
                "--tool-call-budget",
                "16",
                "--wall-time-budget-s",
                "20",
                "--resamples",
                "100",
            ]
        )
        == 0
    )
    run = EvalRun.model_validate_json(capsys.readouterr().out)
    assert (run.input_tokens, run.output_tokens, run.failed_cases) == (3, 2, 1)
    assert run.model_id == "fixture" and run.tool_call_budget == 16 and run.wall_time_budget_s == 20
    assert (
        main(
            [
                "--runs",
                str(root),
                "--split",
                "dev",
                "--compare",
                "A",
                "B",
                "--model-id",
                "fixture",
                "--tool-call-budget",
                "16",
                "--wall-time-budget-s",
                "20",
                "--resamples",
                "100",
            ]
        )
        == 0
    )
    result = VariantComparison.model_validate_json(capsys.readouterr().out)
    assert result.unverified_configuration == [] and result.failed_cases_a == 1


@pytest.mark.parametrize("destination", [None, "--out", "--record-dir"])
@pytest.mark.parametrize("comparison", [False, True])
@pytest.mark.parametrize("explicit_start", [False, True])
def test_batch_records_require_every_source_start(
    batch, capsys, destination, comparison, explicit_start
):
    root, suites, truth, _ = batch
    start = suites[0].flags.frozen_at_ms + 10
    for path in root.glob("*/*.json"):
        raw = json.loads(path.read_text())
        raw["started_at_ms"] = start
        path.write_text(json.dumps(raw))
    # Only one missing source start must block the entire save, even in variant B
    # after variant A has already been scored. Empty-case matches still count.
    missing = root / ("B" if comparison else "A") / f"{truth.match_id}.json"
    raw = json.loads(missing.read_text())
    del raw["started_at_ms"]
    missing.write_text(json.dumps(raw))
    target = root / ("scored.json" if destination == "--out" else "records")
    args = ["--runs", str(root), "--split", "dev", "--resamples", "100"]
    args += ["--compare", "A", "B"] if comparison else ["--variant", "A"]
    if explicit_start:
        args += ["--started-at-ms", str(start + 100)]
    if destination is not None:
        args += [destination, str(target)]
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert "lacks started_at_ms" in output.err and str(missing) in output.err
    assert not output.out and not target.exists()


@pytest.mark.parametrize("null_start", [False, True])
def test_missing_batch_starts_cannot_be_replaced_by_explicit_scoring_start(batch, null_start):
    root, suites, _, _ = batch
    for path in (root / "A").glob("*.json"):
        raw = json.loads(path.read_text())
        if null_start:
            raw["started_at_ms"] = None
        else:
            del raw["started_at_ms"]
        path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="lacks started_at_ms"):
        evaluate_batch(
            root,
            suites,
            variant="A",
            started_at_ms=int(time.time() * 1000),
        )


def test_timestamped_batches_save_the_earliest_start_and_keep_freeze_checks(batch, capsys):
    root, suites, truth, _ = batch
    start = suites[0].flags.frozen_at_ms + 10
    for path in (root / "A").glob("*.json"):
        raw = json.loads(path.read_text())
        raw["started_at_ms"] = start + 100
        path.write_text(json.dumps(raw))
    earliest = root / "A" / f"{truth.match_id}.json"
    raw = json.loads(earliest.read_text())
    raw["started_at_ms"] = start
    earliest.write_text(json.dumps(raw))
    args = ["--runs", str(root), "--split", "dev", "--variant", "A"]
    target = root / "scored.json"
    assert main([*args, "--started-at-ms", str(start + 200), "--out", str(target)]) == 0
    run = EvalRun.model_validate_json(capsys.readouterr().out)
    assert run.started_at_ms == start
    assert EvalRun.model_validate_json(target.read_bytes()) == run
    # A later override cannot conceal a source match starting before the flags froze.
    raw["started_at_ms"] = suites[0].flags.frozen_at_ms - 1
    earliest.write_text(json.dumps(raw))
    bad_target = root / "bad-records"
    with pytest.raises(SystemExit):
        main([*args, "--started-at-ms", str(start + 200), "--record-dir", str(bad_target)])
    assert "frozen before" in capsys.readouterr().err and not bad_target.exists()
