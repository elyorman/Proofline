from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.script import MatchScript, load_script

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


def _script(**overrides):
    base = {
        "match_id": "t01",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC"},
            "away": {"name": "Northvale", "code": "NV"},
        },
    }
    base.update(overrides)
    return MatchScript.model_validate(base)


def test_demo_script_loads():
    script = load_script(M01)
    s1, s2 = script.scripts
    assert (s1.at.period, s1.at.minute, s1.ramp_seconds) == (2, 60, 180)
    assert s2.player == "NV-03"
    assert script.amendments[0].batch.shift.dy_m == -18


def test_unknown_parameter_is_rejected():
    with pytest.raises(ValidationError):
        _script(scripts=[{"id": "s1", "at": "60:00", "team": "home", "set": {"pres": 0.7}}])


def test_player_must_be_on_the_named_team():
    player_on_wrong_team = {
        "id": "s1",
        "at": "60:00",
        "team": "home",
        "player": "NV-03",
        "set": {"stamina_decay": 2.0},
    }
    with pytest.raises(ValidationError):
        _script(scripts=[player_on_wrong_team])


def test_unquoted_yaml_time_is_rejected():
    # YAML reads an unquoted 60:00 as the integer 3600; the clock must refuse it.
    with pytest.raises(ValidationError):
        _script(scripts=[{"id": "s1", "at": 3600, "team": "home", "set": {"press_height": 0.7}}])
