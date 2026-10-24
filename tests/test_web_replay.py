"""Only committed inputs: build the Studio take afresh, then validate its web export."""

import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.llm import Replay
from contracts.card import InsightCard
from contracts.case_file import CaseFile
from contracts.cue import Cue
from contracts.event import EventAmendment
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
    assert len(hero) == 1 and hero[0]["timing"]["verified_at"]["minute"] == 68
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
