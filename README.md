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
azd up        # provision every Azure resource into a new environment
```

## Repository

| Path | Purpose |
|---|---|
| `contracts/` | Pydantic schemas: event, card, proposition, prediction, cue, profile, taxonomy |
| `infra/` | Bicep for every Azure resource, deployed with `azd` |
| `docs/spec.md` | Product spec |
| `docs/*.schema.json` | Exported JSON Schemas |
| `docs/azure-mcp.md` | Transcripts of Azure MCP Server use during the build |
| `scripts/check_engine_isolation.py` | CI guard: product code (including `surfaces/api/`) never imports the match engine or reads ground truth |

## Microsoft technology

| Technology | Where it lives | Evidence |
|---|---|---|
| Microsoft Foundry | [`infra/resources.bicep`](infra/resources.bicep): Foundry project and the `gpt-5-mini` deployment | Deployment verified in [`docs/azure-mcp.md`](docs/azure-mcp.md) |
| Azure MCP Server | Read-only server used to verify every deployment | [`docs/azure-mcp.md`](docs/azure-mcp.md) |
| Cosmos DB, Event Hubs, Container Apps, Container Registry, Web PubSub, Static Web Apps, App Insights, Key Vault | [`infra/resources.bicep`](infra/resources.bicep), all key-less: local auth disabled, access by managed identity and role | Resource and role listings in [`docs/azure-mcp.md`](docs/azure-mcp.md) |
| azd, Bicep, GitHub Actions | [`azure.yaml`](azure.yaml), [`infra/`](infra/), [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | One-command `azd up`; CI runs lint, tests, the isolation guard and a schema check |

## Licence

MIT.
