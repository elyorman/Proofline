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
| `engine/` | Match Engine: synthetic matches from tactical scripts (`proofline-engine generate`) and the planted and decoy suites with sealed ground truth (`proofline-engine suite`); never imported by product code |
| `state/` | State Builder: the planted observables and the score as tool results, each with the evidence set it read, from events delivered by the case's clock |
| `detector/` | Moment Detector: CUSUM over each watched metric's change from the first half, thresholds tuned on the dev split ([`scripts/tune_detector.py`](scripts/tune_detector.py)) |
| `tools_server/` | Custom MCP server exposing the State Builder's tools to the agents |
| `agents/` | The Why Engine: agents pre-register predictions, code tests them through the MCP tools, the Verifier recomputes every number and checks every sentence ([`docs/support-rules.md`](docs/support-rules.md)) |
| `ledger/`, `orchestration/` | Feed ingest into the Cosmos ledger with live detection (`proofline ingest`); the Match Clock replays a match onto Event Hubs (`proofline-engine clock`) |
| `DATASET.md` | The synthetic dataset: the demo match, the stated rule that picks its seed, and how each planted story is checked for visibility in a single match |
| `infra/` | Bicep for every Azure resource, deployed with `azd` |
| `docs/spec.md` | Product spec |
| `docs/*.schema.json` | Exported JSON Schemas |
| `docs/azure-mcp.md` | Transcripts of Azure MCP Server use during the build |
| `scripts/check_engine_isolation.py` | CI guard: product code (including `surfaces/api/`) never imports the match engine or reads ground truth |

## Microsoft technology

| Technology | Where it lives | Evidence |
|---|---|---|
| Microsoft Foundry | [`infra/resources.bicep`](infra/resources.bicep): the Foundry project, `gpt-5-mini` for the agents and for the Verifier's semantic check, which sees only the card's facts and code-written sentences ([`agents/verifier/semantic.py`](agents/verifier/semantic.py)); Phi-4, the earlier Verifier, falsely rejected more sound cards on the seeded suite | Deployments verified in [`docs/azure-mcp.md`](docs/azure-mcp.md); recorded agent and verifier exchanges in [`tests/fixtures/cases/`](tests/fixtures/cases/) |
| Microsoft Agent Framework | [`orchestration/workflow.py`](orchestration/workflow.py): the Why Engine as a workflow (three domain agents in parallel → code tests → cross-examination in parallel → synthesis), checkpointed after every stage, an agent that stops retried from its checkpoint; [`agents/llm.py`](agents/llm.py): every model call through an Agent Framework agent on the Foundry chat client, with Entra ID | [`tests/test_why_engine_workflow.py`](tests/test_why_engine_workflow.py) replays the demo's verified 63' card and exercises recovery; `proofline case --variant A --kill-agent physical` shows it live |
| Custom MCP server | [`tools_server/server.py`](tools_server/server.py): `metric`, `baseline` and `game_state` over the State Builder | [`tests/test_tools_server.py`](tests/test_tools_server.py): calls through the server, refusals for minutes that have not happened |
| Azure MCP Server | Read-only server used to verify every deployment | [`docs/azure-mcp.md`](docs/azure-mcp.md) |
| Cosmos DB, Event Hubs, Container Apps, Container Registry, Web PubSub, Static Web Apps, App Insights, Key Vault | [`infra/resources.bicep`](infra/resources.bicep), all key-less: local auth disabled, access by managed identity and role; [`engine/clock.py`](engine/clock.py) and [`ledger/`](ledger/) stream a match through Event Hubs into the Cosmos ledger | Resource and role listings, and the demo match's events and 63' case read back from Cosmos, in [`docs/azure-mcp.md`](docs/azure-mcp.md) |
| azd, Bicep, GitHub Actions | [`azure.yaml`](azure.yaml), [`infra/`](infra/), [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | One-command `azd up`; CI runs lint, tests, the isolation guard and a schema check |

## Licence

MIT.
