"""Match totals stay within typical top-flight ranges (spec §7.3 realism controls)."""

import statistics
from pathlib import Path

from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
BASE = load_script(M01_PATH).model_copy(update={"scripts": []})


def test_totals_per_team_are_realistic():
    passes, completion, shots, goals = [], [], [], []
    for seed in range(10):
        events = MatchSim(BASE, seed=seed).run()
        for team in ("Harbour City", "Northvale"):
            team_passes = [e for e in events if e.type == "pass" and e.team == team]
            passes.append(len(team_passes))
            completion.append(sum(p.outcome == "complete" for p in team_passes) / len(team_passes))
            shots.append(sum(e.type == "shot" and e.team == team for e in events))
            goals.append(sum(e.type == "goal" and e.team == team for e in events))
    assert 400 <= statistics.mean(passes) <= 600
    assert 0.74 <= statistics.mean(completion) <= 0.86
    assert 9 <= statistics.mean(shots) <= 18
    assert 1.8 <= 2 * statistics.mean(goals) <= 3.8
