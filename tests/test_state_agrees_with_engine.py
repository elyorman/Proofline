"""The State Builder (product) and engine/visibility.py (engine) measure the planted
observables independently; product code cannot import the engine, so this test holds the
two together on the demo match and every dev planted match."""

import math
from pathlib import Path

import pytest
import yaml

from contracts.clock import MatchClock, Window
from contracts.planted import GroundTruth
from contracts.taxonomy import BaselineScope, Metric
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from engine.visibility import change, observable, right_channel_share
from state.tools import Call, Feed, baseline, metric

ROOT = Path(__file__).resolve().parents[1] / "engine"
DEV = ROOT / "suites" / "planted" / "dev"
END = Call(tool_call_id="tc", as_of=MatchClock.parse("90+9:59"), now_ms=0)


def _state_change(feed, name, subject, window):
    during, _ = metric(feed, name, subject, window, END)
    before, _ = baseline(feed, name, subject, BaselineScope.FIRST_HALF, END)
    if during.value is None or before.baseline is None:
        return math.nan
    return during.value - before.baseline.value


def _feed(script):
    sim = MatchSim(script)
    events = sim.run()
    return Feed(meta=match_meta(sim), events=events, data_version="v1"), events


def _cases():
    truth = GroundTruth.model_validate(yaml.safe_load((DEV / "ground_truth.yaml").read_text()))
    for entry in truth.entries:
        script = load_script(DEV / "scripts" / f"{entry.match_id}.yaml")
        for o in entry.observables:
            yield script, entry.team, o.metric, o.subject, entry.window


@pytest.mark.parametrize("script,team,name,subject,window", list(_cases()))
def test_state_measures_each_planted_observable_as_the_engine_does(
    script, team, name, subject, window
):
    feed, events = _feed(script)
    other = next(t.name for t in script.teams.values() if t.name != team)
    expected = change(observable(name, subject, other if subject == team else team), events, window)
    got = _state_change(feed, name, subject, window)
    assert got == pytest.approx(expected, nan_ok=True), (script.match_id, name, subject)


def test_state_measures_the_demo_cards_as_the_engine_does():
    feed, events = _feed(load_script(ROOT / "scripts" / "planted" / "m01.yaml"))
    press = Window.model_validate("58:00-63:00")
    flank = Window.model_validate("45:00-55:00")
    hc, nv = "Harbour City", "Northvale"
    checks = [
        (Metric.PRESSURE_RATE, hc, press, observable(Metric.PRESSURE_RATE, hc, nv)),
        (Metric.LONG_BALL_SHARE, nv, press, observable(Metric.LONG_BALL_SHARE, nv, hc)),
        (Metric.CHANNEL_SHARE_RIGHT, nv, flank, right_channel_share(nv)),
        (Metric.SPRINT_COUNT, nv, press, observable(Metric.SPRINT_COUNT, nv, hc)),
    ]
    for name, subject, window, engine_measure in checks:
        expected = change(engine_measure, events, window)
        assert _state_change(feed, name, subject, window) == pytest.approx(expected), name
