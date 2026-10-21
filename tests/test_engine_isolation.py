"""The guard must catch engine imports anywhere in product code, including surfaces/api."""

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_engine_isolation.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_engine_isolation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_engine_isolation"] = module
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path) -> Path:
    for d in ("engine", "eval", "state", "surfaces/api", "docs"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "eval" / "score.py").write_text("from engine.suites import load\n")
    (tmp_path / "state" / "ppda.py").write_text("import math\n")
    return tmp_path


def test_clean_tree_passes(tmp_path):
    guard = _load()
    assert guard.scan(_repo(tmp_path)) == []


def test_surfaces_api_is_checked(tmp_path):
    guard = _load()
    repo = _repo(tmp_path)
    (repo / "surfaces" / "api" / "main.py").write_text("from engine.clock import Studio\n")
    found = guard.scan(repo)
    assert len(found) == 1 and "surfaces/api/main.py" in found[0]


def test_ground_truth_reference_is_caught(tmp_path):
    guard = _load()
    repo = _repo(tmp_path)
    (repo / "state" / "leak.py").write_text('p = "engine/suites/planted/ground_truth.yaml"\n')
    assert any("ground-truth" in v for v in guard.scan(repo))


def test_clone_location_does_not_hide_violations(tmp_path):
    guard = _load()
    repo = _repo(tmp_path / "data" / "Proofline")
    (repo / "state" / "leak.py").write_text("import engine.suites\n")
    assert len(guard.scan(repo)) == 1


def test_eval_is_exempt(tmp_path):
    guard = _load()
    assert guard.scan(_repo(tmp_path)) == []
