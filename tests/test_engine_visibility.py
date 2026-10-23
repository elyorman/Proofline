import math

import pytest

from contracts.clock import Window
from contracts.event import Event, PassQualifiers, Point
from contracts.prediction import Direction
from contracts.taxonomy import Metric
from engine.visibility import (
    change,
    clears,
    first_half,
    long_ball_share,
    observable,
    pressure_rate,
    right_channel_share,
    separation,
    sprint_count,
    sprint_speed,
    window_minutes,
)


def _event(type_, team, clock="10:00", x=30.0, y=34.0, dist=10.0):
    pass_q = PassQualifiers(distance_m=dist, ball_speed_kmh=50, pressure_on_passer=0)
    return Event(
        event_id="e",
        match_id="t01",
        clock=clock,
        wall_clock_ms=0,
        type=type_,
        team=team,
        start=Point(x=x, y=y),
        end=Point(x=x, y=y),
        pass_q=pass_q if type_ == "pass" else None,
    )


def _all(e):
    return True


def test_pressure_rate_counts_only_the_opponents_first_60_percent():
    events = [
        _event("pass", "Northvale", x=30),  # in Northvale's first 60%
        _event("carry", "Northvale", x=62),
        _event("carry", "Northvale", x=70),  # beyond it
        _event("pass", "Harbour City", x=30),  # the presser's own action
        _event("pressure", "Harbour City", x=60),  # x > 42 in the presser's frame
        _event("pressure", "Harbour City", x=40),
        _event("pressure", "Northvale", x=60),  # the other team's press
    ]
    assert pressure_rate("Harbour City", "Northvale")(events, _all) == 0.5


def test_long_ball_share_counts_passes_over_30_metres():
    events = [_event("pass", "Northvale", dist=d) for d in (10, 30, 31, 45)]
    events.append(_event("pass", "Harbour City", dist=50))
    assert long_ball_share("Northvale")(events, _all) == 0.5


def test_right_channel_share_uses_the_right_third_of_the_width():
    events = [_event("carry", "Northvale", y=y) for y in (10, 45.3, 45.4, 60)]
    events.append(_event("carry", "Harbour City", y=60))
    assert right_channel_share("Northvale")(events, _all) == 0.5


def test_change_is_the_window_against_the_same_matchs_first_half():
    events = [
        _event("pass", "Northvale", clock="10:00", dist=10),
        _event("pass", "Northvale", clock="20:00", dist=40),
        _event("pass", "Northvale", clock="60:00", dist=40),
    ]
    assert long_ball_share("Northvale")(events, first_half) == 0.5
    assert change(long_ball_share("Northvale"), events, Window.model_validate("58:00-63:00")) == 0.5


def test_observables_count_only_the_events_kept():
    events = [
        _event("carry", "Northvale", clock="10:00", y=60),
        _event("pressure", "Harbour City", clock="10:00", x=60),
        _event("carry", "Northvale", clock="60:00", y=10),
        _event("carry", "Northvale", clock="60:00", y=10),
        _event("pressure", "Harbour City", clock="60:00", x=60),
    ]
    assert right_channel_share("Northvale")(events, first_half) == 1.0
    assert pressure_rate("Harbour City", "Northvale")(events, first_half) == 1.0
    assert pressure_rate("Harbour City", "Northvale")(events, _all) == pytest.approx(2 / 3)


def test_first_half_stoppage_belongs_to_the_first_half():
    events = [
        _event("pass", "Northvale", clock="10:00", dist=10),
        _event("pass", "Northvale", clock="45+2:00", dist=40),
        _event("pass", "Northvale", clock="50:00", dist=10),
    ]
    assert long_ball_share("Northvale")(events, first_half) == 0.5
    window = Window.model_validate("45:00-55:00")
    assert change(long_ball_share("Northvale"), events, window) == -0.5


def test_separation_and_clears_are_in_natural_standard_deviations():
    natural = [0.0, 2.0, 4.0]  # mean 2, sd 2
    assert separation([6.0, 8.0], natural) == pytest.approx(2.5)
    assert clears(6.0, natural)
    assert not clears(5.9, natural)


def _sprint(team, player, position, speed, clock):
    return Event(
        event_id="s",
        match_id="t01",
        clock=clock,
        wall_clock_ms=0,
        type="sprint",
        team=team,
        player_id=player,
        position=position,
        start=Point(x=30, y=30),
        end=Point(x=50, y=30),
        qualifiers={"speed_kmh": speed, "distance_m": 20.0},
    )


SPRINTS = [
    _sprint("Harbour City", "HC-02", "RB", 30.0, "10:00"),
    _sprint("Harbour City", "HC-10", "ST", 32.0, "20:00"),
    _sprint("Northvale", "NV-02", "RB", 31.0, "20:00"),
    _sprint("Harbour City", "HC-02", "RB", 28.0, "60:00"),
    Event(
        event_id="e",
        match_id="t01",
        clock="45+0:00",
        wall_clock_ms=0,
        type="period_end",
        team="Harbour City",
    ),
]
CARD = Window.model_validate("58:00-63:00")


def test_sprints_are_counted_per_minute_for_a_team_a_unit_or_a_player():
    # One sprint in 5 minutes against one in the 45-minute first half.
    assert change(sprint_count("Harbour City.defence"), SPRINTS, CARD) == pytest.approx(
        1 / 5 - 1 / 45
    )
    assert change(sprint_count("HC-10"), SPRINTS, CARD) == pytest.approx(-1 / 45)
    assert change(sprint_count("Northvale"), SPRINTS, CARD) == pytest.approx(-1 / 45)


def test_sprint_speed_is_the_mean_and_undefined_without_sprints():
    assert change(sprint_speed("Harbour City"), SPRINTS, CARD) == pytest.approx(28.0 - 31.0)
    assert math.isnan(change(sprint_speed("Northvale"), SPRINTS, CARD))


def test_a_window_spanning_half_time_is_refused():
    with pytest.raises(ValueError, match="spans half-time"):
        window_minutes(Window.model_validate("44:00-46:00"))


def test_observables_are_found_by_metric():
    assert observable(Metric.PRESSURE_RATE, "Harbour City", "Northvale")
    with pytest.raises(ValueError, match="does not measure"):
        observable(Metric.XG, "Harbour City", "Northvale")


def test_clears_in_the_story_direction():
    natural = [0.0, 2.0, 4.0]  # mean 2, sd 2
    assert clears(-2.0, natural, direction=Direction.DOWN)
    assert not clears(-1.9, natural, direction=Direction.DOWN)
    assert not clears(6.0, natural, direction=Direction.DOWN)
