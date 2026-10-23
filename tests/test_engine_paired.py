from pathlib import Path

import pytest

from contracts.clock import MatchClock
from contracts.eval_run import ExclusionRule
from contracts.planted import TruthObservable
from contracts.prediction import Direction
from contracts.taxonomy import Cause, Metric
from engine.paired import _opponent, judge, measure, resolve, t95, window_after
from engine.script import Intervention, load_script

ROOT = Path(__file__).resolve().parents[1]
M01 = load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml")
PRESS = [
    TruthObservable(metric=Metric.PRESSURE_RATE, subject="Harbour City", direction=Direction.UP),
    TruthObservable(metric=Metric.LONG_BALL_SHARE, subject="Northvale", direction=Direction.UP),
]


def _with(**fields):
    iv = Intervention.model_validate({"id": "s1", "team": "home", **fields})
    return M01.model_copy(update={"scripts": [iv]})


def test_a_window_is_counted_from_the_start_of_the_change():
    window = window_after(MatchClock.parse("61:27"), (7, 27))
    assert (str(window.start), str(window.end)) == ("68:27", "88:27")


def test_a_window_stays_in_minutes_every_match_plays_after_a_first_half_baseline():
    assert window_after(MatchClock.parse("63:00"), (7, 27)).end == MatchClock.parse("90:00")
    with pytest.raises(ValueError, match="not every match plays"):
        window_after(MatchClock.parse("63:27"), (7, 27))
    with pytest.raises(ValueError, match="cannot be compared with the first half"):
        window_after(MatchClock.parse("30:00"), (0, 8))


def test_the_interval_uses_the_t_quantile_of_its_seed_count():
    assert t95(19) == pytest.approx(2.093, abs=1e-3)
    assert t95(29) == pytest.approx(2.045, abs=1e-3)


def test_observables_are_named_for_the_script():
    tired = Intervention.model_validate(
        {"id": "s1", "at": "60:00", "team": "away", "unit": "defence", "set": {"stamina_decay": 8}}
    )
    resolved = resolve(Cause.UNIT_FATIGUE, M01, tired)
    assert [o.subject for o in resolved] == ["Northvale.defence", "Northvale.defence"]
    press = resolve(Cause.PRESS_INTENSITY_UP, M01, M01.scripts[0])
    assert [(o.metric, o.subject) for o in press] == [
        (Metric.PRESSURE_RATE, "Harbour City"),
        (Metric.LONG_BALL_SHARE, "Northvale"),
    ]
    with pytest.raises(ValueError, match="measured on a unit; s1 names none"):
        resolve(Cause.UNIT_FATIGUE, M01, M01.scripts[0])


def test_the_opponent_is_found_for_teams_units_and_players_whatever_their_names():
    teams = {
        "home": M01.teams["home"].model_copy(update={"name": "St. Orrin"}),
        "away": M01.teams["away"].model_copy(update={"name": "Kell-on-Sea"}),
    }
    script = M01.model_copy(update={"teams": teams})
    assert _opponent(script, "St. Orrin", "home") == "Kell-on-Sea"
    assert _opponent(script, "St. Orrin.defence", "home") == "Kell-on-Sea"
    assert _opponent(script, "Kell-on-Sea", "home") == "St. Orrin"
    assert _opponent(script, "SO-04", "home") == "Kell-on-Sea"  # a player of the home side


def test_the_demo_press_counts_toward_recall():
    checks, seeds = measure(M01, "s1", PRESS, (0, 8), range(1500, 1600), pairs=20)
    assert len(seeds) == 20
    assert all(c.clears_zero and c.separates for c in checks)
    assert judge("m01", Cause.PRESS_INTENSITY_UP, checks) is None


def test_an_intervention_that_changes_nothing_is_not_observable():
    idle = _with(at="60:00", set={"press_height": 0.3})  # Harbour City's own base press
    checks, _ = measure(idle, "s1", PRESS, (0, 8), range(1500, 1600), pairs=20)
    assert all(c.ci_low == c.ci_high == 0 for c in checks)
    assert judge("idle", Cause.PRESS_INTENSITY_UP, checks).rule == ExclusionRule.NO_PAIRED_EFFECT


def test_a_change_that_never_starts_in_time_cannot_be_measured():
    late = _with(at="80:00", set={"press_height": 0.9})
    with pytest.raises(ValueError, match="starts in time on 0 seeds"):
        measure(late, "s1", PRESS, (0, 8), range(1500, 1510), pairs=20)
