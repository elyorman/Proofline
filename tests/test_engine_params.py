import pytest

from engine.params import ParamTimeline
from engine.script import MatchScript

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
