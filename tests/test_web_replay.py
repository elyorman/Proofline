"""Validate the committed web ledger against contracts and a fresh backend replay."""

import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.llm import Replay
from contracts.card import InsightCard
from contracts.cue import Cue
from contracts.eval_run import Variant
from contracts.event import Event
from detector.cusum import detect
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from orchestration.case import run_case
from state.tools import Feed
from surfaces.web.scripts import export_web_replay as exporter

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "surfaces/web/src/fixtures/ledger.json"


@pytest.fixture(scope="module")
def replayed():
    sim = MatchSim(load_script(ROOT / "engine/scripts/planted/m01.yaml"))
    events = sim.run()
    feed = Feed(meta=match_meta(sim), events=events, data_version="feed-1")
    case = next(c for c in detect(feed.meta, events) if c.window.end.minute == 63)
    replay = Replay(ROOT / "tests/fixtures/cases/m01-063-A")
    # Tool-call ids name their question, so a replay reproduces the card but its trace id.
    with patch("agents.llm.FoundryModel.ask", side_effect=AssertionError("No model calls")):
        outcome = asyncio.run(run_case(Variant.A_PROOFLINE, replay, replay, case, feed))
    return feed, outcome.verdict.card


def test_committed_ledger_validates_every_card_and_cue():
    ledger = json.loads(LEDGER.read_text())
    cards = [InsightCard.model_validate(raw) for raw in ledger["cards"]]
    cues = [Cue.model_validate(raw) for raw in ledger["cues"]]
    assert len({(c.id, c.revision) for c in cards}) == len(cards)
    assert len({c.cue_id for c in cues}) == len(cues)
    assert "ins-m01-063-01" not in {c.id for c in cards}
    for card in cards:
        if card.provenance.trace_id.startswith("stand-in-"):
            assert f"{card.id}@{card.revision}" in ledger["stand_ins"]["cards"]
    assert set(ledger["stand_ins"]["cues"]) == {c.cue_id for c in cues}
    original, withdrawal = [c for c in cards if c.id == "ins-m01-055-01"]
    assert original.status == "shown" and withdrawal.status == "withdrawn"
    assert withdrawal.revision == 2 and withdrawal.verification.status == "rejected"


def test_committed_pressure_card_equals_fresh_backend_replay_except_trace(replayed):
    _, fresh = replayed
    ledger = json.loads(LEDGER.read_text())
    committed = next(c for c in ledger["cards"] if c["id"] == fresh.id)
    actual = copy.deepcopy(committed)
    expected = fresh.model_dump(mode="json")
    assert actual["provenance"].pop("trace_id")
    assert expected["provenance"].pop("trace_id")
    assert actual == expected
    assert fresh.status == "verified" and fresh.verification.support_level == "strong"
    assert fresh.timing.published_at is None
    assert f"{fresh.id}@{fresh.revision}" not in ledger["stand_ins"]["cards"]


def test_committed_press_cue_uses_first_dead_ball_and_real_evidence(replayed):
    feed, card = replayed
    ledger = json.loads(LEDGER.read_text())
    cue = Cue.model_validate(next(c for c in ledger["cues"] if c["insight_id"] == card.id))
    first = next(
        e
        for e in feed.events
        if e.type in exporter.DEAD_BALL and e.clock > exporter.display_time(card)
    )
    assert cue.show_at.not_before == first.clock
    assert cue.fields["team"] == card.subject.team
    assert cue.fields["before"] == card.evidence[0].baseline.value
    assert cue.fields["after"] == card.evidence[0].value
    assert cue.fields["headline"] == card.variants["casual"]["en"]
    assert (
        cue.show_at.not_before.seconds_in_period - card.timing.detected_at.seconds_in_period == 29
    )


@pytest.mark.parametrize("legacy", [False, True])
def test_export_honors_match_and_output_args_with_no_goals(tmp_path, replayed, legacy):
    feed, _ = replayed
    source = tmp_path / "source"
    source.mkdir()
    meta = feed.meta.model_dump(mode="json") | {"match_id": "m17"}
    if legacy:
        meta.update(seed=1234, score={"home": 99}, period_lengths_s={"1": 9999})
    (source / "meta.json").write_text(json.dumps(meta))
    events = [e.model_copy(update={"match_id": "m17"}) for e in feed.events if e.type != "goal"]
    (source / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in events))
    out, ledger_path = tmp_path / "public/custom", tmp_path / "custom-ledger.json"
    exporter.export(source, "m17", out, [], ledger_path)
    exported = json.loads((out / "meta.json").read_text())
    assert set(exported) == {"match_id", "teams"} and exported["match_id"] == "m17"
    assert all(
        Event.model_validate_json(line).match_id == "m17"
        for line in (out / "events.jsonl").read_text().splitlines()
    )
    ledger = json.loads(ledger_path.read_text())
    assert len(ledger["cards"]) == 2  # No goal stand-in is invented for a scoreless match.
    assert all(InsightCard.model_validate(c).match_id == "m17" for c in ledger["cards"])
    assert all(Cue.model_validate(c).match_id == "m17" for c in ledger["cues"])


def test_export_preserves_the_input_card_payload_and_rejects_wrong_match(tmp_path, replayed):
    feed, card = replayed
    source = tmp_path / "source"
    source.mkdir()
    (source / "meta.json").write_text(feed.meta.model_dump_json())
    (source / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in feed.events))
    card_path = tmp_path / "card.json"
    card_path.write_text(card.model_dump_json())
    out, target = tmp_path / "out", tmp_path / "ledger.json"
    exporter.export(source, "m01", out, [card_path], target)
    stored = next(c for c in json.loads(target.read_text())["cards"] if c["id"] == card.id)
    assert stored == json.loads(card_path.read_text())
    with pytest.raises(ValueError, match="different match"):
        exporter.export(source, "other", out, [card_path], target)
    with pytest.raises(ValueError, match="duplicate card"):
        exporter.export(source, "m01", out, [card_path, card_path], target)
    card_path.write_text(card.model_copy(update={"match_id": "other"}).model_dump_json())
    with pytest.raises(ValueError, match="card belongs"):
        exporter.export(source, "m01", out, [card_path], target)


def test_press_cue_waits_for_substitution_and_is_omitted_without_dead_ball(replayed):
    _, card = replayed

    def event(kind, seconds):
        return Event(
            event_id=str(seconds),
            match_id=card.match_id,
            clock=exporter.later(exporter.display_time(card), seconds),
            wall_clock_ms=0,
            type=kind,
            team=card.subject.team,
        )

    events = [event("card", 1), event("substitution", 3), event("foul", 4)]
    (cue,) = exporter.stand_in_cues([card], events)
    assert cue.show_at.not_before == events[1].clock
    assert exporter.stand_in_cues([card], events[:1]) == []
    proposed = InsightCard.model_validate(card.model_dump() | {"status": "proposed"})
    assert exporter.stand_in_cues([proposed], events) == []
