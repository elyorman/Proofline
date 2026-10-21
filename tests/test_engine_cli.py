import json
from pathlib import Path

from engine.cli import main
from engine.io import read_events

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


def test_generate_writes_events_and_meta(tmp_path, capsys):
    assert main(["generate", "--script", str(M01), "--seed", "7", "--out", str(tmp_path)]) == 0
    events = read_events(tmp_path / "events.jsonl")
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["match_id"] == "m01" and meta["seed"] == 7
    assert len(meta["teams"]["home"]["players"]) == 11
    assert len(events) == meta["events"] > 2000
    assert "Harbour City" in capsys.readouterr().out
