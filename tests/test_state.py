import pytest

from contracts.clock import MatchClock, Window
from contracts.event import Event, PassQualifiers, Point
from contracts.meta import MatchMeta
from contracts.taxonomy import BaselineScope, Metric
from contracts.tool_result import ToolResult
from state.subjects import Subject, resolve
from state.tools import Call, Feed, baseline, game_state, metric


def _roster(code):
    roles = ["GK", "RB", "RCB", "LCB", "LB", "DM", "CM", "CM", "RW", "ST", "LW"]
    units = ["goalkeeper"] + ["defence"] * 4 + ["midfield"] * 3 + ["attack"] * 3
    return [
        {"player_id": f"{code}-{i:02d}", "name": f"P{i}", "role": r, "unit": u}
        for i, (r, u) in enumerate(zip(roles, units, strict=True), start=1)
    ]


META = MatchMeta(
    match_id="t01",
    teams={
        side: {"name": name, "code": code, "formation": "4-3-3", "players": _roster(code)}
        for side, name, code in (("home", "St. Orrin", "SO"), ("away", "Northvale", "NV"))
    },
)
WINDOW = Window.model_validate("58:00-63:00")
LATE = Call(tool_call_id="tc-1", as_of=MatchClock.parse("70:00"), now_ms=0)


def _e(type_, team, clock, x=30.0, y=34.0, dist=10.0, player=None, **qualifiers):
    pass_q = PassQualifiers(distance_m=dist, ball_speed_kmh=50, pressure_on_passer=0)
    return Event(
        event_id=f"e-{type_}-{team}-{clock}-{x}-{y}-{dist}-{player}",
        match_id="t01",
        clock=clock,
        wall_clock_ms=0,
        type=type_,
        team=team,
        player_id=player,
        start=Point(x=x, y=y),
        end=Point(x=x, y=y),
        pass_q=pass_q if type_ == "pass" else None,
        qualifiers=qualifiers,
    )


HALF_END = Event(
    event_id="end-1", match_id="t01", clock="45+0:00", wall_clock_ms=0, type="period_end", team="x"
)


def _sprint(player, clock, speed):
    team = "St. Orrin" if player.startswith("SO") else "Northvale"
    return _e("sprint", team, clock, player=player, speed_kmh=speed, distance_m=20.0)


def _feed(*events):
    return Feed(meta=META, events=sorted(events, key=lambda e: e.clock.sort_key), data_version="v1")


def test_subjects_resolve_through_the_roster_whatever_the_names():
    assert resolve(META, "St. Orrin") == Subject("St. Orrin")
    assert resolve(META, "St. Orrin.defence") == Subject("St. Orrin", unit="defence")
    assert resolve(META, "NV-04") == Subject("Northvale", player_id="NV-04")
    for unknown in ("St.", "St. Orrin.bench", "NV-12", "Harbour City"):
        with pytest.raises(ValueError, match="is not a team, unit or player"):
            resolve(META, unknown)


def test_pressure_rate_counts_the_zone_on_both_sides_of_the_ratio():
    feed = _feed(
        _e("pass", "Northvale", "59:00", x=30),  # in Northvale's first 60%
        _e("carry", "Northvale", "59:10", x=62),
        _e("carry", "Northvale", "59:20", x=70),  # beyond it
        _e("pressure", "St. Orrin", "59:30", x=60),  # x > 42 in the presser's frame
        _e("pressure", "St. Orrin", "59:40", x=40),
        _e("pressure", "St. Orrin", "64:00", x=60),  # after the window
    )
    result, evidence = metric(feed, Metric.PRESSURE_RATE, "St. Orrin", WINDOW, LATE)
    assert (result.value, result.n_events) == (0.5, 2)
    assert len(evidence.events) == 5 and evidence.evidence_set_id == result.evidence_set_id
    assert ToolResult.model_validate_json(result.model_dump_json()) == result


def test_shares_and_their_empty_windows():
    feed = _feed(
        *(_e("pass", "Northvale", "60:00", dist=d) for d in (10, 30, 31, 45)),
        _e("carry", "Northvale", "61:00", y=50),
        _e("carry", "Northvale", "61:00", y=10),
    )
    long, _ = metric(feed, Metric.LONG_BALL_SHARE, "Northvale", WINDOW, LATE)
    right, _ = metric(feed, Metric.CHANNEL_SHARE_RIGHT, "Northvale", WINDOW, LATE)
    assert (long.value, long.n_events) == (0.5, 4)
    assert (right.value, right.n_events) == (pytest.approx(1 / 6), 6)  # only y=50
    empty, _ = metric(feed, Metric.LONG_BALL_SHARE, "St. Orrin", WINDOW, LATE)
    assert empty.value is None and empty.insufficient_data == "no passes"
    with pytest.raises(ValueError, match="measured for a team"):
        metric(feed, Metric.LONG_BALL_SHARE, "NV-04", WINDOW, LATE)


def test_sprints_by_team_unit_or_player_against_the_played_first_half():
    feed = _feed(
        _sprint("SO-02", "10:00", 30.0),
        _sprint("SO-10", "20:00", 32.0),
        _sprint("SO-02", "60:00", 28.0),
        HALF_END,
    )
    count, _ = metric(feed, Metric.SPRINT_COUNT, "St. Orrin.defence", WINDOW, LATE)
    first, _ = baseline(feed, Metric.SPRINT_COUNT, "St. Orrin", BaselineScope.FIRST_HALF, LATE)
    speed, _ = metric(feed, Metric.SPRINT_SPEED, "SO-10", WINDOW, LATE)
    assert count.value == pytest.approx(1 / 5) and first.baseline.value == pytest.approx(2 / 45)
    assert speed.value is None and speed.insufficient_data == "no sprints"


def test_a_tool_reads_only_what_the_clock_has_delivered():
    feed = _feed(_e("pass", "Northvale", "20:00"), HALF_END, _e("pass", "Northvale", "60:00"))
    early = Call(tool_call_id="tc-2", as_of=MatchClock.parse("40:00"), now_ms=0)
    with pytest.raises(ValueError, match="has not finished"):
        metric(feed, Metric.LONG_BALL_SHARE, "Northvale", WINDOW, early)
    first_half = BaselineScope.FIRST_HALF
    pending, _ = baseline(feed, Metric.LONG_BALL_SHARE, "Northvale", first_half, early)
    assert pending.insufficient_data == "the first half has not ended" and pending.baseline is None
    so_far, evidence = baseline(
        feed, Metric.LONG_BALL_SHARE, "Northvale", BaselineScope.MATCH_SO_FAR, early
    )
    assert so_far.baseline.n_events == 1 and len(evidence.events) == 1


def test_game_state_counts_only_goals_already_scored():
    feed = _feed(_e("goal", "Northvale", "12:30"), _e("goal", "St. Orrin", "77:09"))
    at_63 = Call(tool_call_id="tc-3", as_of=MatchClock.parse("63:00"), now_ms=0)
    result, _ = game_state(feed, at_63)
    assert result.values == {"home_goals": 0.0, "away_goals": 1.0}
