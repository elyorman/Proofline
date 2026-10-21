"""Write a generated match to disk: events.jsonl plus meta.json (rosters, score).

Nothing here reveals the script's interventions; those stay in the YAML and the
sealed ground truth.
"""

import json
from pathlib import Path

from contracts.event import Event
from engine.sim import MatchSim


def write_match(sim: MatchSim, events: list[Event], out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "events.jsonl").open("w", encoding="utf-8") as f:
        for event in events:
            f.write(event.model_dump_json() + "\n")
    meta = {
        "match_id": sim.script.match_id,
        "seed": sim.seed,
        "teams": {
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
        "period_lengths_s": sim.period_lengths,
        "score": sim.score,
        "events": len(events),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return out


def read_events(path: str | Path) -> list[Event]:
    with Path(path).open(encoding="utf-8") as f:
        return [Event.model_validate_json(line) for line in f if line.strip()]
