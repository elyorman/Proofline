"""Normal variation and confirmation: deterministic, from the committed season and the demo
match; nothing here calls a model."""

import asyncio
from pathlib import Path

import pytest

from agents.confirm import confirm, extended
from agents.single import case_tools
from contracts.clock import Window
from contracts.taxonomy import Metric
from detector.cusum import detect
from engine.io import match_meta
from engine.script import load_script
from engine.season import season
from engine.sim import MatchSim
from state import natural
from state.tools import Feed

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def m01():
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    events = sim.run()
    return Feed(meta=match_meta(sim), events=events, data_version="feed-1")


def test_a_window_reads_against_the_season_spread_nearest_its_length_and_minute():
    assert natural.bucket(Window.model_validate("58:00-63:00")) == (5, 65)
    assert natural.bucket(Window.model_validate("47:00-62:00")) == (15, 60)
    assert natural.bucket(Window.model_validate("10:00-20:00")) is None  # first half
    late = natural.spread(Metric.SPRINT_COUNT, "team", Window.model_validate("75:00-85:00"))
    early = natural.spread(Metric.SPRINT_COUNT, "team", Window.model_validate("50:00-60:00"))
    assert late.mean < early.mean < 0  # sprints fall through every second half


def test_a_late_fall_in_sprints_is_ordinary_play_and_a_raised_press_is_not(m01):
    window = Window.model_validate("80:00-90:00")
    # A 30% fall at 80-90' is about what ordinary play shows then.
    z, _ = natural.sigmas(m01.meta, Metric.SPRINT_COUNT, "Northvale", window, 2.8, 4.0)
    assert abs(z) < 1
    press = Window.model_validate("58:00-63:00")
    z, normal = natural.sigmas(m01.meta, Metric.PRESSURE_RATE, "Harbour City", press, 0.83, 0.32)
    assert z > 3 and normal.n > 100


def test_a_change_that_lasts_is_confirmed_and_one_that_fades_is_not(m01):
    def held(minute):
        case = next(c for c in detect(m01.meta, m01.events) if c.window.end.minute == minute)
        case = extended(case)
        tools, _ = case_tools(case, m01)
        return [p.holds for p in asyncio.run(confirm(tools, case, m01.meta))]

    assert held(63) == [True]  # Harbour City kept pressing over 63-68'
    assert held(51) == [False]  # a swing in Harbour City's long balls that faded by 56'


def test_a_confirmed_case_runs_on_to_the_confirming_minute(m01):
    case = next(c for c in detect(m01.meta, m01.events) if c.window.end.minute == 63)
    ext = extended(case)
    assert str(ext.window) == "58:00-68:00" and ext.detected_at == case.window.end


def test_a_small_season_measures_every_metric_at_every_level():
    doc = season(matches=4, workers=2)
    levels = {(s["metric"], s["level"]) for s in doc["spreads"]}
    assert ("pressure_rate", "team") in levels and ("sprint_count", "player") in levels
    assert all(s["sd"] >= 0 and s["n"] >= 2 for s in doc["spreads"])
    assert doc["seeds"] == [3000, 3003]


def test_both_teams_are_measured_so_a_change_can_be_read_against_the_other_side(m01):
    from agents.confirm import both_teams

    readings = {
        (r.metric, r.subject): r for r in both_teams(m01, Window.model_validate("58:00-68:00"))
    }
    assert len(readings) == 6  # pressing, long balls and sprints for each team
    assert readings["pressure_rate", "Harbour City"].sigmas > 3  # Harbour City pressed...
    assert readings["long_ball_share", "Northvale"].sigmas > 3  # ...and Northvale went long
    assert abs(readings["pressure_rate", "Northvale"].sigmas) < 1
