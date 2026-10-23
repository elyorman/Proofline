import pytest
from pydantic import ValidationError

from contracts.planted import CAUSE_OBSERVABLES, GroundTruth, PlantedTruth
from contracts.prediction import Direction
from contracts.taxonomy import DEFAULT_THRESHOLD_KIND, Cause, Metric

HC_PRESS = dict(metric=Metric.PRESSURE_RATE, subject="Harbour City", direction=Direction.UP)
NV_LONG = dict(metric=Metric.LONG_BALL_SHARE, subject="Northvale", direction=Direction.UP)


def _truth(**overrides):
    base = dict(
        match_id="p-h-01",
        cause=Cause.PRESS_INTENSITY_UP,
        team="Harbour City",
        script_id="s1",
        started="60:00",
        window="60:00-68:00",
        observables=[HC_PRESS, NV_LONG],
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
        (dict(observables=[NV_LONG, HC_PRESS]), "observables must be"),
        (dict(observables=[HC_PRESS | {"direction": Direction.DOWN}, NV_LONG]), "observables must"),
        (dict(observables=[HC_PRESS | {"subject": "Northvale"}, NV_LONG]), "cannot be the team"),
        (dict(observables=[HC_PRESS, NV_LONG | {"subject": "Harbour City"}]), "be the opponent"),
        (dict(window="58:00-66:00"), "opens before the change began"),
        (dict(cause=Cause.NONE), "names nothing"),
    ],
)
def test_planted_truth_refuses_what_does_not_fit(overrides, message):
    with pytest.raises(ValidationError, match=message):
        PlantedTruth(**_truth(**overrides))


@pytest.mark.parametrize(
    "cause,subject,message",
    [
        (Cause.UNIT_FATIGUE, "Northvale.defence", "cannot be the unit"),
        (Cause.PLAYER_FATIGUE, "Harbour City", "cannot be the player"),
        (Cause.PLAYER_FATIGUE, "Harbour City.defence", "cannot be the player"),
    ],
)
def test_fatigue_is_measured_on_the_teams_own_unit_or_a_player(cause, subject, message):
    def fatigue(subject):
        observables = [
            dict(metric=o.metric, subject=subject, direction=o.direction)
            for o in CAUSE_OBSERVABLES[cause]
        ]
        return _truth(cause=cause, window="67:00-87:00", observables=observables)

    assert PlantedTruth(
        **fatigue("Harbour City.defence" if cause == Cause.UNIT_FATIGUE else "HC-04")
    )
    with pytest.raises(ValidationError, match=message):
        PlantedTruth(**fatigue(subject))


def test_a_team_name_may_contain_a_dot():
    dotted = _truth(observables=[HC_PRESS, NV_LONG | {"subject": "St. Orrin"}])
    assert PlantedTruth(**dotted)


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
    with pytest.raises(ValidationError, match="has no planted ground truth"):
        GroundTruth(suite="corrections", split="heldout", entries=[nothing])
