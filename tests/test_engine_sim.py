import math
from itertools import pairwise
from pathlib import Path

from contracts.event import Point
from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)


def _dump(events):
    return [e.model_dump_json() for e in events]


def test_same_script_and_seed_is_deterministic():
    assert _dump(MatchSim(M01, seed=3).run()) == _dump(MatchSim(M01, seed=3).run())


def test_seed_changes_the_match():
    assert _dump(MatchSim(M01, seed=3).run()) != _dump(MatchSim(M01, seed=4).run())


def test_events_are_ordered_with_sequential_ids():
    events = MatchSim(M01, seed=3).run()
    assert [e.event_id for e in events] == [f"m01-{i:05d}" for i in range(1, len(events) + 1)]
    keys = [e.clock.sort_key for e in events]
    assert keys == sorted(keys)


def test_two_periods_with_stoppage_time():
    events = MatchSim(M01, seed=3).run()
    markers = [e.type for e in events if e.type in ("period_start", "period_end")]
    assert markers == ["period_start", "period_end", "period_start", "period_end"]
    assert any(e.clock.period == 1 and e.clock.stoppage for e in events)


def test_every_player_is_on_a_roster():
    sim = MatchSim(M01, seed=3)
    events = sim.run()
    roster = {p.player_id for side in sim.lineups.values() for p in side}
    assert {e.player_id for e in events if e.player_id} <= roster
    assert {e.team for e in events} == {"Harbour City", "Northvale"}


def test_interventions_leave_the_match_before_them_untouched():
    for sid, start_minute in (("s1", 60), ("s2", 62)):
        without = M01.model_copy(update={"scripts": [s for s in M01.scripts if s.id != sid]})

        def before(events, cutoff=start_minute):
            return _dump([e for e in events if e.clock.minute < cutoff])

        assert before(MatchSim(M01, seed=3).run()) == before(MatchSim(without, seed=3).run())


def test_each_player_acts_for_their_own_team():
    code = {team.name: team.code for team in M01.teams.values()}
    for seed in (3, 4, 5):
        for e in MatchSim(M01, seed=seed).run():
            assert e.player_id is None or e.player_id.startswith(code[e.team] + "-"), e.event_id


def _close(p, q):
    return abs(p.x - q.x) <= 0.11 and abs(p.y - q.y) <= 0.11


def test_the_ball_moves_continuously_between_actions():
    """Each action starts where the ball is: kept, won (mirrored) or restarted.

    A set-piece taker is also the player who then plays the ball.
    """
    for seed in (3, 4, 5):
        owner, ball, taker = None, None, None
        for e in MatchSim(M01, seed=seed).run():
            if e.type == "set_piece":
                owner, ball, taker = e.team, e.start, e.player_id
            elif e.type in ("pressure", "foul"):  # by the defending team, at the mirrored ball
                assert e.team != owner, e.event_id
                assert _close(e.start, Point(x=105 - ball.x, y=68 - ball.y)), e.event_id
            elif e.type in ("tackle", "interception"):
                assert _close(e.start, Point(x=105 - ball.x, y=68 - ball.y)), e.event_id
                owner, ball, taker = e.team, e.start, None
            elif e.type in ("pass", "carry", "dribble", "shot"):
                assert e.team == owner and _close(e.start, ball), e.event_id
                assert taker is None or e.player_id == taker, e.event_id
                ball, taker = e.end, None


def test_a_ball_over_a_touchline_comes_back_as_a_throw_in():
    """Open play reflects off the touchlines; only a misplaced pass goes over one."""
    for seed in (3, 4, 5):
        play = [e for e in MatchSim(M01, seed=seed).run() if e.type != "sprint"]
        throw_ins = 0
        for prev, e in pairwise(play):
            over = prev.type == "pass" and prev.end.y in (0.0, 68.0)
            throw_in = e.type == "set_piece" and e.qualifiers["kind"] == "throw_in"
            assert over == throw_in, e.event_id
            if e.type in ("carry", "dribble"):
                assert 0.0 < e.end.y < 68.0, e.event_id  # carries turn back off a touchline
            if over:
                throw_ins += 1
                assert prev.outcome == "incomplete" and e.team != prev.team, e.event_id
                length = math.hypot(prev.end.x - prev.start.x, prev.end.y - prev.start.y)
                assert abs(prev.pass_q.distance_m - length) <= 0.2, prev.event_id
                line = 67.5 if prev.end.y == 0.0 else 0.5  # the same touchline, other frame
                assert _close(e.start, Point(x=105 - prev.end.x, y=line)), e.event_id
        assert throw_ins > 0
