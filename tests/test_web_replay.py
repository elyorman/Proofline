"""Only committed inputs: build the Studio take afresh, then validate its web export."""

import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.llm import Replay
from ambient import build_feed
from contracts.ambient import AmbientFeed
from contracts.card import InsightCard
from contracts.case_file import CaseFile
from contracts.cue import Cue
from contracts.event import Event, EventAmendment
from contracts.meta import MatchMeta
from contracts.question import Answer
from contracts.tool_result import DependencyEntry
from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim
from orchestration.studio import studio
from surfaces.web.scripts import export_web_replay as exporter
from tools_server.server import DirectorySource

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "surfaces/web/src/fixtures/ledger.json"


@pytest.fixture(scope="module")
def replayed(tmp_path_factory):
    data = tmp_path_factory.mktemp("studio-source")
    sim = MatchSim(load_script(ROOT / "engine/scripts/planted/m01.yaml"))
    write_match(sim, sim.run(), data / "m01")
    replay = Replay(ROOT / "tests/fixtures/studio/m01")
    with patch("agents.llm.FoundryModel.ask", side_effect=AssertionError("No model calls")):
        take = asyncio.run(studio(DirectorySource(data), "m01", replay, replay))
    return data / "m01", take


def stable(value):
    """Only traces and checkpoint wall times vary between recorded replays."""
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in {"trace_id", "wall_clock_ms"}}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def test_committed_ledger_validates_every_record():
    take = json.loads(LEDGER.read_text())
    for field, contract in {
        "cards": InsightCard,
        "cues": Cue,
        "case_files": CaseFile,
        "amendments": EventAmendment,
        "dependencies": DependencyEntry,
        "corrections": exporter.CorrectionRecord,
    }.items():
        assert take[field]
        for record in take[field]:
            contract.model_validate(record)
    assert take["stand_ins"] == {"cards": [], "cues": []}
    assert take["profile"]["language"] == "es"
    assert take["profile"]["favorite_club"] == "Northvale"


def test_committed_studio_equals_fresh_recorded_take(replayed):
    _, fresh = replayed
    committed = json.loads(LEDGER.read_text())
    for field in fresh:
        assert stable(committed[field]) == stable(fresh[field]), field


def test_real_correction_changes_only_the_flank_and_keeps_all_revisions():
    take = json.loads(LEDGER.read_text())
    flank = [c for c in take["cards"] if c["id"] == "ins-m01-057-shape_change"]
    hero = [c for c in take["cards"] if c["id"] == "ins-m01-063-pressure_shift"]
    assert [(c["revision"], c["status"]) for c in flank] == [(1, "shown"), (2, "withdrawn")]
    assert flank[0]["timing"]["published_at"]["minute"] == 62
    assert flank[1]["timing"]["published_at"]["minute"] == 70
    assert flank[1]["variants"]["casual"]["es"]
    assert flank[0]["evidence"] != flank[1]["evidence"]
    # The press card is shown at 68' and settled by its follow-up at 83', not by a correction.
    assert [(c["revision"], c["status"]) for c in hero] == [(1, "shown"), (2, "revised")]
    assert hero[0]["timing"]["verified_at"]["minute"] == 68
    assert hero[1]["revisions"][-1]["reason"].startswith("follow-up over 68:00-83:00")
    assert not hero[1]["revisions"][-1]["amendment_ids"]
    assert take["corrections"] == [
        dict(card_id=flank[1]["id"], decision="withdraw", revision=2, amendment_id="a1")
    ]
    cue = next(c for c in take["cues"] if c["kind"] == "withdrawal")
    assert cue["status"] == "pending" and cue["insight_revision"] == 2
    assert take["amendments"][0]["event_ids"]


def test_export_keeps_every_studio_payload_unchanged(tmp_path, replayed):
    source, take = replayed
    studio_path = tmp_path / "studio.json"
    studio_path.write_text(json.dumps(take))
    target = tmp_path / "web.json"
    exporter.export(source, "m01", tmp_path / "public", [], target, studio_path)
    exported = json.loads(target.read_text())
    assert {k: exported[k] for k in take} == take
    bad = copy.deepcopy(take)
    bad["corrections"][0]["amendment_id"] = "missing"
    with pytest.raises(ValueError, match="missing amendment"):
        exporter.validate_studio(bad, "m01")
    bad = copy.deepcopy(take)
    bad["case_files"][0]["case"]["stage"] = "open"
    with pytest.raises(ValueError):
        exporter.validate_studio(bad, "m01")


def test_export_validates_and_preserves_recorded_answers(tmp_path, replayed):
    source, _ = replayed
    answers_path = ROOT / "tests/fixtures/questions/m01/A/answers.jsonl"
    answers = [json.loads(line) for line in answers_path.read_text().splitlines()]
    assert len(answers) == 5
    for answer in answers:
        Answer.model_validate(answer)
    assert json.loads(LEDGER.read_text())["answers"] == answers
    target = tmp_path / "answers-web.json"
    exporter.export(source, "m01", tmp_path / "public", [], target, answers_path=answers_path)
    assert json.loads(target.read_text())["answers"] == answers
    bad = copy.deepcopy(answers[0])
    bad["question"]["match_id"] = "other-match"
    invalid = tmp_path / "bad-answers.jsonl"
    invalid.write_text(json.dumps(bad) + "\n")
    with pytest.raises(ValueError, match="match"):
        exporter.export(source, "m01", tmp_path / "bad", [], target, answers_path=invalid)


def _source_feed(source: Path):
    meta = MatchMeta.model_validate(json.loads((source / "meta.json").read_text()))
    lines = (source / "events.jsonl").read_text().splitlines()
    return build_feed([Event.model_validate_json(line) for line in lines], meta)


def test_committed_ambient_is_the_fresh_match_through_the_ambient_layer(replayed):
    source, _ = replayed
    committed = json.loads(LEDGER.read_text())["ambient"]
    feed = AmbientFeed.model_validate(committed)
    assert committed == _source_feed(source).model_dump(mode="json")
    assert feed.home == "Harbour City" and feed.away == "Northvale"
    # The demo match's own story is visible: Harbour City's raised press after 58'
    # tilts momentum their way and turns the game chaotic.
    at = {str(p.at): p for p in feed.control}
    assert at["63:00"].chaos > at["55:00"].chaos
    assert next(m for m in feed.momentum if m.period == 2 and m.minute == 64).value > 0
    assert {line.kind for line in feed.ticker} >= {"kick_off", "goal", "half_time", "full_time"}
    assert [line.text.es for line in feed.ticker if line.kind == "goal"][-1].startswith("Gol")


def test_export_adds_the_validated_ambient_feed(tmp_path, replayed):
    source, take = replayed
    studio_path = tmp_path / "studio.json"
    studio_path.write_text(json.dumps(take))
    target = tmp_path / "web.json"
    exporter.export(source, "m01", tmp_path / "public", [], target, studio_path)
    exported = json.loads(target.read_text())
    assert exported["ambient"] == _source_feed(source).model_dump(mode="json")
    assert exported["ambient"] == json.loads(LEDGER.read_text())["ambient"]


def test_comparison_cases_are_valid_and_preserved_by_export(tmp_path, replayed):
    source, _ = replayed
    files = json.loads(LEDGER.read_text())["comparison_case_files"]
    assert [f["variant"] for f in files] == ["A", "B"]
    # One take everywhere: the three agents' side is the Studio take's own 63' case.
    studio = json.loads(LEDGER.read_text())["case_files"]
    assert files[0] == next(
        f for f in studio if f["case"]["case_id"] == files[1]["case"]["case_id"]
    )
    a, b = [CaseFile.model_validate(f) for f in files]
    assert a.case.case_id == b.case.case_id == "case-m01-063-pressure_shift"
    assert a.case.window == b.case.window
    assert a.case.detected_at == b.case.detected_at
    assert a.agents == ["tactics", "physical", "game_state"]
    assert b.agents == ["single"]
    paths = []
    for f in files:
        path = tmp_path / f"case-{f['variant']}.json"
        path.write_text(json.dumps(f))
        paths.append(path)
    target = tmp_path / "web.json"
    exporter.export(source, "m01", tmp_path / "public", [], target, case_paths=paths)
    assert json.loads(target.read_text())["comparison_case_files"] == files
    invalid = copy.deepcopy(files[0])
    invalid["case"]["match_id"] = "other-match"
    paths[0].write_text(json.dumps(invalid))
    with pytest.raises(ValueError, match="match"):
        exporter.export(source, "m01", tmp_path / "bad", [], target, case_paths=paths)
