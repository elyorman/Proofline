# CLAUDE.md — Proofline

Proofline is a multi-agent match-intelligence engine for live football, built solo for the Microsoft × Premier League "Inside the Game" hackathon. Submission closes 27 October 2026 11:59 pm Pacific; the public link must stay up through 10 November. The full spec is `docs/spec.md`; read it before any non-trivial change. This file is the operating manual for working in this repo.

## The one-line mission

Win Grand Prize and Best Multi-Agent by making every rubric clause visible in a two-minute video, a public link and the README. If a change does not move one of those three, it is not the next task.

## Non-negotiable rules

1. **LLMs never compute statistics.** Every number comes from a deterministic tool in `state/` and is recomputed by the Verifier. If you find yourself asking a model for a value, stop and add a tool.
2. **Product code never imports `engine/`** and never reads `engine/suites/**/ground_truth*.yaml`. CI enforces this (`scripts/check_engine_isolation.py`) across every package including `surfaces/api/`; do not weaken the check. Only `eval/` reads ground truth. The season-average baseline is a plain data file, `state/season_baselines.json`, generated once by the engine and committed.
3. **No fabricated evidence.** No GitHub Copilot PRs made for show; Copilot is claimed only where it did real work. No scoreboard numbers typed by hand; every number in the README comes from an `eval_runs` record. Every evaluation suite that runs is reported, including ones where the single agent matched.
4. **The video must match the product.** Any claim spoken in the demo must be supported by the scoreboard at recording time. The proof narration has two variants (`docs/demo-script.md`); pick after the ablation runs.
5. **Fictional everything.** Clubs, players, competition, kits, logos. Never reference a real club, league, player or broadcaster in code, data, UI copy, tests or commits. "Premier League" appears only in `README.md` to name the hackathon.
6. **Nothing reaches a surface without the Verifier.** Fast-lane templates are the only exception, and they contain only deterministic facts.
7. **Secrets live in Key Vault via managed identity.** No keys in code, `.env` committed, or Bicep parameters. Local dev uses `azd env` values and `DefaultAzureCredential`.
8. **Scope is frozen.** The out-of-scope list in `docs/spec.md §17` is not started under any circumstances. Free time goes to the Fan Companion, the video and the README.

## Repository map

```
contracts/      pydantic schemas: event, card, proposition, prediction, cue, profile, taxonomy — the source of truth; change these first, then everything downstream
engine/         Match Engine, scripts, suites, paired runs, clock. Never imported by product code.
state/          State Builder metrics (pure functions over events) + windows
ambient/        deterministic tags, momentum, gauge, ticker
tools_server/   MCP server exposing the State Builder catalog (never name a package `mcp`: it shadows the SDK)
detector/       Moment Detector (CUSUM-style change points)
agents/         tactics, physical, game_state, synthesis, verifier, narrator, director
orchestration/  Agent Framework workflows, pre-registration validation, budgets, checkpoints
corrections/    Correction Watcher + dependency index
ledger/         Cosmos DB models, change-feed handlers
eval/           Evaluator, matching rules, ablation B, seeded false claims, Foundry eval logging
surfaces/web/   Fan Companion, Analyst Console, overlay renderer (one SPA, three routes)
surfaces/api/   cue feed, profiles, "Why?" endpoint, run-live endpoint
infra/          Bicep + azd
docs/           spec.md, architecture.md, taxonomy.md, support-rules.md, demo-script.md, azure-mcp.md, copilot.md, schemas
```

## Stack and commands

- Python 3.12, `uv` for env and deps, `ruff` for lint/format, `pytest` for tests, `pydantic` v2 for contracts.
- Front end: Vite + React + TypeScript in `surfaces/web/`, `pnpm`.
- Infra: `azd` + Bicep. Region and env name live in `.azure/<env>/.env`, never in code.

```bash
uv sync                                   # install
uv run ruff check . && uv run ruff format --check .
uv run pytest -q                          # unit + contract tests
uv run python scripts/check_engine_isolation.py
uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/   # the script carries its seed
uv run proofline run --mode studio --match m01   # local pipeline against the deployed ledger
uv run proofline eval --suite planted,decoys,corrections --variant A,B --split heldout
azd up                                    # provision + deploy everything
azd env get-values                        # endpoints and resource names
pnpm --dir surfaces/web dev
```

Add a `Makefile` target for anything run more than twice.

## How to work

- **Contracts first.** A new field goes into `contracts/` with a test before any producer or consumer uses it. Coordinates are the truth and zones are derived; the primary cause lives only in the primary attribution proposition; tracking samples never go to Cosmos, only their per-window aggregates do. Schemas are exported to `docs/*.schema.json` by `scripts/export_schemas.py`; run it and commit the output.
- **Small, named commits.** One concern per commit, imperative subject, body says why. Commit messages must not reference real clubs or leagues. Commits are authored by the repository owner only: no `Co-Authored-By` or AI attribution trailers.
- **Tests for every deterministic layer.** `state/`, `detector/`, `corrections/`, the Verifier's deterministic checks and the Evaluator's matching rules get unit tests with hand-built event fixtures. Agents are tested with recorded tool results, never live model calls.
- **No live model calls in tests or CI.** Record fixtures in `tests/fixtures/` and replay.
- **Cost discipline.** Every role runs on gpt-5-mini, the only gpt-5 model with quota on our Free Trial subscription (gpt-5.6-terra and gpt-5.6-luna have none). A larger model is used only if we upgrade and get quota, set via `PROOFLINE_MODEL_TIER=final`; both ablation variants always use the same model. Role prompts and tool schemas are cached. Log tokens per case to App Insights; check `proofline cost --match <id>` after the first full match and update `docs/cost.md`.
- **Checkpoints are real.** Every Why Engine stage writes to `cases` before the next starts; the recovery path (kill an agent mid-case, resume from checkpoint, flag `recovered_from_checkpoint`) has a test and a `proofline demo kill-agent` command used in the video.
- **Replay is the public path.** The judging link serves recorded ledgers; "Run live" is rate-limited per viewer and per day and shares the same code path as replay. Never make the public link depend on a model call.
- **Localization.** All viewer-facing strings go through `narrator/` (model) or `ambient/i18n/` (templates). English and Spanish are required; never hard-code UI copy in components.
- **Observability.** Every case carries an OpenTelemetry trace ID and, once verified, a Foundry eval run ID; both are shown on the Analyst Console.

## Build order and gates

Work strictly in this order; a gate must hold before the next step starts.

1. Contracts; repo with CI and the isolation guard; `azd` skeleton; Foundry models deployed. **Gate: `azd up` from a clean clone.**
2. Match Engine (planted suite, paired runs, batch mode, realism report); State Builder incl. Rhythm; MCP server; Moment Detector. **Gate: a scripted match streams through Event Hubs into Cosmos and the detector fires on the planted moment.**
3. Why Engine as a single agent (= ablation B), then three agents, pre-registration, cross-examination, synthesis, checkpoint recovery; Verifier and support rules; Foundry-hosted semantic check; Evaluator on planted and decoy suites. **Gate: a verified card for the 63' pressure shift and a first A-vs-B number.** Fabric go/no-go decided here.
4. Event versions, Correction Watcher, dependency index, correction suite; Narrator EN/ES; Director; Fan Companion. **Gate: the correction beat runs end to end on the fan surface.**
5. Analyst Console (case file, Verifier panel, revision diff, scoreboard, ledger view, Ops panel via Azure MCP, recovery indicator); Broadcast cue feed, overlay renderer, approve/hold/kill, correction cues; dataset release via `gh release`. **Gate: all eight demo beats run in Studio mode unattended. Feature freeze.**
6. Frontend design pass; replay-backed public link; final eval and ablation B on the final-tier model; write the proof narration from measured numbers; record; README, pitch, testing instructions; submit. **Gate: video under two minutes, link tested from a phone and a clean browser, every spoken claim backed by the scoreboard.**

Kill switches when a gate fails are in `docs/spec.md §21`. Apply them; do not improvise new scope.

## Hero technology: leave evidence

Every Microsoft technology we use must leave something a judge can click or see. When you add one, add its row to the README table with a link into the code or a screenshot.

| Technology | Where it lives | Evidence |
|---|---|---|
| Microsoft Foundry | `agents/verifier/semantic.py` (hosted agent), `eval/foundry_evals.py`, tracing | eval run links on the console |
| Agent Framework | `orchestration/` | workflow diagram, recovery beat |
| Custom MCP server | `tools_server/` | tool-call log per hypothesis |
| Azure MCP Server | console Ops panel, `docs/azure-mcp.md` transcripts | panel in video |
| Event Hubs, Cosmos DB, Container Apps, Web PubSub, Static Web Apps, App Insights, Key Vault | `infra/`, `ledger/` | architecture diagram, ledger view, trace IDs |
| azd + Bicep + GitHub Actions | `infra/`, `.github/workflows/` | README badge, CI guard |
| GitHub CLI | release workflow publishing the dataset | release assets |
| Fabric RTI (stretch) | Eventstream → Eventhouse → Real-Time Dashboard | screenshot in README |

The README does not name the build tool. Do not claim GitHub Copilot unless it did real work.

## Definition of done for any feature

- Contract updated and exported; tests green; `ruff` clean; isolation guard passes.
- Visible on at least one surface or in the README.
- Works in replay mode without a live model call where applicable.
- Fictional names only; EN and ES strings present if viewer-facing.
- If it touches a demo beat, the beat still runs unattended in Studio mode.

## When unsure

Prefer the deterministic option, the smaller scope, the thing a judge can see, and the honest number. Ask before adding a dependency, a new Azure resource, or a new agent.
