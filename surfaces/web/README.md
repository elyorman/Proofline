# Proofline replay surfaces

The web app plays the complete recorded Studio ledger: verified cards, fast-lane
goals, case files, revisions, amendments and producer cues. It starts paused at
68:00 with the Studio profile: a Northvale fan reading Spanish and following
Ambrel. The fan companion, analyst console, broadcast studio and overlay share
a replay clock. No runtime path calls a model.

## Run and regenerate

Use the Python environment in this worktree. From the repository root:

```bash
uv sync
uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/
uv run proofline run --mode studio --match m01 --replay tests/fixtures/studio/m01
uv run proofline case --match m01 --minute 63 --variant A --replay tests/fixtures/cases/m01-063-A
uv run proofline case --match m01 --minute 63 --variant B --replay tests/fixtures/cases/m01-063-B
uv run python surfaces/web/scripts/export_web_replay.py \
  --source data/m01 --match m01 --out surfaces/web/public/fixtures/m01 \
  --studio-ledger runs/studio/m01/ledger.json \
  --answers tests/fixtures/questions/m01/A/answers.jsonl \
  --case-files runs/case-m01-063-pressure_shift-A.json runs/case-m01-063-pressure_shift-B.json
cd surfaces/web
corepack pnpm install --frozen-lockfile
corepack pnpm types
corepack pnpm dev
```

`corepack pnpm fixtures`, from `surfaces/web/`, repeats the engine, Studio, A/B
case and export commands above. Every agent command uses `--replay`.
`PROOFLINE_PYTHON=/absolute/path/to/this/worktree/.venv/bin/python` optionally
selects the environment; imports still resolve to this checkout. Regeneration
preserves recorded content; trace IDs and checkpoint wall times vary by run.

The five answers are imported from the committed canonical JSONL. To reproduce
them from recorded exchanges, from the repository root:

```bash
uv run proofline questions --data data \
  --questions tests/fixtures/questions/m01/questions.jsonl --variant A \
  --out runs/q-m01 --replay tests/fixtures/questions/m01/exchanges-A
```

The exporter writes `src/fixtures/ledger.json`, keeping backend payloads
unchanged after contract validation. `--ledger PATH` selects another output.
`--answers PATH` imports validated `Answer` JSONL; `--case-files PATH...` imports
validated comparison case files. `--cards PATH...` supports individual cards
instead of a Studio ledger, without inventing any other records. The
`stand_ins` index is empty: all demo records now have real backend producers.
The generated event feed stays in ignored `public/fixtures/m01/`; `data/`,
`runs/`, browser screenshots and build output are also ignored.

## Views and demo beats

- **Fan companion (`#/fan`).** Cards appear at `published_at`, falling back to
  `verified_at`, then `detected_at` for fast-lane records. The 62:00 cards precede
  the 68:00 press explanation. At 70:00 the flank card becomes its withdrawal in
  the same position; the press explanation stays. How we know reveals supplied
  evidence, rejected alternatives and revision history.
- **Ask Proofline (fan and console).** Five localized suggestion chips jump to
  the recorded question time. The response uses the narrator's locale, explains
  the premise in plain words, shows code's measured premise test and, when
  explained, the verified card with How we know. Rewinding hides a future
  answer. An unknown typed question explicitly requires Run live, which is
  unavailable in this public replay. No request is sent.
- **Investigation (`#/analyst`).** Select any recorded case, including the faded
  51-minute detection. Confirmation, both teams' readings, agent columns,
  pre-registered predictions, test verdicts, refusals, directed counter-tests,
  synthesis and checkpoints come from its case file. Challenge buttons scroll
  to the target hypothesis. The tool-call log is collapsed initially. Overview,
  verification and history remain available; the flank's history includes the
  evidence diff, amendment a1 and its affected event IDs.
- **Same-moment comparison.** On the 63-minute case, Compare with one agent
  places the standalone A and B recordings beside each other, clearly labelled
  as one recorded A/B run. It does not replace the Studio take or claim a
  winner. The scoreboard link opens Evaluation, currently an honest empty state.
- **Broadcast (`#/broadcast`) and overlay (`#/overlay`).** The real withdrawal
  cue is pending at 70:25. Approve it to put its recorded fields on screen for
  eight seconds. Hold, approve and kill affect only the local browser session;
  rewinding removes later decisions. The four insight cues are recorded as
  expired because no eligible dead ball occurred in their slots. Their fields
  remain inspectable under Preview fields, explicitly separate from on-air
  output; no cue or airing time is fabricated.

All views were checked in Chrome at desktop and 360px widths. Local ignored
screenshots in `.artifacts/studio-*.png` capture the withdrawal, Spanish Ask,
investigation, A/B comparison, revision diff, correction cue and mobile layouts.

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

Python tests build a fresh match from committed inputs and replay Studio with
model calls forbidden. They validate committed records, compare the complete
Studio payload (excluding trace IDs and checkpoint wall times), verify the real
correction and exercise the answer/comparison export boundaries. Tests never
read ignored `data/` or `runs/`. Web tests cover clock and verification guards,
revisions, cue controls, localized questions, case-file investigations and
comparison pairing. No dependencies were added.

## Boundaries

- Metadata supplies only match ID and teams. Scores come from delivered goals;
  each half's length comes from its `period_end` event, including stoppage time.
- Statistical readings and verdicts are recorded backend values. The UI formats
  them and never computes an investigation statistic or counter-test result.
- Viewer copy is localized in English and Spanish. Free-form backend reasons
  and cue fields are displayed verbatim because they have no localized fields.
- Studio currently exports a plain correction-summary dict; the exporter uses
  a local strict boundary model. A shared backend contract would remove this
  duplicate definition.
- Cross-examination `result` is serialized by the backend but absent from its
  validation-mode JSON schema. The UI reads that recorded value through a typed
  extension; it does not derive a verdict. Exporting the serialization schema
  would make this explicit in generated TypeScript.
- Recovery shows the recorded flag and completed/failed agents per checkpoint.
  Case files do not identify successfully retried agents separately.
- Evaluation scores and trace URLs are not supplied. Their UI remains empty or
  shows the recorded identifier. Hosting, CI, backend and root docs are unchanged.
