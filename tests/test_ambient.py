"""The ambient layer over hand-built events: tags, badges, strips and the ticker."""

import json

import pytest

from ambient import RULES, build_feed, strips, tags
from ambient.ticker import LOCALES, football_minute, templates, ticker
from contracts.ambient import AmbientFeed
from contracts.clock import MatchClock
from contracts.event import Event, PassQualifiers, Point, ShotQualifiers
from contracts.meta import MatchMeta

HOME, AWAY = "St. Orrin", "Northvale"


def _roster(code):
    units = ["goalkeeper"] + ["defence"] * 4 + ["midfield"] * 3 + ["attack"] * 3
    return [
        {"player_id": f"{code}-{i:02d}", "name": f"{code} Player {i}", "role": "X", "unit": u}
        for i, u in enumerate(units, start=1)
    ]


META = MatchMeta(
    match_id="t01",
    teams={
        side: {"name": name, "code": code, "formation": "4-3-3", "players": _roster(code)}
        for side, name, code in (("home", HOME, "SO"), ("away", AWAY, "NV"))
    },
)
_n = iter(range(1_000_000))


def ev(type_, clock, team=HOME, player="SO-10", start=(30.0, 34.0), end=None, **kw):
    return Event(
        event_id=f"e{next(_n)}",
        match_id="t01",
        clock=clock,
        wall_clock_ms=0,
        type=type_,
        team=team,
        player_id=player,
        start=Point(x=start[0], y=start[1]) if start else None,
        end=Point(x=end[0], y=end[1]) if end else None,
        **kw,
    )


def pass_(clock, dist=10.0, pressure=0.0, outcome="complete", start=(30, 34), end=(40, 34), **kw):
    receiver = kw.pop("receiver_id", None)
    q = PassQualifiers(
        distance_m=dist, ball_speed_kmh=50, pressure_on_passer=pressure, receiver_id=receiver
    )
    return ev("pass", clock, pass_q=q, outcome=outcome, start=start, end=end, **kw)


def shot(clock, speed=80.0, outcome="off_target", **kw):
    q = ShotQualifiers(shot_speed_kmh=speed, distance_m=18, angle_deg=30, defenders_in_cone=1)
    return ev("shot", clock, shot_q=q, outcome=outcome, **kw)


def sprint(clock, speed, **kw):
    return ev("sprint", clock, qualifiers={"speed_kmh": speed, "distance_m": 25.0}, **kw)


def whistle(clock):
    return ev("period_end", clock, player=None, start=None)


# Speed tags and pass difficulty.


def test_speed_tags_fire_strictly_above_their_thresholds():
    events = [
        sprint("10:00", 32.0),
        sprint("10:05", 32.1, team=AWAY, player="NV-07"),
        shot("11:00", speed=110.0),
        shot("12:00", speed=110.4, outcome="on_target"),
        sprint("13:00", 35.0, player=None),
    ]
    found = tags.speed_tags(events)
    assert [(t.kind, t.player_id, t.speed_kmh) for t in found] == [
        ("sprint", "NV-07", 32.1),
        ("shot", "SO-10", 110.4),
    ]
    assert found[0].team == AWAY and found[0].at == MatchClock.parse("10:05")


@pytest.mark.parametrize(
    "dist, pressure, difficulty",
    [(40.0, 0.6, 80), (20.0, 0.0, 25), (60.0, 1.0, 100), (0.0, 0.0, 0), (32.0, 0.8, 80)],
)
def test_pass_difficulty_is_half_length_and_half_pressure(dist, pressure, difficulty):
    assert tags.pass_difficulty(pass_("10:00", dist=dist, pressure=pressure)) == difficulty


def test_pass_difficulty_is_only_for_passes():
    with pytest.raises(ValueError, match="only a pass"):
        tags.pass_difficulty(sprint("10:00", 30.0))


def test_only_completed_standout_passes_get_a_badge():
    hard = pass_("20:00", dist=45.0, pressure=0.7, receiver_id="SO-09")
    events = [
        hard,
        pass_("21:00", dist=45.0, pressure=0.7, outcome="incomplete"),
        pass_("22:00", dist=38.0, pressure=0.6),  # 47.5 + 30 = 78
    ]
    badges = tags.pass_badges(events)
    assert [(b.event_id, b.difficulty, b.receiver_id) for b in badges] == [
        (hard.event_id, 85, "SO-09")
    ]
    assert badges[0].distance_m == 45.0 and badges[0].pressure_on_passer == 0.7


# Momentum.


def test_threat_counts_shots_and_completed_entries_into_the_final_third():
    assert strips.threat(shot("10:00")) == 3.0
    assert strips.threat(pass_("10:00", start=(60, 30), end=(75, 30))) == 1.0
    assert strips.threat(ev("carry", "10:00", start=(69.9, 30), end=(70, 30))) == 1.0
    assert strips.threat(pass_("10:00", start=(60, 30), end=(75, 30), outcome="incomplete")) == 0
    assert strips.threat(pass_("10:00", start=(72, 30), end=(90, 30))) == 0.0  # already there
    assert strips.threat(ev("pressure", "10:00")) == 0.0


def test_momentum_is_the_decayed_share_of_recent_threat():
    events = [
        shot("00:30"),
        pass_("02:10", team=AWAY, player="NV-04", start=(50, 34), end=(80, 34)),
        whistle("03:20"),
    ]
    points = strips.momentum(events, HOME, AWAY)
    assert [(p.minute, str(p.at)) for p in points] == [
        (0, "01:00"),
        (1, "02:00"),
        (2, "03:00"),
        (3, "03:20"),
    ]
    decay = 0.5**0.5
    assert points[0].value == 1.0  # 3 home points, none away
    assert points[1].home_threat == round(3 * decay, 2)
    assert points[1].value == round(3 * decay / 3, 3)  # a quiet spell fades towards zero
    home, away = 3 * decay**2, 1.0
    assert points[2].value == round((home - away) / max(home + away, 3), 3)
    assert all(-1 <= p.value <= 1 for p in points)


def test_momentum_restarts_each_half_and_waits_for_the_minute_to_end():
    events = [
        shot("44:10"),
        whistle("45+0:30"),
        shot("46:20", team=AWAY, player="NV-09"),
        shot("47:30", team=AWAY, player="NV-09"),  # the live minute: not yet shown
    ]
    points = strips.momentum(events, HOME, AWAY)
    second = [p for p in points if p.period == 2]
    assert [p.minute for p in second] == [45, 46]
    assert second[0].home_threat == 0.0  # the home shot before half-time is not carried over
    assert second[1].value == -1.0
    assert max(p.at for p in points if p.period == 1) == MatchClock.parse("45+0:30")


# Control vs chaos.


def _spell(start_min, period=1, actions=20, turnovers=1):
    """`actions` passes and `turnovers` possession changes inside one minute."""
    base = start_min * 60
    out = [
        pass_(str(MatchClock(period=period, minute=(base + i) // 60, second=(base + i) % 60)))
        for i in range(actions)
    ]
    out += [
        ev("possession_change", MatchClock(period=period, minute=start_min, second=30 + i))
        for i in range(turnovers)
    ]
    return out


def test_control_reads_actions_per_possession_over_five_minutes():
    events = _spell(0, actions=20, turnovers=1) + _spell(5, actions=12, turnovers=5)
    points = strips.control(events + [whistle("06:00")])
    by_at = {str(p.at): p for p in points}
    first = by_at["01:00"]
    assert (str(first.since), first.actions, first.turnovers) == ("00:00", 20, 1)
    assert first.spell == 10.0 and first.chaos == 0.0
    # 05:00-06:00 only: 12 actions over 6 possessions is a spell of 2, full chaos.
    late = by_at["06:00"]
    assert str(late.since) == "01:00"
    assert (late.actions, late.turnovers, late.spell, late.chaos) == (12, 5, 2.0, 1.0)
    mid = strips.control(_spell(0, actions=13, turnovers=1) + [whistle("01:00")])[0]
    assert mid.spell == 6.5 and mid.chaos == 0.5


def test_a_thin_window_has_no_gauge_reading_and_nothing_future_is_counted():
    events = _spell(0, actions=9, turnovers=0) + _spell(2, actions=30) + [whistle("02:40")]
    points = strips.control(events)
    assert [str(p.at) for p in points] == ["01:00", "02:00", "02:40"]
    assert points[0].spell is None and points[0].chaos is None
    assert points[1].actions == 9  # the 2nd-minute spell starts at 02:00, after the sample
    assert points[2].actions == 9 + 30


def test_control_samples_stay_inside_their_half():
    first_half = _spell(44) + [whistle("45+0:00")]
    events = first_half + _spell(45, period=2, actions=12) + [whistle("46:00")]
    second = [p for p in strips.control(events) if p.at.period == 2]
    assert [(str(p.since), str(p.at), p.actions) for p in second] == [("45:00", "46:00", 12)]


# Ticker.


@pytest.mark.parametrize(
    "clock, minute",
    [
        ("00:00", "1'"),
        ("66:49", "67'"),
        ("44:59", "45'"),
        ("45+1:30", "45+2'"),
        ("90+2:10", "90+3'"),
    ],
)
def test_ticker_uses_football_minutes(clock, minute):
    for locale in LOCALES:
        assert football_minute(MatchClock.parse(clock), locale) == minute


def test_every_template_exists_in_every_language():
    tables = templates()
    assert set(tables) == {"en", "es"}
    assert set(tables["en"]) == set(tables["es"])
    assert tables["en"]["goal"] != tables["es"]["goal"]


def test_ticker_writes_localized_lines_for_the_news_only():
    hard = pass_("30:00", dist=45.0, pressure=0.8, player="NV-07", team=AWAY)
    events = [
        ev("period_start", "00:00", player=None, start=None),
        ev("set_piece", "01:00", qualifiers={"kind": "throw_in"}),
        shot("11:59", speed=96.6, outcome="on_target", team=AWAY, player="NV-09"),
        shot("12:00", speed=101.0, outcome="goal"),
        ev("goal", "12:02"),
        ev("foul", "20:00", team=AWAY, player="NV-04"),
        ev("set_piece", "20:20", qualifiers={"kind": "free_kick"}),
        hard,
        whistle("45+2:03"),
    ]
    badges = tags.pass_badges(events)
    lines = ticker(events, META, badges)
    assert [line.kind for line in lines] == [
        "kick_off",
        "shot",
        "goal",
        "foul",
        "free_kick",
        "pass_badge",
        "half_time",
    ]
    text = {line.kind: line.text for line in lines}
    assert text["shot"].en == "Shot on target — NV Player 9, 12' · 97 km/h"
    assert text["shot"].es == "Tiro a puerta — NV Player 9, 12' · 97 km/h"
    assert text["goal"].en == "Goal — SO Player 10 (St. Orrin), 13' · St. Orrin 1–0 Northvale"
    assert text["goal"].es.startswith("Gol — SO Player 10")
    assert text["free_kick"].es == "Tiro libre para St. Orrin, 21'"
    assert text["pass_badge"].en == "Standout pass — NV Player 7, 31' · difficulty 90"
    assert text["half_time"].en == "Half-time: St. Orrin 1–0 Northvale"
    assert [line.team for line in lines][:3] == [None, AWAY, HOME]


# The whole feed.


def test_the_feed_is_valid_deterministic_and_states_its_rules():
    events = [
        ev("period_start", "00:00", player=None, start=None),
        *_spell(0),
        sprint("00:40", 34.2),
        shot("00:50", speed=112.0),
        whistle("02:00"),
    ]
    feed = build_feed(list(reversed(events)), META)
    AmbientFeed.model_validate_json(feed.model_dump_json())
    assert feed.model_dump() == build_feed(events, META).model_dump()
    assert (feed.home, feed.away, feed.rules) == (HOME, AWAY, RULES)
    assert (RULES.sprint_kmh, RULES.shot_kmh, RULES.badge_difficulty) == (32.0, 110.0, 80)
    assert (RULES.shot_threat, RULES.entry_threat, RULES.momentum_half_life_min) == (3, 1, 2)
    assert (RULES.control_spell, RULES.chaos_spell, RULES.control_window_min) == (10, 3, 5)
    assert [t.kind for t in feed.speed_tags] == ["sprint", "shot"]
    assert [p.minute for p in feed.momentum] == [0, 1]
    assert feed.ticker[0].kind == "kick_off"
    json.loads(feed.model_dump_json())


def test_the_feed_refuses_another_match():
    other = ev("period_start", "00:00", player=None, start=None).model_copy(
        update={"match_id": "t02"}
    )
    with pytest.raises(ValueError, match="different match"):
        build_feed([other], META)
