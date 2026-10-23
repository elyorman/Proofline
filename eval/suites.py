"""Load a sealed suite and bind its scripts and answer key to a digest."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from contracts.eval_run import FlagSet, Split, Suite
from contracts.planted import GroundTruth


@dataclass(frozen=True)
class SuiteBundle:
    truth: GroundTruth
    flags: FlagSet | None
    digest: str


def load_suite(root: str | Path, suite: Suite | str, split: Split | str) -> SuiteBundle:
    suite, split = Suite(suite), Split(split)
    if suite not in (Suite.PLANTED, Suite.DECOYS):
        raise ValueError("the evaluator core scores planted and decoy suites")
    path = Path(root) / suite / split
    truth = GroundTruth.model_validate(
        yaml.safe_load((path / "ground_truth.yaml").read_text(encoding="utf-8"))
    )
    if (truth.suite, truth.split) != (suite, split):
        raise ValueError("the answer key belongs to a different suite or split")
    flags = None
    if suite == Suite.PLANTED:
        raw = json.loads((path / "ground_truth_flags.json").read_text(encoding="utf-8"))
        flags = FlagSet.model_validate(raw)
        if raw.get("flag_set_id") != flags.flag_set_id:
            raise ValueError("stored flag_set_id does not match its content")
        if flags.split != split or set(flags.match_ids) != {e.match_id for e in truth.entries}:
            raise ValueError("frozen flags do not cover the suite")
        entries = {e.match_id: e for e in truth.entries}
        for exclusion in flags.exclusions:
            entry = entries[exclusion.match_id]
            actual = [(o.metric, o.subject, o.direction) for o in exclusion.observables]
            expected = [(o.metric, o.subject, o.direction) for o in entry.observables]
            if exclusion.cause != entry.cause or actual != expected:
                raise ValueError("an exclusion must use its planted class's observables")
    scripts = sorted((path / "scripts").glob("*.yaml"))
    if {p.stem for p in scripts} != {e.match_id for e in truth.entries}:
        raise ValueError("scripts do not cover the suite")
    digest = hashlib.sha256()
    for artifact in [path / "ground_truth.yaml", *scripts]:
        digest.update(artifact.relative_to(path).as_posix().encode() + b"\0")
        digest.update(artifact.read_bytes() + b"\0")
    return SuiteBundle(truth, flags, digest.hexdigest())
