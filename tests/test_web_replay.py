"""The web build exports an allowlisted manifest and explicit demo records."""

import json

import pytest

from contracts.card import InsightCard
from contracts.cue import Cue
from contracts.event import Event
from surfaces.web.scripts import export_web_replay


@pytest.mark.parametrize("legacy", [False, True])
def test_web_export_preserves_event_contracts_and_hides_engine_metadata(
    tmp_path, monkeypatch, legacy
):
    monkeypatch.setattr(export_web_replay, "WEB", tmp_path)
    (tmp_path / "src").mkdir()
    public = tmp_path / "public/fixtures/m01"
    public.mkdir(parents=True)
    (public / "match.json").write_text("{}")
    source = tmp_path / "source"
    source.mkdir()
    meta = dict(
        match_id="m01",
        teams={
            side: dict(
                name=name,
                code=code,
                formation="4-3-3",
                players=[
                    dict(
                        player_id=f"{code}-10",
                        name=f"{code} Player",
                        role="ST",
                        unit="attack",
                    )
                ],
            )
            for side, name, code in (("home", "Harbour City", "HC"), ("away", "Northvale", "NV"))
        },
    )
    if legacy:
        meta.update(seed=4434, score={"home": 99}, period_lengths_s={"1": 9999, "2": 9999})
    (source / "meta.json").write_text(json.dumps(meta))
    goal = Event.model_validate(
        dict(
            event_id="g1",
            match_id="m01",
            clock="00:55",
            wall_clock_ms=55000,
            type="goal",
            team="Harbour City",
        )
    )
    (source / "events.jsonl").write_text(goal.model_dump_json() + "\n")
    export_web_replay.export(source)
    manifest = json.loads((public / "meta.json").read_text())
    assert set(manifest) == {"match_id", "teams"}
    assert len(manifest["teams"]) == 2
    assert set(manifest["teams"]) == {"home", "away"}
    assert all(
        set(t) == {"name", "code", "formation", "players"} for t in manifest["teams"].values()
    )
    assert all(
        set(p) == {"player_id", "name", "role", "unit"}
        for t in manifest["teams"].values()
        for p in t["players"]
    )
    assert not (public / "match.json").exists()
    events = [
        Event.model_validate_json(line)
        for line in (public / "events.jsonl").read_text().splitlines()
    ]
    cards, cues = export_web_replay.demo_ledger(next(e for e in events if e.type == "goal"))
    assert all(InsightCard.model_validate(c.model_dump()) for c in cards)
    assert all(Cue.model_validate(c.model_dump()) for c in cues)
    original, withdrawal = [c for c in cards if c.id == "ins-m01-055-01"]
    assert original.status == "shown" and withdrawal.status == "withdrawn"
    assert original.revision == 1 and withdrawal.revision == 2
    assert withdrawal.verification.status == "rejected"
    assert all(c.provenance.trace_id.startswith("fixture-") for c in cards)
    assert all(c.provenance.foundry_eval_run is None for c in cards)
    assert all(
        c.verification.verifier_model_family == "fixture-only-no-model-run"
        for c in cards
        if c.verification
    )
    source = (tmp_path / "src/fixtures.ts").read_text()
    assert "Illustrative UI records, not agent output" in source
