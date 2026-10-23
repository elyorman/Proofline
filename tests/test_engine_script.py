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


def _intervention(**overrides):
    base = {"id": "s1", "at": "60:00", "team": "home", "set": {"press_height": 0.7}}
    base.update(overrides)
    return base


def _amendment(at="68:00", dy=-22, dx=0.0, **band):
    batch_filter = {"types": ["pass", "carry"], "team": "away", "window": "45:00-55:00"}
    batch_filter |= {"y_min": 0, "y_max": 46, **band}
    shift = {"dx_m": dx, "dy_m": dy}
    return {"id": "a1", "at": at, "batch": {"filter": batch_filter, "shift": shift}, "reason": "r"}


def test_demo_script_loads():
    script = load_script(M01)
    (s1,) = script.scripts
    assert (s1.at.period, s1.at.minute, s1.ramp_seconds) == (2, 56, 120)
    assert s1.set == {"press_height": 0.9}
    (a1,) = script.amendments
    assert a1.batch.filter.types == ["pass", "carry", "dribble"]
    assert a1.batch.shift.dy_m == -22


@pytest.mark.parametrize(
    "intervention,message",
    [
        ({"set": {"pres": 0.7}}, "not valid team parameter"),
        ({"set": {"stamina_decay": 2.0}}, "not valid team parameter"),
        ({"set": {"press_height": 7.5}}, "outside"),
        ({"set": {"press_height": float("nan")}}, "outside"),
        ({"player": "NV-03", "set": {"stamina_decay": 2.0}}, "not on the home team"),
        ({"player": "HC-3", "set": {"stamina_decay": 2.0}}, "should match pattern"),
        ({"player": "HC-03", "set": {"stamina_decay": -1.0}}, "outside"),
        ({"player": "HC-03", "set": {"stamina_decay": 10.5}}, "outside"),
        ({"unit": "defence", "set": {"press_height": 0.7}}, "not valid player parameter"),
        ({"unit": "defense", "set": {"stamina_decay": 2.0}}, "Input should be"),
        ({"player": "HC-03", "unit": "defence", "set": {"stamina_decay": 2.0}}, "not both"),
        ({"when": "drawing"}, "Input should be"),
    ],
)
def test_bad_interventions_are_rejected(intervention, message):
    with pytest.raises(ValidationError, match=message):
        _script(scripts=[_intervention(**intervention)])


@pytest.mark.parametrize(
    "amendment,message",
    [
        (_amendment(types=["carries"]), "Input should be"),
        (_amendment(types=[]), "at least 1 item"),
        (_amendment(types=["shot"]), "shot cannot be amended"),
        (_amendment(y_min=50, y_max=32), "above y_max"),
        (_amendment(at="50:00"), "before its window ends"),
        (_amendment(y_max=48), "leaves the pitch"),
        (_amendment(dx=3.0), "lateral only"),
        (_amendment(dy=float("nan")), "finite, non-zero"),
        (_amendment(dy=float("inf")), "finite, non-zero"),
        (_amendment(dy=0), "finite, non-zero"),
    ],
)
def test_incoherent_amendments_are_rejected(amendment, message):
    with pytest.raises(ValidationError, match=message):
        _script(amendments=[amendment])


def test_an_amendment_can_relocate_several_event_types():
    script = _script(amendments=[_amendment(types=["pass", "carry", "dribble"])])
    assert script.amendments[0].batch.filter.types == ["pass", "carry", "dribble"]


def test_unquoted_yaml_time_is_rejected(tmp_path):
    # YAML reads an unquoted 56:00 as the integer 3360; loading must refuse it.
    bad = tmp_path / "bad.yaml"
    bad.write_text(M01.read_text().replace('at: "56:00"', "at: 56:00"))
    with pytest.raises(ValidationError, match="valid dictionary"):
        load_script(bad)


def test_the_spec_shows_the_demo_script_as_it_is():
    spec = (M01.parents[3] / "docs" / "spec.md").read_text(encoding="utf-8")
    assert f"```yaml\n{M01.read_text(encoding='utf-8')}```" in spec


def test_a_unit_and_a_score_trigger_can_be_scripted():
    script = _script(
        scripts=[
            _intervention(unit="midfield", set={"stamina_decay": 8.0}),
            _intervention(id="s2", when="trailing", set={"press_height": 0.9}),
        ]
    )
    tired, chasing = script.scripts
    assert (tired.unit, tired.player, chasing.when) == ("midfield", None, "trailing")
