import json
from pathlib import Path

import pytest

from contracts.eval_run import EvalRun, VariantComparison
from eval.__main__ import main
from eval.compare import compare
from eval.records import identity, load_records, save_records
from eval.runner import evaluate
from eval.scoreboard import END, FIGURE, START, render, scoreboard
from eval.suites import load_suite

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evaluated():
    suites = [load_suite(ROOT / "engine/suites", name, "dev") for name in ("planted", "decoys")]
    a = evaluate(suites, [], run_id="dev-A", variant="A", model_id="scripted", resamples=100)
    b = evaluate(suites, [], run_id="dev-B", variant="B", model_id="scripted", resamples=100)
    return suites, a, b, compare(a, b, resamples=100)


def test_records_are_immutable_and_partial_groups_are_not_written(evaluated, tmp_path):
    _, a, b, comparison = evaluated
    save_records([a], tmp_path)
    original = (tmp_path / "dev-A.json").read_bytes()
    with pytest.raises(FileExistsError):
        save_records([b, a, comparison], tmp_path)
    assert sorted(p.name for p in tmp_path.glob("*.json")) == ["dev-A.json"]
    assert (tmp_path / "dev-A.json").read_bytes() == original
    save_records([b, comparison], tmp_path)
    loaded = load_records(tmp_path)
    assert {identity(r) for r in loaded} == {a.run_id, b.run_id, comparison.comparison_id}
    with pytest.raises(ValueError, match="safe file"):
        save_records([a.model_copy(update={"run_id": "../outside"})], tmp_path)


def test_scoreboard_uses_only_records_and_reports_every_run(evaluated, tmp_path, monkeypatch):
    _, a, b, comparison = evaluated
    a.model_id = None
    # Batch records may have missing configuration; it must stay visible.
    a.batch_digest = "b" * 64
    save_records([a, b, comparison], tmp_path)

    def no_suite(*args):
        raise AssertionError("scoreboard must not read sealed truth or feeds")

    monkeypatch.setattr("eval.suites.load_suite", no_suite)
    text = scoreboard(tmp_path)
    assert text == render(load_records(tmp_path))
    for record in (a, b, comparison):
        assert identity(record) in text and record.suite_digest in text
    assert a.flags.flag_set_id in text and "tuning only" in text and "unverified" in text
    assert "All-planted recall" in text and "Cause precision" in text and "Decoy restraint" in text
    assert "A − B" in text
    assert "n=11" in text and "n=12" in text and "n=4" in text
    for excluded in a.flags.exclusions:
        assert excluded.match_id in text and excluded.cause in text and excluded.rule in text


def test_readme_check_requires_exact_generated_text(evaluated, tmp_path, capsys):
    _, a, _, _ = evaluated
    records = tmp_path / "records"
    save_records([a], records)
    text = scoreboard(records)
    readme = tmp_path / "README.md"
    readme.write_text(f"User prose\n{START}\n{text}{END}\nOther prose\n")
    assert main(["scoreboard", "--records", str(records), "--check", str(readme)]) == 0
    assert capsys.readouterr().out == text
    quoted = FIGURE.findall(text)[0]
    readme.write_text(f"Prose quotes {quoted}.\n{START}\n{text}{END}\n")
    assert scoreboard(records, readme) == text
    readme.write_text(f"Prose quotes 99.9% and [1.0, 2.0].\n{START}\n{text}{END}\n")
    with pytest.raises(ValueError, match=r"no record holds: 99\.9%, \[1\.0, 2\.0\]"):
        scoreboard(records, readme)
    readme.write_text(f"{START}\n{text}{END}\n".replace("n=11", "n=999"))
    with pytest.raises(SystemExit) as exc:
        main(["scoreboard", "--records", str(records), "--check", str(readme)])
    assert exc.value.code == 2
    readme.write_text(f"Prose\n{START}\nstale\n{END}\nTail\n")
    assert main(["scoreboard", "--records", str(records), "--write", str(readme)]) == 0
    assert readme.read_text() == f"Prose\n{START}\n{text}{END}\nTail\n"
    assert scoreboard(records, readme) == text
    readme.write_text(f"Prose with no scoreboard quotes {quoted}.\n")  # figures checked alone
    assert scoreboard(records, readme) == text
    readme.write_text("Prose with no scoreboard quotes 99.9%.\n")
    with pytest.raises(ValueError, match="no record holds"):
        scoreboard(records, readme)
    readme.write_text(f"{START}\nhalf a pair\n")
    with pytest.raises(ValueError, match="markers"):
        scoreboard(records, readme)


def test_batch_record_dir_keeps_both_runs_and_comparison(evaluated, tmp_path, capsys):
    suites, _, _, _ = evaluated
    root, records = tmp_path / "runs", tmp_path / "records"
    for variant in ("A", "B"):
        (root / variant).mkdir(parents=True)
        for suite in suites:
            for truth in suite.truth.entries:
                (root / variant / f"{truth.match_id}.json").write_text(
                    json.dumps(
                        dict(
                            match_id=truth.match_id,
                            variant=variant,
                            started_at_ms=suites[0].flags.frozen_at_ms + 1,
                            cases=[],
                        )
                    )
                )
    base = [
        "--runs",
        str(root),
        "--split",
        "dev",
        "--record-dir",
        str(records),
        "--resamples",
        "100",
    ]
    assert main([*base, "--variant", "A"]) == 0
    a = EvalRun.model_validate_json(capsys.readouterr().out)
    original = (records / f"{a.run_id}.json").read_bytes()
    assert main([*base, "--compare", "A", "B"]) == 0
    result = VariantComparison.model_validate_json(capsys.readouterr().out)
    assert len(load_records(records)) == 3
    assert result.run_a == a.run_id and (records / f"{a.run_id}.json").read_bytes() == original
    with pytest.raises(SystemExit):
        main([*base, "--variant", "A"])


def test_empty_and_invalid_record_directories(tmp_path):
    assert "No evaluation records" in scoreboard(tmp_path)
    (tmp_path / "bad.json").write_text("[]")
    with pytest.raises(ValueError, match="bad.json"):
        scoreboard(tmp_path)


def test_json_contains_detector_metrics_exclusions_differences_and_citations(evaluated, tmp_path):
    _, a, b, comparison = evaluated
    save_records([a, b, comparison], tmp_path)
    data = json.loads(scoreboard(tmp_path, json_output=True))
    by_id = {r["id"]: r for r in data["records"]}
    assert by_id[a.run_id]["metrics"] == a.model_dump(mode="json")["metrics"]
    assert by_id[a.run_id]["exclusions"] == a.flags.model_dump(mode="json")["exclusions"]
    assert by_id[a.run_id]["citations"]["flag_set_id"] == a.flags.flag_set_id
    assert by_id[comparison.comparison_id]["differences"] == [
        comparison.difference.model_dump(mode="json")
    ]
