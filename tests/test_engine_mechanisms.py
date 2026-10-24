"""Paired runs show each scripted mechanism moves its observable (spec §7.2)."""

import statistics
from pathlib import Path

from engine.script import Intervention, load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)
# m01 no longer plants fatigue (one player's sprints cannot show it in a single match),
# so the stamina mechanism is checked on m01 plus a test-only intervention.
TIRED = M01.model_copy(
    update={
        "scripts": [
            *M01.scripts,
            Intervention.model_validate(
                {
                    "id": "s2",
                    "at": "62:00",
                    "ramp": "6m",
                    "team": "away",
                    "player": "NV-03",
                    "set": {"stamina_decay": 2.5},
                }
            ),
        ]
    }
)
SEEDS = range(20)


def _paired_ci(script, sid, observable):
    """Mean with-minus-without difference over seeds, with a normal 95% CI."""
    without = script.model_copy(update={"scripts": [s for s in script.scripts if s.id != sid]})
    diffs = [
        observable(MatchSim(script, seed=s).run()) - observable(MatchSim(without, seed=s).run())
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


def nv_unpressed_long_share(events):
    """Long-ball share of Northvale passes from their own 70 m that nobody pressed.

    Measured to full time: few passes qualify in a few minutes once the press is high.
    """
    passes = [
        e
        for e in events
        if e.type == "pass"
        and e.team == "Northvale"
        and e.start.x < 70
        and e.pass_q.pressure_on_passer == 0
        and _in(e, 62, 90)
    ]
    return sum(p.pass_q.distance_m > 30 for p in passes) / len(passes)


def hc_sprints(events):
    return sum(e.type == "sprint" and e.team == "Harbour City" and _in(e, 62, 68) for e in events)


def nv03_sprints(events):
    return sum(e.type == "sprint" and e.player_id == "NV-03" and _in(e, 66, 90) for e in events)


def test_raised_press_means_more_pressure():
    low, _ = _paired_ci(M01, "s1", hc_pressure_rate)
    assert low > 0


def test_raised_press_pushes_the_opponent_long():
    low, _ = _paired_ci(M01, "s1", nv_long_ball_share)
    assert low > 0


def test_a_high_press_is_bypassed_with_long_balls():
    low, _ = _paired_ci(M01, "s1", nv_unpressed_long_share)
    assert low > 0


def test_a_raised_press_is_run_with_more_sprints():
    low, _ = _paired_ci(M01, "s1", hc_sprints)
    assert low > 0


def test_stamina_decay_costs_sprints():
    _, high = _paired_ci(TIRED, "s2", nv03_sprints)
    assert high < 0
