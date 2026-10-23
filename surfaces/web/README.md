# Proofline web shell

A local React + TypeScript SPA with three hash routes: `#/fan`, `#/analyst` and
`#/broadcast`. One replay clock drives the score, event locations, statistics,
insight revisions and overlay cues across all three views. English and Spanish
catalogs cover the UI; all clubs and players are fictional.

## Run locally

From the repository root, with Python 3.12+, uv, Node 20+ and pnpm 10.11.0:

```bash
uv sync --locked
cd surfaces/web
pnpm install --frozen-lockfile
pnpm types
pnpm fixtures
pnpm dev
```

The fixture command uses the repository's uv environment. To reuse another
existing virtual environment, set `PROOFLINE_PYTHON=/absolute/path/to/venv/bin/python`.
Generated match files stay in ignored `public/fixtures/m01/`; do not commit them.
The small generated contract types and illustrative ledger records under `src/`
are source artifacts. Regenerate them before testing when contracts change.

```bash
pnpm test
pnpm build
pnpm preview
```

If pnpm is supplied by Corepack, run these commands as `corepack pnpm ...` from
`surfaces/web/`, where `package.json` pins the package manager version.

## What the shell demonstrates

- Starts paused at 63:40. Play at 1×, 4× or 16×, seek backwards, or use moment
  shortcuts. Each half's length comes from its `period_end` event. First-half
  stoppage stays distinct from the second half.
- Scores, passes, accuracy, shots, pressures, the event feed and the ten-minute
  activity chart use only events delivered at the replay cutoff. Empty pass
  samples have no accuracy value. The chart shows action counts, not momentum.
- Pitch marks show actual event coordinates, with both axes mirrored for the
  away team. No invented tracking/formation positions or shot trajectories.
  Player Focus filters the event locations and counts recorded involvements.
- Insight records appear at their publication time. At 68:10 the sample flank
  record is replaced by its withdrawal; the analyst history retains revision 1.
  Seeking backwards restores the earlier state. The pressure record is unaffected.
- The broadcast view renders eight-second sample cues. Hold, approve and kill
  affect only the browser session; the decision log records match time. Rewinding
  discards decisions after the new cutoff. Restart/reset clears local decisions.
  The replay module also supports dead-ball slots using delivered event times.

## Data boundary and limitations

The build-only `scripts/fixtures.mjs` invokes the simulator CLI into temporary
storage. `scripts/export_web_replay.py` validates the exported events, cards and
cues with the Python contracts, then writes public fixtures. Both scripts live
under `surfaces/web/`. No Python code under the web surface imports the engine.

The browser consumes `meta.json` in the current feed shape: only `match_id` and
`teams` (home/away team and roster records). The exporter also accepts this older
branch's metadata and copies only those pre-match fields. It never copies the
seed, score or period lengths; the app never reads them. Scores come from goal
events up to the replay cutoff, and half lengths come from `period_end` events.
Keep generated runtime assets separate from the engine source when packaging a
future deployment.

The event feed is a genuine simulator export. The full-lane insight cards,
verification fields and correction cues are **authored illustrative fixtures**,
not results of agents, tool calls, a verifier or the Correction Watcher. The
exported event feed currently has no amendment stream; the withdrawal demonstrates
the ledger UI only. Every view labels this distinction. The first key-event card
uses a goal actually present in the exported feed.

Raw tool arguments, evidence sets, trace links, evaluations, live agents, durable
producer decisions, real profile services and APIs are not connected. Evaluation
is an empty state and Run live is disabled. This change prepares the frontend
boundary; it does not satisfy the backend build gates in `docs/spec.md`.

Hash routing works on static hosts without rewrite rules. Vite uses a relative
asset base. This shell is local work; no hosting or Azure resources are changed.
