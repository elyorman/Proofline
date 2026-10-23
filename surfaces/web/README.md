# Proofline replay surfaces

The fan and analyst views render the actual verified 63-minute card from a
recorded backend run. The producer view (`#/broadcast`) controls timed graphics;
`#/overlay` renders those graphics over the pitch without the producer queue.
All views share the replay clock, and English/Spanish UI catalogs have key parity.

## Run

From the repository root, with Python 3.12+, uv, Node 20+ and pnpm 10.11.0:

```bash
uv sync
uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/
uv run proofline case --match m01 --minute 63 --variant A --replay tests/fixtures/cases/m01-063-A
cd surfaces/web
corepack pnpm install --frozen-lockfile
corepack pnpm types
corepack pnpm fixtures
corepack pnpm dev
```

`pnpm fixtures` repeats the two recorded backend commands above, then exports the
feed and card. It never calls a model; every case command includes `--replay`.
`PROOFLINE_PYTHON=/absolute/path/to/venv/bin/python` optionally selects a Python
environment, while imports still resolve to this checkout. The runtime event
feed stays in ignored `public/fixtures/m01/`; `data/` and `runs/` are also ignored.

The app starts paused at the real card's display time (currently 63:00). Select
Español and open **Cómo lo sabemos** to see the supplied Spanish variant,
pressure-rate values and actual rejected alternatives. Data mode uses the
analyst variant. The analyst view includes propositions, attribution roles and
agents, evidence and baselines, tool-call references, investigation counts and
cross-examination, recovery status, verification checks, support/language level,
provenance, dependencies and revision reasons.

The **Overlay · 63:29** shortcut visits the first dead ball after the card. The
stand-in press cue waits **29 seconds** after 63:00 on m01 and uses the real card's
team, first evidence baseline/value and supplied casual variant. It airs for
8 seconds. Hold/approve/kill decisions affect only this browser session and are
shared between the producer and overlay routes. Rewinding discards later local
decisions; restart/reset clears them.

## Export other card files

From the repository root:

```bash
uv run python surfaces/web/scripts/export_web_replay.py \
  --source data/m01 --match m01 --out surfaces/web/public/fixtures/m01 \
  --cards runs/ins-m01-063-pressure_shift-A.json
```

`--cards` accepts multiple individual card JSON files. Each is validated as an
`InsightCard`, must belong to `--match`, and is stored unchanged in the committed
`src/fixtures/ledger.json`. `--ledger PATH` selects another ledger output, useful
for tests. The output folder is exactly `--out`. Scoreless matches are supported;
no goal card is invented when the feed contains no goal.

The ledger's separate `stand_ins` index identifies the authored 55-minute flank
note, its withdrawal, optional first-goal card and cues. These producers do not
exist in the backend yet. The exporter marks them as stand-ins in comments and
validates them against the public contracts. There is no hand-built pressure
card. The withdrawal demonstrates revision playback, not a real amendment run.

## Verification

From the repository root:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_engine_isolation.py
```

From `surfaces/web/`:

```bash
corepack pnpm test
corepack pnpm build
corepack pnpm preview
```

Python tests validate every committed card/cue and compare the pressure card with
a fresh backend replay, excluding only `provenance.trace_id`. The MCP server also
allocates transient tool identifiers; the comparison pins only that identifier
factory to the saved references. Metrics, recorded model answers, verification,
narration and returned cards are never patched. The test also checks that tool
requests are identical across the fresh runs. There are no live model calls.

Vitest covers display-time fallback, in-place withdrawals, metric formatting,
catalog fallback/parity, case-file fields, duplicate evidence references, shot
outcomes, cue-template selection and producer controls. Per-view error boundaries
keep the match controls and other views available if a view cannot render.

## Boundaries

- Metadata contains only `match_id` and team/roster fields. Scores use delivered
  goal events and half lengths use `period_end`, including stoppage time.
- Card text comes only from supplied `variants`; rejection and revision reasons
  are shown verbatim. The UI never invents a fatigue rejection or support level.
- Evidence numbers follow the narrator's units: long-ball and channel shares are
  percents, sprint speed has one decimal and km/h, other metrics have two decimals.
  Channel-share percentages extend the current backend narrator, which still
  formats those shares as decimals.
- The recorded card lacks a Director publication timestamp and broadcast cue, so
  display falls back to `detected_at` and the exporter supplies the marked cue.
- Raw tool arguments, full evidence sets, per-counter-test details and trace/eval
  URLs are not attached to the card. The UI shows only the fields and references
  it actually has. Evaluation remains an empty state; Run live remains disabled.
- Hash routes and relative assets support static hosting. No hosting, CI,
  backend files or cloud resources are changed here.
