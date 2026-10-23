import pytest

from contracts.clock import MatchClock
from engine.params import ParamTimeline
from engine.script import Intervention, MatchScript

SCRIPT = MatchScript.model_validate(
    {
        "match_id": "t01",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC", "press_height": 0.45},
            "away": {"name": "Northvale", "code": "NV"},
        },
        "scripts": [
            {
                "id": "s1",
                "at": "60:00",
                "ramp": "3m",
                "team": "home",
                "set": {"press_height": 0.75},
            },
            {
                "id": "s2",
                "at": "62:00",
                "ramp": "6m",
                "team": "away",
                "player": "NV-03",
                "set": {"stamina_decay": 2.5},
            },
        ],
    }
)
TL = ParamTimeline(SCRIPT)
SECOND_HALF = 45 * 60


def at(minute: float) -> float:
    """Seconds into the second half for a display minute."""
    return minute * 60 - SECOND_HALF


def test_value_is_base_before_the_intervention():
    assert TL.team("home", 2, at(59.9))["press_height"] == pytest.approx(0.45)
    assert TL.team("home", 1, 30 * 60)["press_height"] == pytest.approx(0.45)


def test_value_ramps_linearly_then_holds():
    assert TL.team("home", 2, at(61.5))["press_height"] == pytest.approx(0.60)
    assert TL.team("home", 2, at(63))["press_height"] == pytest.approx(0.75)
    assert TL.team("home", 2, at(85))["press_height"] == pytest.approx(0.75)


def test_other_team_and_players_are_untouched():
    assert TL.team("away", 2, at(70))["press_height"] == pytest.approx(0.5)
    assert TL.player("away", "NV-04", 2, at(70))["stamina_decay"] == pytest.approx(1.0)


def test_player_parameter_ramps():
    assert TL.player("away", "NV-03", 2, at(65))["stamina_decay"] == pytest.approx(1.75)
    assert TL.player("away", "NV-03", 2, at(70))["stamina_decay"] == pytest.approx(2.5)


EDGES = MatchScript.model_validate(
    {
        "match_id": "t02",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC", "press_height": 0.4},
            "away": {"name": "Northvale", "code": "NV", "directness": 0.1},
        },
        "scripts": [
            {"id": "a", "at": "44:00", "ramp": "4m", "team": "home", "set": {"press_height": 0.8}},
            {"id": "b", "at": "70:00", "team": "away", "set": {"directness": 0.5}},
            {"id": "c", "at": "75:00", "ramp": "2m", "team": "away", "set": {"directness": 0.3}},
            {"id": "d", "at": "45+2:10", "ramp": "1m", "team": "away", "set": {"quality": 0.9}},
        ],
    }
)
EDGE_TL = ParamTimeline(EDGES)


def test_a_ramp_running_at_half_time_completes_at_the_restart():
    assert EDGE_TL.team("home", 1, 45 * 60)["press_height"] == pytest.approx(0.5)  # 1 of 4 min
    assert EDGE_TL.team("home", 2, 0)["press_height"] == pytest.approx(0.8)


def test_a_zero_ramp_is_a_step_at_its_start():
    assert EDGE_TL.team("away", 2, at(69.99))["directness"] == pytest.approx(0.1)
    assert EDGE_TL.team("away", 2, at(70))["directness"] == pytest.approx(0.5)


def test_the_later_intervention_wins():
    assert EDGE_TL.team("away", 2, at(76))["directness"] == pytest.approx(0.4)  # halfway to 0.3
    assert EDGE_TL.team("away", 2, at(80))["directness"] == pytest.approx(0.3)


def test_a_first_half_stoppage_start_ramps_within_stoppage():
    start = 47 * 60 + 10  # 45+2:10, in first-half seconds
    assert EDGE_TL.team("away", 1, start - 1)["quality"] == pytest.approx(0.5)
    assert EDGE_TL.team("away", 1, start + 30)["quality"] == pytest.approx(0.7)


TRIGGERED = MatchScript.model_validate(
    {
        "match_id": "t03",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC", "press_height": 0.4},
            "away": {"name": "Northvale", "code": "NV"},
        },
        "scripts": [
            {
                "id": "chase",
                "at": "55:00",
                "ramp": "2m",
                "team": "home",
                "when": "trailing",
                "set": {"press_height": 0.9},
            },
            {
                "id": "legs",
                "at": "60:00",
                "team": "away",
                "unit": "defence",
                "set": {"stamina_decay": 8.0},
            },
        ],
    }
)


def test_a_unit_intervention_reaches_every_player_of_that_unit_only():
    tl = ParamTimeline(TRIGGERED)
    assert tl.player("away", "NV-02", 2, at(61), unit="defence")["stamina_decay"] == 8.0
    assert tl.player("away", "NV-07", 2, at(61), unit="midfield")["stamina_decay"] == 1.0
    assert tl.player("home", "HC-02", 2, at(61), unit="defence")["stamina_decay"] == 1.0


def test_a_score_triggered_intervention_waits_for_its_start():
    tl = ParamTimeline(TRIGGERED)
    assert tl.started == {"chase": None, "legs": MatchClock.parse("60:00")}
    assert [iv.id for iv in tl.pending()] == ["chase"]
    assert tl.team("home", 2, at(70))["press_height"] == pytest.approx(0.4)
    tl.start(tl.pending()[0], MatchClock.parse("66:00"))
    assert tl.pending() == []
    assert tl.team("home", 2, at(67))["press_height"] == pytest.approx(0.65)  # half the ramp
    assert tl.team("home", 2, at(70))["press_height"] == pytest.approx(0.9)


def test_a_later_start_wins_even_when_its_at_is_earlier():
    fixed = {"id": "fixed", "at": "60:00", "team": "home", "set": {"press_height": 0.6}}
    script = TRIGGERED.model_copy(
        update={"scripts": [TRIGGERED.scripts[0], Intervention.model_validate(fixed)]}
    )
    tl = ParamTimeline(script)
    assert tl.team("home", 2, at(65))["press_height"] == pytest.approx(0.6)
    tl.start(tl.pending()[0], MatchClock.parse("70:00"))  # `at` 55:00, but it starts at 70:00
    assert tl.team("home", 2, at(75))["press_height"] == pytest.approx(0.9)
