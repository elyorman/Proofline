import json
from pathlib import Path

import pytest

from contracts.eval_run import QUESTION_METRICS, QuestionRun
from contracts.question import Answer, PlainAnswer
from eval.questions import keys, main, question_digest, question_samples, score_run, suite_digest
from eval.records import load_records

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def question_batch(tmp_path):
    key = keys("dev")[:4]  # two complete match clusters, from committed scripts/truth
    (tmp_path / "questions.jsonl").write_text(
        "".join(k.question.model_dump_json() + "\n" for k in key)
    )
    answers = []
    for i, item in enumerate(key):
        correct = i == 0
        claimed = i != 3
        answers.append(
            PlainAnswer(
                question=item.question,
                happening=claimed,
                cause=item.cause if correct else "tactical.block_deeper" if claimed else None,
                team=item.team if correct else "Harbour City" if claimed else None,
                text="A scripted answer.",
                tool_calls=3,
                input_tokens=10,
                output_tokens=3,
            )
        )
    for variant in ("A", "B", "P"):
        (tmp_path / variant).mkdir()
        values = (
            answers
            if variant == "P"
            else [
                Answer(
                    question=k.question,
                    variant=variant,
                    outcome="unanswerable",
                    reason="scripted",
                    text={"en": "No premise.", "es": "Sin premisa."},
                    input_tokens=4,
                    output_tokens=2,
                )
                for k in key
            ]
        )
        (tmp_path / variant / "answers.jsonl").write_text(
            "".join(a.model_dump_json() + "\n" for a in values)
        )
    return tmp_path, key, answers


def test_question_run_records_metrics_match_clusters_and_tokens(question_batch):
    root, _, _ = question_batch
    run = score_run(
        root, "dev", "P", model_id="scripted", tool_call_budget=16, seed=7, resamples=300
    )
    metrics = {m.name: m for m in run.metrics}
    assert set(metrics) == set(QUESTION_METRICS)
    assert metrics["true_premise_accuracy"].value == 0.5
    assert metrics["false_premise_rejection"].value == 0.5
    assert metrics["false_claims_per_question"].value == 0.5
    assert metrics["claim_precision"].value == pytest.approx(1 / 3)
    assert (run.input_tokens, run.output_tokens) == (40, 12)
    assert len(question_samples(run.rows, "false_claims_per_question")) == 2
    assert all(d == 2 for _, d in question_samples(run.rows, "false_claims_per_question"))
    for metric in run.metrics:
        assert metric.ci_low <= metric.value <= metric.ci_high
    repeated = score_run(
        root, "dev", "P", model_id="scripted", tool_call_budget=16, seed=7, resamples=300
    )
    assert run.metrics == repeated.metrics and run.run_id == repeated.run_id
    assert QuestionRun.model_validate_json(run.model_dump_json()) == run


def test_question_cli_saves_an_immutable_record(question_batch, capsys):
    root, _, _ = question_batch
    out, records = root / "scored.json", root / "records"
    args = [
        "score",
        "--runs",
        str(root),
        "--split",
        "dev",
        "--variant",
        "P",
        "--out",
        str(out),
        "--record-dir",
        str(records),
        "--resamples",
        "100",
    ]
    assert main(args) == 0
    run = QuestionRun.model_validate_json(capsys.readouterr().out)
    assert QuestionRun.model_validate_json(out.read_bytes()) == run
    assert load_records(records) == [run]
    original = out.read_bytes()
    with pytest.raises(SystemExit):
        main(args)
    assert out.read_bytes() == original


def test_missing_and_failed_questions_stay_in_denominators(question_batch):
    root, key, answers = question_batch
    path = root / "P/answers.jsonl"
    values = [
        answers[0].model_dump(mode="json"),
        dict(question=key[1].question.model_dump(mode="json"), error="model had no answer"),
        answers[3].model_dump(mode="json"),
    ]
    path.write_text("".join(json.dumps(v) + "\n" for v in values))
    run = score_run(root, "dev", "P", resamples=100)
    assert len(run.rows) == 4 and sum(r.answered for r in run.rows) == 2
    assert sum(r.error is not None for r in run.rows) == 1
    assert sum(r.outcome == "missing" for r in run.rows) == 1
    assert (run.input_tokens, run.output_tokens) == (20, 6)
    assert not run.token_usage_complete


@pytest.mark.parametrize("change", ["duplicate", "question", "unverified_card"])
def test_invalid_question_answers_are_refused(question_batch, change):
    root, key, answers = question_batch
    if change == "unverified_card":
        recorded = ROOT / "tests/fixtures/questions/m01/A/answers.jsonl"
        raw = next(
            json.loads(line)
            for line in recorded.read_text().splitlines()
            if json.loads(line).get("card")
        )
        raw["question"] = key[0].question.model_dump(mode="json")
        raw["card"]["match_id"] = key[0].question.match_id
        raw["card"]["status"] = "proposed"
        (root / "A/answers.jsonl").write_text(json.dumps(raw) + "\n")
        variant = "A"
    else:
        raw = [a.model_dump(mode="json") for a in answers]
        if change == "duplicate":
            raw.append(raw[0])
        else:
            raw[0]["question"]["text"] = "An unrelated question?"
        (root / "P/answers.jsonl").write_text("".join(json.dumps(a) + "\n" for a in raw))
        variant = "P"
    with pytest.raises(ValueError):
        score_run(root, "dev", variant, resamples=100)


def test_question_generation_manifest_binds_the_suite(tmp_path):
    path = tmp_path / "questions.jsonl"
    assert main(["make", "--split", "dev", "--out", str(path)]) == 0
    questions = [k.question for k in keys("dev")]
    metadata = json.loads(path.with_suffix(".meta.json").read_text())
    assert metadata["question_set_digest"] == question_digest(questions)
    assert metadata["suite_digest"] == suite_digest("dev")
    (tmp_path / "P").mkdir()
    (tmp_path / "P/answers.jsonl").write_text("")
    assert score_run(tmp_path, "dev", "P", resamples=100).suite_origin_verified
    metadata["suite_digest"] = "0" * 64
    path.with_suffix(".meta.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="manifest"):
        score_run(tmp_path, "dev", "P", resamples=100)


def test_verified_question_cards_match_by_primary_class_and_team(question_batch):
    root, key, _ = question_batch
    path = ROOT / "tests/fixtures/questions/m01/A/answers.jsonl"
    raw = next(
        json.loads(line) for line in path.read_text().splitlines() if json.loads(line).get("card")
    )
    raw["question"] = key[0].question.model_dump(mode="json")
    raw["card"]["match_id"] = key[0].question.match_id
    raw["card"]["subject"]["team"] = key[0].team
    primary = next(p for p in raw["card"]["propositions"] if p.get("role") == "primary")
    primary["cause"] = key[0].cause
    target = root / "A/answers.jsonl"
    target.write_text(json.dumps(raw) + "\n")
    assert score_run(root, "dev", "A", resamples=100).rows[0].right
    raw["card"]["subject"]["team"] = "Unrelated Town"
    target.write_text(json.dumps(raw) + "\n")
    row = score_run(root, "dev", "A", resamples=100).rows[0]
    assert row.claimed and row.false_claim and not row.right


@pytest.mark.parametrize(
    "first,second,expected", [("A", "P", -0.5), ("A", "B", 0), ("B", "P", -0.5)]
)
def test_paired_question_differences(question_batch, first, second, expected):
    from eval.question_compare import compare_questions

    root, _, _ = question_batch
    a, b = (score_run(root, "dev", v, resamples=100) for v in (first, second))
    comparison = compare_questions(a, b, seed=7, resamples=300)
    assert comparison.difference.value == expected
    assert comparison.difference.ci_low <= expected <= comparison.difference.ci_high
    assert len(comparison.question_ids) == 4 and len(comparison.match_ids) == 2
    assert comparison == compare_questions(a, b, seed=7, resamples=300)
    with pytest.raises(ValueError, match="question_set_digest"):
        compare_questions(a, b.model_copy(update={"question_set_digest": "0" * 64}))


def test_question_comparison_uses_only_mutually_answered_questions(question_batch):
    from eval.question_compare import compare_questions

    root, key, _ = question_batch
    a_path = root / "A/answers.jsonl"
    values = [json.loads(line) for line in a_path.read_text().splitlines()]
    values[0] = dict(question=key[0].question.model_dump(mode="json"), error="no answer")
    a_path.write_text("".join(json.dumps(v) + "\n" for v in values))
    a, p = (score_run(root, "dev", v, resamples=100) for v in ("A", "P"))
    result = compare_questions(a, p, resamples=100)
    assert result.unpaired_question_ids == [key[0].question.question_id]
    assert len(result.question_ids) == 3 and result.difference.n == 1
    assert result.difference.value == 0


def test_question_comparison_cli_retains_source_records(question_batch, capsys):
    from contracts.eval_run import VariantComparison

    root, _, _ = question_batch
    records = root / "records"
    args = [
        "score",
        "--runs",
        str(root),
        "--split",
        "dev",
        "--compare",
        "A",
        "P",
        "--record-dir",
        str(records),
        "--resamples",
        "100",
    ]
    assert main(args) == 0
    result = VariantComparison.model_validate_json(capsys.readouterr().out)
    assert result.comparison_type == "questions" and result.variant_b == "P"
    assert len(load_records(records)) == 3
