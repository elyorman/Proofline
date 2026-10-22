"""Match totals stay within typical top-flight ranges (spec §7.3 realism controls).

Seeds 100-139 are held out: none of them were used to tune the engine's constants.
"""

import statistics
from collections import Counter
from pathlib import Path

from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
BASE = load_script(M01_PATH).model_copy(update={"scripts": []})


def test_totals_per_team_are_realistic():
    passes, completion, shots, goals, shot_x, shot_dist = [], [], [], [], [], []
    throw_ins, on_ball_y = [], []
    for seed in range(100, 140):
        events = MatchSim(BASE, seed=seed).run()
        match_shots = [e for e in events if e.type == "shot"]
        shot_x += [round(e.start.x) for e in match_shots]
        shot_dist += [e.shot_q.distance_m for e in match_shots]
        throw_ins.append(
            sum(e.type == "set_piece" and e.qualifiers["kind"] == "throw_in" for e in events)
        )
        on_ball_y += [e.start.y for e in events if e.type in ("pass", "carry", "dribble")]
        for team in ("Harbour City", "Northvale"):
            team_passes = [e for e in events if e.type == "pass" and e.team == team]
            passes.append(len(team_passes))
            completion.append(sum(p.outcome == "complete" for p in team_passes) / len(team_passes))
            shots.append(sum(e.type == "shot" and e.team == team for e in events))
            goals.append(sum(e.type == "goal" and e.team == team for e in events))
    assert 400 <= statistics.mean(passes) <= 600
    assert 0.75 <= statistics.mean(completion) <= 0.86
    assert 10 <= statistics.mean(shots) <= 17
    assert 2.4 <= 2 * statistics.mean(goals) <= 3.3
    assert 15 <= statistics.mean(shot_dist) <= 21
    # Open play must not pile up on one line: no single metre of x holds 15% of shots,
    assert Counter(shot_x).most_common(1)[0][1] / len(shot_x) < 0.15
    # no 2 m strip of the width holds 8% of on-ball actions, and neither wide third of
    # the width is starved.
    strips = Counter(int(y // 2) for y in on_ball_y)
    assert max(strips.values()) / len(on_ball_y) < 0.08
    for wide in (sum(y < 68 / 3 for y in on_ball_y), sum(y > 68 * 2 / 3 for y in on_ball_y)):
        assert wide / len(on_ball_y) >= 0.25
    assert 30 <= statistics.mean(throw_ins) <= 55
