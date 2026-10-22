import hashlib
import json
from pathlib import Path

import pytest

from engine.cli import main
from engine.io import read_events
from engine.script import load_script
from engine.sim import MatchSim

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


def test_generate_round_trips_events_and_writes_meta(tmp_path, capsys):
    assert main(["generate", "--script", str(M01), "--seed", "7", "--out", str(tmp_path)]) == 0
    events = read_events(tmp_path / "events.jsonl")
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert events == MatchSim(load_script(M01), seed=7).run()
    assert meta["match_id"] == "m01" and meta["seed"] == 7 and meta["events"] == len(events)
    assert len(meta["teams"]["home"]["players"]) == 11
    assert "Harbour City" in capsys.readouterr().out


def test_meta_reveals_nothing_about_the_script(tmp_path):
    # Interventions are sealed ground truth; meta.json may carry only these keys.
    main(["generate", "--script", str(M01), "--out", str(tmp_path)])
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert set(meta) == {"match_id", "seed", "teams", "period_lengths_s", "score", "events"}
    for team in meta["teams"].values():
        assert set(team) == {"name", "code", "formation", "players"}


@pytest.mark.parametrize(
    "args", [["--script", "missing.yaml"], ["--script", str(M01), "--seed", "-3"]]
)
def test_bad_input_is_a_usage_error(tmp_path, capsys, args):
    with pytest.raises(SystemExit) as exit_info:
        main(["generate", *args, "--out", str(tmp_path)])
    assert exit_info.value.code == 2
    assert "proofline-engine" in capsys.readouterr().err


def test_the_demo_match_is_pinned(tmp_path, capsys):
    """The video's match. A change that moves it must update these lines on purpose."""
    main(["generate", "--script", str(M01), "--out", str(tmp_path)])
    out = capsys.readouterr().out.strip()
    assert out == "m01 seed 4434: 2963 events, Harbour City 2-3 Northvale"
    digest = hashlib.sha256((tmp_path / "events.jsonl").read_bytes()).hexdigest()
    assert digest == "fe4a2b2f7fac83443c3828ba3e22e893d31c99b7661f9939bec6804da3e45424"
