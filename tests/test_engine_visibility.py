import pytest

from contracts.clock import Window
from contracts.event import Event, PassQualifiers, Point
from engine.visibility import (
    change,
    clears,
    first_half,
    long_ball_share,
    pressure_rate,
    right_channel_share,
    separation,
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
