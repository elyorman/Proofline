"""Write a generated match to disk: events.jsonl plus meta.json (`contracts.meta`).

Nothing here reveals the script's interventions, which stay in the YAML and the sealed
ground truth, or anything the events have not yet delivered: meta.json names the teams
and rosters only.
"""

from pathlib import Path

from contracts.event import Event, EventAmendment
from contracts.meta import MatchMeta
from engine.amend import first_delivered
from engine.sim import MatchSim


def _write(path: Path, text: str) -> None:
    """Write whole or not at all, so a reader never sees a truncated file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_match(sim: MatchSim, events: list[Event], out_dir: str | Path) -> Path:
    """Write the events as the feed first delivered them and, for a script with amendments,
    the batches that later correct them in amendments.jsonl, in the order they arrive."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    delivered, corrected = first_delivered(sim.script, events)
    _write(out / "events.jsonl", "".join(e.model_dump_json() + "\n" for e in delivered))
    _write(out / "meta.json", match_meta(sim).model_dump_json(indent=2) + "\n")
    batches = [
        EventAmendment(
            amendment_id=a.id,
            match_id=sim.script.match_id,
            at=a.at,
            event_ids=corrected[a.id],
            shift=a.batch.shift,
            reason=a.reason,
        )
        for a in sorted(sim.script.amendments, key=lambda a: a.at.sort_key)
    ]
    path = out / "amendments.jsonl"
    if batches:
        _write(path, "".join(b.model_dump_json() + "\n" for b in batches))
    else:
        path.unlink(missing_ok=True)
    return out


def match_meta(sim: MatchSim) -> MatchMeta:
    """The match's metadata as a feed states it before kick-off."""
    return MatchMeta(
        match_id=sim.script.match_id,
        teams={
            side: {
                "name": team.name,
                "code": team.code,
                "formation": team.formation,
                "players": [
                    {"player_id": p.player_id, "name": p.name, "role": p.role, "unit": p.unit}
                    for p in sim.lineups[side]
                ],
            }
            for side, team in sim.script.teams.items()
        },
    )


def read_meta(path: str | Path) -> MatchMeta:
    return MatchMeta.model_validate_json(Path(path).read_text(encoding="utf-8"))


def read_events(path: str | Path) -> list[Event]:
    with Path(path).open(encoding="utf-8") as f:
        return [Event.model_validate_json(line) for line in f if line.strip()]
