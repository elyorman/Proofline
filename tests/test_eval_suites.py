import json
import shutil
from pathlib import Path

import pytest

from contracts.eval_run import EvalRun
from eval.__main__ import main
from eval.runner import evaluate
from eval.suites import load_suite

ROOT = Path(__file__).resolve().parents[1]


def test_digest_binds_the_actual_scripts(tmp_path):
    source = ROOT / "engine/suites/planted/dev"
    target = tmp_path / "planted/dev"
    shutil.copytree(source, target)
    original = load_suite(tmp_path, "planted", "dev")
    script = next((target / "scripts").glob("*.yaml"))
    script.write_text(script.read_text() + "\n# artifact changed\n")
    assert load_suite(tmp_path, "planted", "dev").digest != original.digest


def test_refuses_flags_with_an_untrusted_stored_digest(tmp_path):
    target = tmp_path / "planted/dev"
    shutil.copytree(ROOT / "engine/suites/planted/dev", target)
    path = target / "ground_truth_flags.json"
    flags = json.loads(path.read_text())
    flags["flag_set_id"] = "forged"
    path.write_text(json.dumps(flags))
    with pytest.raises(ValueError, match="flag_set_id"):
        load_suite(tmp_path, "planted", "dev")


def test_cli_scores_the_whole_cohort_even_with_no_cards(tmp_path):
    cards = tmp_path / "cards"
    cards.mkdir()
    out = tmp_path / "run.json"
    assert (
        main(
            [
                "--cards",
                str(cards),
                "--split",
                "dev",
                "--variant",
                "B",
                "--model-id",
                "fixture-model",
                "--run-id",
                "empty",
                "--resamples",
                "100",
                "--suites-root",
                str(ROOT / "engine/suites"),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    run = EvalRun.model_validate_json(out.read_text())
    assert len(run.outcomes) == 16
    assert sum(o.correct for o in run.outcomes) == 4
    assert "cause_precision" in run.undefined_metrics
    assert all(
        o.excluded == (o.match_id in {e.match_id for e in run.flags.exclusions})
        for o in run.outcomes
    )


def test_cli_rejects_a_missing_card_directory(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--cards",
                str(tmp_path / "missing"),
                "--split",
                "dev",
                "--variant",
                "A",
                "--model-id",
                "fixture",
                "--run-id",
                "bad",
                "--out",
                str(tmp_path / "run.json"),
            ]
        )
    assert exc.value.code == 2


def test_cli_compares_saved_runs(tmp_path):
    suites = [load_suite(ROOT / "engine/suites", "planted", "dev")]
    for variant in ("A", "B"):
        run = evaluate(
            suites, [], run_id=variant, variant=variant, model_id="fixture", resamples=50
        )
        (tmp_path / f"{variant}.json").write_text(run.model_dump_json())
    out = tmp_path / "comparison.json"
    assert (
        main(
            [
                "compare",
                "--run-a",
                str(tmp_path / "A.json"),
                "--run-b",
                str(tmp_path / "B.json"),
                "--out",
                str(out),
                "--resamples",
                "50",
            ]
        )
        == 0
    )
    from contracts.eval_run import VariantComparison

    comparison = VariantComparison.model_validate_json(out.read_text())
    assert comparison.difference.value == 0
    assert comparison.difference.n == 11
    assert comparison.flag_set_id == run.flags.flag_set_id
    assert comparison.suite_digest == run.suite_digest


def test_cli_comparison_refuses_the_same_saved_run(tmp_path, capsys):
    suite = load_suite(ROOT / "engine/suites", "planted", "dev")
    run = evaluate([suite], [], run_id="same", variant="A", model_id="fixture", resamples=50)
    path = tmp_path / "run.json"
    path.write_text(run.model_dump_json())
    out = tmp_path / "comparison.json"
    with pytest.raises(SystemExit) as exc:
        main(["compare", "--run-a", str(path), "--run-b", str(path), "--out", str(out)])
    assert exc.value.code == 2
    assert "different runs" in capsys.readouterr().err
    assert not out.exists()


def test_cli_bad_yaml_is_a_usage_error(tmp_path, capsys):
    suite = tmp_path / "planted/dev"
    suite.mkdir(parents=True)
    (suite / "ground_truth.yaml").write_text("suite: [broken")
    cards = tmp_path / "cards"
    cards.mkdir()
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--cards",
                str(cards),
                "--suites-root",
                str(tmp_path),
                "--suite",
                "planted",
                "--split",
                "dev",
                "--variant",
                "A",
                "--run-id",
                "fixture",
                "--model-id",
                "fixture",
                "--out",
                str(tmp_path / "run.json"),
            ]
        )
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_suite_exclusions_must_use_the_truths_subjects(tmp_path):
    from contracts.eval_run import FlagSet

    target = tmp_path / "planted/dev"
    shutil.copytree(ROOT / "engine/suites/planted/dev", target)
    path = target / "ground_truth_flags.json"
    raw = json.loads(path.read_text())
    for observable in raw["exclusions"][0]["observables"]:
        observable["subject"] = "unrelated"
    path.write_text(FlagSet.model_validate(raw).model_dump_json())
    with pytest.raises(ValueError, match="observables"):
        load_suite(tmp_path, "planted", "dev")


def test_cli_never_overwrites_a_saved_run_with_a_comparison(tmp_path, capsys):
    suite = load_suite(ROOT / "engine/suites", "planted", "dev")
    paths = [tmp_path / "A.json", tmp_path / "B.json"]
    for variant, path in zip(("A", "B"), paths, strict=True):
        run = evaluate(
            [suite], [], run_id=variant, variant=variant, model_id="fixture", resamples=50
        )
        path.write_text(run.model_dump_json())
    original = paths[0].read_bytes()
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "compare",
                "--run-a",
                str(paths[0]),
                "--run-b",
                str(paths[1]),
                "--out",
                str(paths[0]),
                "--resamples",
                "50",
            ]
        )
    assert exc.value.code == 2
    assert "exists" in capsys.readouterr().err
    assert paths[0].read_bytes() == original
