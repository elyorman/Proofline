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


def test_question_scoreboards_and_json_use_records_only(question_batch, monkeypatch, capsys):
    from eval.__main__ import main as eval_main
    from eval.question_compare import compare_questions
    from eval.records import save_records
    from eval.scoreboard import estimate, scoreboard

    root, _, _ = question_batch
    runs = [score_run(root, "dev", variant, resamples=100) for variant in ("A", "B", "P")]
    differences = [
        compare_questions(runs[a], runs[b], resamples=100) for a, b in ((0, 2), (0, 1), (1, 2))
    ]
    records = root / "records"
    save_records([*runs, *differences], records)

    def no_inputs(*args):
        raise AssertionError("rendering must use committed records alone")

    monkeypatch.setattr("eval.questions.keys", no_inputs)
    monkeypatch.setattr("eval.suites.load_suite", no_inputs)
    text = scoreboard(records)
    assert "| Metric (95% CI; n) | A | B | P |" in text
    assert "tuning only" in text
    assert eval_main(["scoreboard", "--records", str(records), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == 1 and len(data["records"]) == 6
    assert len(data["question_suites"]) == 1
    for row in data["question_suites"][0]["metrics"]:
        assert set(row["variants"]) == {"A", "B", "P"}
    by_id = {r["id"]: r for r in data["records"]}
    for run in runs:
        saved = by_id[run.run_id]
        assert saved["metrics"] == run.model_dump(mode="json")["metrics"]
        assert saved["citations"]["record"] == f"{run.run_id}.json"
        assert saved["citations"]["question_set_digest"] == run.question_set_digest
        assert "suite_origin" in saved["citations"]["unverified"]
        assert "flag_set_id" not in saved["citations"]["unverified"]
        for metric in run.metrics:
            assert estimate(metric) in text
    for difference in differences:
        assert by_id[difference.comparison_id]["differences"] == [
            difference.difference.model_dump(mode="json")
        ]


def test_unanswerable_is_counted_apart_from_explicit_premise_rejection(question_batch):
    from eval.records import save_records
    from eval.scoreboard import scoreboard

    root, key, _ = question_batch
    path = root / "A/answers.jsonl"
    values = [json.loads(line) for line in path.read_text().splitlines()]
    # One false premise is tested and rejected; all others have no framed premise.
    values[1].update(
        outcome="premise_false",
        premise=dict(
            metric="pressure_rate",
            subject="Harbour City",
            direction="down",
            since=key[1]
            .question.asked_at.model_copy(update={"minute": key[1].question.asked_at.minute - 5})
            .model_dump(mode="json"),
        ),
    )
    path.write_text("".join(json.dumps(v) + "\n" for v in values))
    run = score_run(root, "dev", "A")
    assert run.record_version == 2
    assert run.unanswerable == 3 and run.premise_rejected == 1
    metric = next(m for m in run.metrics if m.name == "false_premise_rejection")
    assert metric.value == 0.5 and metric.n == 2
    records = root / "new-records"
    save_records([run], records)
    text = scoreboard(records)
    assert "3 unanswerable; 1 premise rejected" in text
    encoded = json.loads(scoreboard(records, json_output=True))
    coverage = encoded["question_suites"][0]["coverage"][0]
    assert coverage["unanswerable"] == 3 and coverage["premise_rejected"] == 1
    # Old records keep their original no-cause definition and remain loadable.
    legacy = run.model_dump(mode="json")
    legacy["record_version"] = 1
    legacy["metrics"] = [
        dict(m, value=1, ci_low=0.5, ci_high=1) if m["name"] == "false_premise_rejection" else m
        for m in legacy["metrics"]
    ]
    old = QuestionRun.model_validate(legacy)
    assert next(m for m in old.metrics if m.name == "false_premise_rejection").value == 1


def test_plain_no_cause_is_distinct_from_rejecting_the_premise(question_batch):
    root, _, answers = question_batch
    answers[3].happening = True  # no cause named, but the premise was accepted
    (root / "P/answers.jsonl").write_text("".join(a.model_dump_json() + "\n" for a in answers))
    run = score_run(root, "dev", "P")
    assert run.unanswerable == 0 and run.premise_rejected == 0
    assert next(m for m in run.metrics if m.name == "false_premise_rejection").value == 0


def test_answer_join_uses_match_and_text_instead_of_question_labels(question_batch):
    from eval.question_compare import compare_questions
    from eval.questions import score

    root, key, answers = question_batch
    # Reused labels across responses cannot overwrite a different match/text pair.
    for answer in answers:
        answer.question = answer.question.model_copy(update={"question_id": "same-label"})
    (root / "P/answers.jsonl").write_text("".join(a.model_dump_json() + "\n" for a in answers))
    assert score(answers, key)["answered_right"] == "1/2"
    original = score_run(root, "dev", "P")
    assert sum(r.answered for r in original.rows) == 4
    # Renumbering the source question file preserves content identity and suite matching.
    changed = [
        k.question.model_copy(update={"question_id": f"renamed-{i}"}) for i, k in enumerate(key)
    ]
    assert question_digest(changed) == question_digest([k.question for k in key])
    (root / "questions.jsonl").write_text("".join(q.model_dump_json() + "\n" for q in changed))
    relabelled = score_run(root, "dev", "P")
    assert original.run_id != relabelled.run_id
    assert original.question_set_digest == relabelled.question_set_digest
    renamed = score_run(root, "dev", "B")
    assert original.question_set_digest == renamed.question_set_digest
    comparison = compare_questions(original, renamed)
    assert len(comparison.question_ids) == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("match_id", "unrelated"),
        ("text", "An unrelated question?"),
        ("locale", "es"),
        ("asked_at", {"period": 2, "minute": 89, "second": 0}),
    ],
)
def test_reused_question_id_never_matches_wrong_content(question_batch, field, value):
    from eval.questions import score

    root, key, answers = question_batch
    answers[0].question = type(answers[0].question).model_validate(
        answers[0].question.model_dump() | {field: value}
    )
    with pytest.raises(ValueError, match="different question set"):
        score(answers, key)
    (root / "P/answers.jsonl").write_text("".join(a.model_dump_json() + "\n" for a in answers))
    with pytest.raises(ValueError, match="different question set"):
        score_run(root, "dev", "P")


def test_duplicate_answer_text_is_rejected_even_with_a_different_id(question_batch):
    root, _, answers = question_batch
    extra = answers[0].model_copy(deep=True)
    extra.question.question_id = "another-label"
    (root / "P/answers.jsonl").write_text(
        "".join(a.model_dump_json() + "\n" for a in [*answers, extra])
    )
    with pytest.raises(ValueError, match="more than one answer"):
        score_run(root, "dev", "P")


def test_legacy_question_manifest_remains_verifiable(question_batch):
    root, key, _ = question_batch
    (root / "questions.meta.json").write_text(
        json.dumps(
            dict(
                split="dev",
                suite_digest=suite_digest("dev"),
                question_set_digest=question_digest([k.question for k in key], include_ids=True),
            )
        )
    )
    assert score_run(root, "dev", "P").suite_origin_verified


def test_a_question_on_an_unobservable_change_is_listed_but_counted_nowhere(tmp_path):
    key = keys("dev")
    (tmp_path / "questions.jsonl").write_text(
        "".join(k.question.model_dump_json() + "\n" for k in key)
    )
    (tmp_path / "P").mkdir()
    (tmp_path / "P/answers.jsonl").write_text("")
    run = score_run(tmp_path, "dev", "P", resamples=100)
    (excluded,) = [r for r in run.rows if r.excluded]
    assert excluded.match_id == "m225" and excluded.premise_true  # its tired player, unseen
    accuracy = next(m for m in run.metrics if m.name == "true_premise_accuracy")
    assert accuracy.n == sum(k.premise_true and not k.excluded for k in key) == 11
