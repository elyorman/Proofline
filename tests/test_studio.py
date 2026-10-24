"""Studio mode on the demo match, replayed from a recorded run: every case through the Why
Engine and the Verifier, the 68' amendment through the Correction Watcher, and the Director's
schedule, with no model call. The recorded run's verdicts are its own; this checks the run."""

import asyncio
import json
from pathlib import Path

import pytest

from agents.llm import Replay
from contracts.card import InsightCard
from contracts.case_file import CaseFile
from contracts.cue import Cue
from contracts.event import EventAmendment
from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim
from orchestration.studio import studio
from tools_server.server import DirectorySource

ROOT = Path(__file__).resolve().parents[1]
RECORDED = ROOT / "tests" / "fixtures" / "studio" / "m01"


@pytest.fixture(scope="module")
def ledger(tmp_path_factory):
    root = tmp_path_factory.mktemp("matches")
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    write_match(sim, sim.run(), root / "m01")
    replay = Replay(RECORDED)
    return asyncio.run(studio(DirectorySource(root), "m01", replay, replay))


def test_every_case_of_the_match_is_filed_and_every_card_scheduled(ledger):
    files = [CaseFile.model_validate(f) for f in ledger["case_files"]]
    assert [f.case.case_id for f in files] == [
        "case-m01-051-pressure_shift",
        "case-m01-057-pressure_shift",
        "case-m01-057-shape_change",
        "case-m01-063-pressure_shift",
        "case-m01-078-pressure_shift",
    ]
    cards = [InsightCard.model_validate(c) for c in ledger["cards"]]
    filed = {f.case.card_id for f in files} - {None}
    assert filed == {c.id for c in cards if c.lane == "full"}
    assert sum(c.lane == "fast" for c in cards) == 5  # the goals
    for c in cards:  # a correction to a card the fan never saw stays on the console
        if c.timing.published_at is not None:
            assert c.status in ("shown", "revised", "withdrawn") or c.lane == "fast"
        if c.status == "shown":
            assert c.timing.published_at is not None
    assert all(Cue.model_validate(c) for c in ledger["cues"])
    (a1,) = [EventAmendment.model_validate(a) for a in ledger["amendments"]]
    assert a1.amendment_id == "a1" and len(a1.event_ids) == 81
    # The recorded take's correction beat: the flank card withdrawn, the press card left alone.
    assert [(c["card_id"], c["decision"]) for c in ledger["corrections"]] == [
        ("ins-m01-057-shape_change", "withdraw")
    ]


def test_a_studio_replay_is_the_same_ledger_every_time(ledger, tmp_path):
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    write_match(sim, sim.run(), tmp_path / "m01")
    replay = Replay(RECORDED)
    again = asyncio.run(studio(DirectorySource(tmp_path), "m01", replay, replay))

    def stable(x):  # trace ids and checkpoint wall clocks belong to the run, not the match
        if isinstance(x, dict):
            return {k: stable(v) for k, v in x.items() if k not in ("trace_id", "wall_clock_ms")}
        return [stable(v) for v in x] if isinstance(x, list) else x

    assert json.dumps(stable(again), sort_keys=True) == json.dumps(stable(ledger), sort_keys=True)
