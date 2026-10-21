"""Paired runs show each scripted mechanism moves its observable (spec §7.2)."""

import statistics
from pathlib import Path

from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)
SEEDS = range(20)


def _without(sid):
    return M01.model_copy(update={"scripts": [s for s in M01.scripts if s.id != sid]})


def _paired_ci(sid, observable):
    """Mean with-minus-without difference over seeds, with a normal 95% CI."""
    diffs = [
        observable(MatchSim(M01, seed=s).run()) - observable(MatchSim(_without(sid), seed=s).run())
        for s in SEEDS
    ]
    mean = statistics.mean(diffs)
    half = 1.96 * statistics.stdev(diffs) / len(diffs) ** 0.5
    return mean - half, mean + half


def _in(e, lo, hi):
    return lo <= e.clock.minute < hi


def hc_pressure_rate(events):
    """Harbour City pressures per Northvale action in Northvale's first 60%.

    A rate, not a count: a heavier press also shortens Northvale's time on the ball there.
    That zone is x < 63 in Northvale's frame and x > 42 in Harbour City's.
    """
    pressures = sum(
        e.type == "pressure" and e.team == "Harbour City" and e.start.x > 42 and _in(e, 62, 68)
        for e in events
    )
    actions = sum(
        e.type in ("pass", "carry", "dribble")
        and e.team == "Northvale"
        and e.start.x < 63
        and _in(e, 62, 68)
        for e in events
    )
    return pressures / actions


def nv_long_ball_share(events):
    passes = [e for e in events if e.type == "pass" and e.team == "Northvale" and _in(e, 62, 68)]
    return sum(p.pass_q.distance_m > 30 for p in passes) / len(passes)


def nv03_sprints(events):
    return sum(e.type == "sprint" and e.player_id == "NV-03" and _in(e, 66, 90) for e in events)


def test_raised_press_means_more_pressure():
    low, _ = _paired_ci("s1", hc_pressure_rate)
    assert low > 0


def test_raised_press_pushes_the_opponent_long():
    low, _ = _paired_ci("s1", nv_long_ball_share)
    assert low > 0


def test_stamina_decay_costs_sprints():
    _, high = _paired_ci("s2", nv03_sprints)
    assert high < 0
