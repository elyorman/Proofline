# Proofline

**Match intelligence that shows its evidence, knows its limits, and corrects itself.**

Proofline is a multi-agent match-intelligence engine for live football. It ingests a synthetic event feed, detects moments where the game shifts, and lets three specialist agents investigate and cross-examine competing explanations on a shared ledger. An independent verifier recomputes every number before anything reaches a fan, an analyst or a broadcast overlay, and every published claim is corrected or withdrawn when the data changes.

Built for the Microsoft × Premier League "Inside the Game" Developer Hackathon. Category: **Best Multi-Agent System**. All clubs, players and competitions are fictional.

> Status: scaffolding. The sections below fill in as each build gate is passed; see `docs/spec.md`.

## Quickstart

```bash
uv sync
uv run pytest
uv run python scripts/check_engine_isolation.py
```

## Repository

| Path | Purpose |
|---|---|
| `contracts/` | Pydantic schemas: event, card, proposition, prediction, cue, profile, taxonomy |
| `docs/spec.md` | Product spec |
| `docs/*.schema.json` | Exported JSON Schemas |
| `scripts/check_engine_isolation.py` | CI guard: product code (including `surfaces/api/`) never imports the match engine or reads ground truth |

## Licence

MIT.
