import pytest
from pydantic import ValidationError

from contracts.planted import CAUSE_OBSERVABLES, GroundTruth, PlantedTruth
from contracts.prediction import Direction
from contracts.taxonomy import DEFAULT_THRESHOLD_KIND, Cause, Metric


def _truth(**overrides):
    base = dict(
        match_id="p-h-01",
        cause=Cause.PRESS_INTENSITY_UP,
        team="Harbour City",
        script_id="s1",
        started="60:00",
        window="60:00-68:00",
        observables=[
            dict(metric=Metric.PRESSURE_RATE, subject="Harbour City", direction=Direction.UP),
            dict(metric=Metric.LONG_BALL_SHARE, subject="Northvale", direction=Direction.UP),
        ],
    )
    return base | overrides


def test_plantable_classes_have_real_observables():
    for cause, observables in CAUSE_OBSERVABLES.items():
        assert cause.domain in ("tactical", "physical", "game_state")
        assert observables and all(o.metric in DEFAULT_THRESHOLD_KIND for o in observables)
        assert all(o.direction != Direction.FLAT for o in observables)
    # Every domain has a class the engine can plant, so every agent can be right.
    assert {c.domain for c in CAUSE_OBSERVABLES} == {"tactical", "physical", "game_state"}


def test_planted_truth_matches_its_class():
    assert PlantedTruth(**_truth()).window.end.minute == 68
    nothing = PlantedTruth(match_id="d-h-01", cause=Cause.NONE)
    assert nothing.observables == []


@pytest.mark.parametrize(
    "overrides,message",
    [
        (dict(cause=Cause.BLOCK_DEEPER), "cannot be planted"),
        (dict(team=None), "names its team, script and window"),
        (dict(observables=[]), "observables must be"),
        (dict(window="58:00-66:00"), "opens before the change began"),
        (dict(cause=Cause.NONE), "names nothing"),
    ],
)
def test_planted_truth_refuses_what_does_not_fit(overrides, message):
    with pytest.raises(ValidationError, match=message):
        PlantedTruth(**_truth(**overrides))


def test_ground_truth_fits_its_suite():
    planted = PlantedTruth(**_truth())
    nothing = PlantedTruth(match_id="d-h-01", cause=Cause.NONE)
    assert GroundTruth(suite="planted", split="heldout", entries=[planted])
    assert GroundTruth(suite="decoys", split="heldout", entries=[nothing])
    with pytest.raises(ValidationError, match="plants nothing"):
        GroundTruth(suite="decoys", split="heldout", entries=[planted])
    with pytest.raises(ValidationError, match="plants a cause"):
        GroundTruth(suite="planted", split="heldout", entries=[nothing])
    with pytest.raises(ValidationError, match="appears once"):
        GroundTruth(suite="planted", split="heldout", entries=[planted, planted])
