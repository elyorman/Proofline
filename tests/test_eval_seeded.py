import asyncio
import json
import math
from pathlib import Path

import pytest

from agents.llm import Recording, Replay, Usage
from agents.verifier.checks import Record
from agents.verifier.semantic import SemanticReport, SentenceCheck
from contracts.eval_run import SeededRun, SeedType, Split, Variant
from detector.cusum import detect
from engine.io import match_meta, write_match
from engine.script import load_script
from engine.sim import MatchSim
from eval.batch import BatchCase
from eval.records import load_records, save_records
from eval.seeded import benchmark_card, replay_case, run_seeded, summarize
from eval.seeds import mutations, next_display
from orchestration.case import run_case
from state.tools import Feed

ROOT = Path(__file__).resolve().parents[1]
EXCHANGES = ROOT / "tests/fixtures/cases/m01-063-A"


class AcceptAll:
    """A deliberately permissive scripted semantic model makes missed types visible."""

    def __init__(self):
        self.calls = 0

    async def ask(self, role, instructions, prompt, schema):
        self.calls += 1
        assert role == "verifier" and schema is SemanticReport
        return SemanticReport(
            sentences=[
                SentenceCheck(
                    sentence=s, entailed=True, overstated=False, reason="scripted control"
                )
                for s in json.loads(prompt)["sentences"]
            ]
        ), Usage(3, 2)


@pytest.fixture(scope="module")
def real_case():
    sim = MatchSim(load_script(ROOT / "engine/scripts/planted/m01.yaml"))
    events = sim.run()
    feed = Feed(meta=match_meta(sim), events=events, data_version="feed-1")
    case = next(c for c in detect(feed.meta, events) if c.window.end.minute == 63)
    replay = Replay(EXCHANGES)
    outcome = asyncio.run(run_case(Variant.A_PROOFLINE, replay, replay, case, feed))
    assert outcome.verdict.card.status == "verified"
    record = Record.of(outcome.finding.tools.log, outcome.finding.evidence)
    return sim, events, feed, case, outcome, record


def differences(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [p for k in a for p in differences(a[k], b[k], f"{path}.{k}".strip("."))]
    if isinstance(a, list) and isinstance(b, list):
        return [
            p
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for p in differences(x, y, f"{path}[{i}]")
        ]
    return [] if a == b else [path]


def test_each_seed_changes_only_its_declared_field(real_case):
    _, _, feed, _, outcome, _ = real_case
    card = outcome.verdict.card
    original = card.model_dump(mode="json")
    seeded = mutations(card, feed)
    assert {m.kind for m in seeded} == set(SeedType)
    for mutation in seeded:
        if mutation.card is None:
            assert mutation.skip_reason
            continue
        assert differences(original, mutation.card.model_dump(mode="json")) == [mutation.field]
        assert mutation.before != mutation.after
    assert card.model_dump(mode="json") == original
    by_type = {m.kind: m for m in seeded}
    assert by_type[SeedType.CLAIM_DIRECTION].after != card.claim
    assert by_type[SeedType.WRONG_TEAM].after.endswith("Northvale.")
    certainty = by_type[SeedType.OVERCERTAINTY]
    if card.verification.support_level == "strong":
        assert certainty.card is None and "strong support" in certainty.skip_reason
    else:
        assert "definitely proves" in certainty.after


def test_certainty_seed_applies_to_measured_support_without_other_changes(real_case):
    from contracts.taxonomy import LanguageLevel, SupportLevel

    _, _, feed, _, outcome, _ = real_case
    card = outcome.verdict.card.model_copy(deep=True)
    card.verification.support_level = SupportLevel.MODERATE
    card.verification.language_level = LanguageLevel.MEASURED
    seed = next(m for m in mutations(card, feed) if m.kind == SeedType.OVERCERTAINTY)
    assert "definitely proves" in seed.after
    assert differences(card.model_dump(mode="json"), seed.card.model_dump(mode="json")) == ["claim"]


@pytest.mark.parametrize("value", [0.833333, 0.005, 1.234, -1.234, -0.001, 100.0])
def test_numeric_mutation_uses_the_first_float_that_changes_two_decimal_display(value):
    changed = next_display(value)
    assert changed > value and f"{changed:.2f}" != f"{value:.2f}"
    assert f"{math.nextafter(changed, -math.inf):.2f}" == f"{value:.2f}"


def test_controls_and_every_seed_are_verified_and_reproduce_from_recording(real_case, tmp_path):
    _, _, feed, _, outcome, record = real_case
    model = AcceptAll()
    first, usage = asyncio.run(
        benchmark_card(
            Recording(model, tmp_path), outcome.verdict.card, record, feed, outcome.finding.exams
        )
    )
    second, replay_usage = asyncio.run(
        benchmark_card(Replay(tmp_path), outcome.verdict.card, record, feed, outcome.finding.exams)
    )
    assert first == second and usage == replay_usage
    assert first.control.status == "passed"
    by_type = {t.kind: t for t in first.trials}
    assert by_type[SeedType.EVIDENCE_VALUE].verification.recompute == "mismatch"
    assert by_type[SeedType.BASELINE_VALUE].verification.recompute == "mismatch"
    assert by_type[SeedType.UNSUPPORTED_NUMBER].verification.number_check == "failed"
    assert by_type[SeedType.PRIMARY_DIRECTION].verification.contradiction_check == "failed"
    assert not by_type[SeedType.WRONG_TEAM].caught
    assert not by_type[SeedType.CLAIM_DIRECTION].caught
    assert not by_type[SeedType.UNNAMED_CAUSE].caught
    types, catch, control = summarize([first], seed=7, resamples=100)
    assert catch.value == sum(t.caught for t in first.trials if t.applied) / sum(
        t.applied for t in first.trials
    )
    assert catch.ci_low <= catch.value <= catch.ci_high
    assert control.value == 0 and len(types) == len(SeedType)
    # Every seed belonging to one card stays in the same bootstrap cluster.
    missed = first.model_copy(deep=True)
    for trial in missed.trials:
        if trial.applied:
            trial.verification = first.control
            trial.caught = False
    _, clustered, _ = summarize([first, missed], seed=7, resamples=500)
    assert clustered.value == catch.value / 2
    assert clustered.n == 2 * catch.n and clustered.ci_low == 0


def test_false_rejections_are_reported_even_when_every_seed_is_caught(real_case):
    class RejectAll(AcceptAll):
        async def ask(self, *args):
            report, usage = await super().ask(*args)
            for sentence in report.sentences:
                sentence.entailed = False
                sentence.reason = "scripted false rejection"
            return report, usage

    _, _, feed, _, outcome, record = real_case
    result, _ = asyncio.run(
        benchmark_card(RejectAll(), outcome.verdict.card, record, feed, outcome.finding.exams)
    )
    _, catch, controls = summarize([result], seed=7, resamples=100)
    assert catch.value == 1 and controls.value == 1
    assert result.control.semantic_check == "failed"


def envelope(case, card):
    return BatchCase(
        case_id=case.case_id,
        moment=case.moment_type,
        window=case.window,
        outcome=card.case_outcome,
        card=card,
        published=True,
        tool_calls=9,
        tokens=(20, 10),
        recovered=False,
        hypotheses=4,
        counter_tests=3,
    )


def test_reconstruction_ignores_only_trace_id(real_case, monkeypatch):
    _, _, feed, case, outcome, _ = real_case
    expected = envelope(case, outcome.verdict.card.model_copy(deep=True))
    expected.card.provenance.trace_id = "different"

    async def same(*args):
        return outcome

    monkeypatch.setattr("eval.seeded.run_case", same)
    assert (
        asyncio.run(replay_case(Variant.A_PROOFLINE, expected, case.match_id, feed, EXCHANGES))
        is outcome
    )
    expected.card.evidence[0].tool_call_id = "different-tool-reference"
    with pytest.raises(ValueError, match="beyond trace_id"):
        asyncio.run(replay_case(Variant.A_PROOFLINE, expected, case.match_id, feed, EXCHANGES))


def test_seeded_runner_saves_complete_replayable_results(real_case, tmp_path, monkeypatch):
    sim, events, _, case, outcome, _ = real_case
    data, runs = tmp_path / "data", tmp_path / "runs"
    write_match(sim, events, data / case.match_id)
    (runs / "A").mkdir(parents=True)
    (runs / "A" / f"{case.match_id}.json").write_text(
        json.dumps(
            dict(
                match_id=case.match_id,
                variant="A",
                cases=[envelope(case, outcome.verdict.card).model_dump(mode="json")],
            )
        )
    )

    async def stable(*args):
        return outcome

    # The fixture supplies the real case. Stable tool IDs are a producer prerequisite;
    # strict mismatch rejection itself is tested above rather than bypassed in production.
    monkeypatch.setattr("eval.seeded.run_case", stable)
    recorded = tmp_path / "verifier"
    run = asyncio.run(
        run_seeded(
            runs,
            Variant.A_PROOFLINE,
            data,
            EXCHANGES,
            Recording(AcceptAll(), recorded),
            recorded,
            split=Split.DEV,
            model_id="scripted",
            limit=1,
            concurrency=2,
            resamples=100,
        )
    )
    replayed = asyncio.run(
        run_seeded(
            runs,
            Variant.A_PROOFLINE,
            data,
            EXCHANGES,
            Replay(recorded),
            recorded,
            split=Split.DEV,
            model_id="scripted",
            limit=1,
            resamples=100,
        )
    )
    assert run.cards == replayed.cards and run.types == replayed.types
    assert run.run_id == replayed.run_id and run.catch_rate == replayed.catch_rate
    save_records([run], tmp_path / "records")
    assert load_records(tmp_path / "records") == [run]
    assert SeededRun.model_validate_json(run.model_dump_json()) == run
    from eval.scoreboard import scoreboard

    rendered = scoreboard(tmp_path / "records")
    assert "missed" in rendered and "Controls rejected" in rendered
    for kind in SeedType:
        assert kind.value in rendered


def test_seeded_cli_records_and_replays_without_live_models(
    real_case, tmp_path, monkeypatch, capsys
):
    from eval.__main__ import main

    sim, events, _, case, outcome, _ = real_case
    data, runs = tmp_path / "data", tmp_path / "runs"
    write_match(sim, events, data / case.match_id)
    (runs / "A").mkdir(parents=True)
    (runs / "A" / f"{case.match_id}.json").write_text(
        json.dumps(
            dict(
                match_id=case.match_id,
                variant="A",
                cases=[envelope(case, outcome.verdict.card).model_dump(mode="json")],
            )
        )
    )

    async def stable(*args):
        print("backend progress should be on stderr")
        return outcome

    def scripted_models(record=None, replay=None):
        verifier = Replay(replay) if replay is not None else Recording(AcceptAll(), record)
        return None, verifier

    monkeypatch.setattr("eval.seeded.run_case", stable)
    monkeypatch.setattr("orchestration.case.models", scripted_models)
    verifier = tmp_path / "verifier"
    records = tmp_path / "records"
    args = [
        "seeded",
        "--runs",
        str(runs),
        "--split",
        "dev",
        "--variant",
        "A",
        "--data",
        str(data),
        "--exchanges",
        str(EXCHANGES),
        "--record-dir",
        str(records),
        "--model-id",
        "scripted",
        "--resamples",
        "100",
        "--limit",
        "1",
    ]
    assert main([*args, "--record", str(verifier), "--run-id", "scripted-live-path"]) == 0
    output = capsys.readouterr()
    first = SeededRun.model_validate_json(output.out)
    assert "backend progress" in output.err
    assert main([*args, "--replay", str(verifier), "--run-id", "scripted-replay-path"]) == 0
    second = SeededRun.model_validate_json(capsys.readouterr().out)
    assert first.cards == second.cards and first.catch_rate == second.catch_rate
    assert len(load_records(records)) == 2


def test_seeded_runner_spends_nothing_when_source_card_does_not_match(
    real_case, tmp_path, monkeypatch
):
    sim, events, _, case, outcome, _ = real_case
    data, runs = tmp_path / "data", tmp_path / "runs"
    write_match(sim, events, data / case.match_id)
    (runs / "A").mkdir(parents=True)
    card = outcome.verdict.card.model_copy(deep=True)
    card.claim += " changed"
    (runs / "A" / f"{case.match_id}.json").write_text(
        json.dumps(
            dict(
                match_id=case.match_id,
                variant="A",
                cases=[envelope(case, card).model_dump(mode="json")],
            )
        )
    )

    async def same(*args):
        return outcome

    monkeypatch.setattr("eval.seeded.run_case", same)
    model = AcceptAll()
    with pytest.raises(ValueError, match="beyond trace_id"):
        asyncio.run(
            run_seeded(
                runs,
                Variant.A_PROOFLINE,
                data,
                EXCHANGES,
                model,
                tmp_path / "verifier",
                split=Split.DEV,
                resamples=100,
            )
        )
    assert model.calls == 0
