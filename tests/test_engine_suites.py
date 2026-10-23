from pathlib import Path

import yaml

from contracts.eval_run import FlagSet, Split
from contracts.planted import CAUSE_OBSERVABLES, GroundTruth
from contracts.taxonomy import Cause
from engine.script import load_script
from engine.sim import MatchSim
from engine.suite_builder import decoys, dump_script, planted, write

ROOT = Path(__file__).resolve().parents[1] / "engine" / "suites"


def _load(tmp_path, text):
    path = tmp_path / "script.yaml"
    path.write_text(text, encoding="utf-8")
    return load_script(path)


def test_a_small_planted_suite_plants_every_class_unambiguously(tmp_path):
    built = planted(Split.DEV, per_class=1, pairs=20, processes=4)
    assert {t.cause for t in built.truth.entries} == set(CAUSE_OBSERVABLES)
    for script, truth in zip(built.scripts, built.truth.entries, strict=True):
        text = dump_script(script)
        # The script and its match id name a mechanism, never the class it stands for.
        assert truth.cause.value.split(".")[1] not in text and "." not in script.match_id
        sim = MatchSim(_load(tmp_path, text))
        sim.run()
        assert sim.params.started["s1"] == truth.started
    assert built.flags.scripts == [s.match_id for s in built.scripts]
    out = write(built, tmp_path)
    names = sorted(p.name for p in out.iterdir())
    assert names == ["ground_truth.yaml", "ground_truth_flags.json", "scripts"]
    reread = GroundTruth.model_validate(yaml.safe_load((out / "ground_truth.yaml").read_text()))
    assert reread == built.truth


def test_decoys_plant_nothing():
    built = decoys(Split.DEV, count=2)
    assert [t.cause for t in built.truth.entries] == [Cause.NONE, Cause.NONE]
    assert all(s.scripts == [] for s in built.scripts)


def test_the_committed_suites_are_consistent():
    for truth_path in sorted(ROOT.glob("*/*/ground_truth.yaml")):
        truth = GroundTruth.model_validate(yaml.safe_load(truth_path.read_text(encoding="utf-8")))
        scripts = {p.stem: load_script(p) for p in (truth_path.parent / "scripts").glob("*.yaml")}
        assert set(scripts) == {e.match_id for e in truth.entries}, truth_path
        flags_path = truth_path.with_name("ground_truth_flags.json")
        if flags_path.exists():
            flags = FlagSet.model_validate_json(flags_path.read_text(encoding="utf-8"))
            assert flags.split == truth.split and set(flags.scripts) == set(scripts)
        first = truth.entries[0]
        if first.started is not None:  # the record matches what the engine does
            sim = MatchSim(scripts[first.match_id])
            sim.run()
            assert sim.params.started[first.script_id] == first.started
