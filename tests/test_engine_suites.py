import re
from pathlib import Path

import pytest
import yaml

from contracts.eval_run import SEED_RANGES, FlagSet, Split
from contracts.planted import CAUSE_OBSERVABLES, GroundTruth, PlantedTruth
from contracts.taxonomy import Cause
from engine.paired import LATEST_START
from engine.script import load_script
from engine.sim import MatchSim
from engine.suite_builder import DECOY_OFFSET, FAIR_LEAD, decoys, dump_script, planted, write

ROOT = Path(__file__).resolve().parents[1] / "engine" / "suites"
M01 = load_script(ROOT.parent / "scripts" / "planted" / "m01.yaml")
OPAQUE_ID = re.compile(r"m\d{3}")


def _load(tmp_path, text):
    path = tmp_path / "script.yaml"
    path.write_text(text, encoding="utf-8")
    return load_script(path)


def _check_planted(events, truth: PlantedTruth, started):
    """The record matches what the engine does, and the score gives no other fair answer
    from the start of the change to the end of its window."""
    assert started == truth.started and truth.started <= LATEST_START, truth.match_id
    goals = [e for e in events if e.type == "goal" and e.clock <= truth.window.end]
    signed = [1 if g.team == truth.team else -1 for g in goals]
    leads = [sum(signed[: i + 1]) for i, g in enumerate(goals) if truth.started <= g.clock]
    leads.append(sum(s for s, g in zip(signed, goals, strict=True) if g.clock < truth.started))
    fair = FAIR_LEAD.get(truth.cause, lambda lead: True)
    assert all(fair(lead) for lead in leads), (truth.match_id, leads)


def test_a_small_planted_suite_plants_every_class_unambiguously(tmp_path):
    built = planted(Split.DEV, per_class=1, pairs=20, processes=4)
    assert {t.cause for t in built.truth.entries} == set(CAUSE_OBSERVABLES)
    for script, truth in zip(built.scripts, built.truth.entries, strict=True):
        text = dump_script(script)
        # The script names a mechanism, never the class it stands for, and its id is opaque.
        assert truth.cause.value.split(".")[1] not in text
        assert OPAQUE_ID.fullmatch(script.match_id)
        sim = MatchSim(_load(tmp_path, text))
        _check_planted(sim.run(), truth, sim.params.started["s1"])
    seeds = [s.seed for s in built.scripts]
    assert len(set(seeds)) == len(seeds)
    assert all(s - SEED_RANGES[Split.DEV].start < DECOY_OFFSET for s in seeds)
    assert built.flags.match_ids == [s.match_id for s in built.scripts]
    out = write(built, tmp_path)
    names = sorted(p.name for p in out.iterdir())
    assert names == ["ground_truth.yaml", "ground_truth_flags.json", "scripts"]
    reread = GroundTruth.model_validate(yaml.safe_load((out / "ground_truth.yaml").read_text()))
    assert reread == built.truth


def test_decoys_plant_nothing_and_a_rebuild_replaces_the_suite(tmp_path):
    out = write(decoys(Split.DEV, count=3), tmp_path)
    built = decoys(Split.DEV, count=2)
    assert [t.cause for t in built.truth.entries] == [Cause.NONE, Cause.NONE]
    assert all(s.scripts == [] and OPAQUE_ID.fullmatch(s.match_id) for s in built.scripts)
    write(built, tmp_path)
    assert {p.stem for p in (out / "scripts").glob("*.yaml")} == {s.match_id for s in built.scripts}


def test_decoys_start_in_every_style_the_planted_matches_do():
    presses = [t.press_height for s in decoys(Split.HELDOUT).scripts for t in s.teams.values()]
    assert min(presses) < 0.4 and max(presses) > 0.6  # a low and a high press, not just mid


def test_suite_sizes_are_bounded():
    with pytest.raises(ValueError, match="holds 1 to"):
        decoys(Split.DEV, count=0)
    with pytest.raises(ValueError, match="holds 1 to"):
        planted(Split.DEV, per_class=40)


def test_a_script_with_amendments_is_not_written_without_them():
    with pytest.raises(ValueError, match="amendments are not written yet"):
        dump_script(M01)


def test_the_committed_suites_are_consistent():
    ids, seeds = [], []
    for truth_path in sorted(ROOT.glob("*/*/ground_truth.yaml")):
        truth = GroundTruth.model_validate(yaml.safe_load(truth_path.read_text(encoding="utf-8")))
        scripts = {p.stem: load_script(p) for p in (truth_path.parent / "scripts").glob("*.yaml")}
        assert set(scripts) == {e.match_id for e in truth.entries}, truth_path
        flags_path = truth_path.with_name("ground_truth_flags.json")
        if flags_path.exists():
            flags = FlagSet.model_validate_json(flags_path.read_text(encoding="utf-8"))
            assert flags.split == truth.split and set(flags.match_ids) == set(scripts)
        for entry in truth.entries:
            script = scripts[entry.match_id]
            assert script.seed in SEED_RANGES[truth.split], entry.match_id
            if entry.started is not None:
                sim = MatchSim(script)
                _check_planted(sim.run(), entry, sim.params.started[entry.script_id])
        ids += list(scripts)
        seeds += [s.seed for s in scripts.values()]
    # No id says which suite or split it is in, and every match has seeds of its own.
    assert ids and all(OPAQUE_ID.fullmatch(i) for i in ids)
    assert len(set(ids)) == len(ids) and len(set(seeds)) == len(seeds)
