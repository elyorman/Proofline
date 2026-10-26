# Proofline replay surfaces

The web app plays the complete recorded Studio ledger: verified cards, fast-lane
goals, case files, revisions, amendments and producer cues, plus the ambient
layer computed from the match's events. It starts paused at 68:00 with the
Studio profile, a Northvale fan following Ambrel, in the browser's language:
Spanish when `navigator.language` starts with `es`, otherwise English. The fan
companion, analyst console, broadcast studio and overlay share one replay clock,
shown in the sticky match header on every route, beside a small badge that says
this is a recorded replay with no live model calls. No runtime path calls a
model.

## Deep links

A URL can open any route at a clock, paused, and in a language:

| Link | Opens |
|---|---|
| `#/fan?t=68:00` | the press card landing on the fan view |
| `#/fan?t=70:00` | the flank card's withdrawal leading the fan view |
| `#/analyst?t=68:00` | the 63' case file on the console |
| `#/fan?t=68:00&lang=en` | the same in English (`lang` is `en` or `es`) |
| `#/overlay?t=70:25` | the withdrawal cue's slot on the overlay |

`t` takes every clock form the match uses (`70:00`, `45+2:10`, `90+3`, or a bare
minute). A first-half clock never spills into the second half, a clock past the
final whistle opens full time, and an unreadable `t` or `lang` is ignored. A link
without `lang` opens in the browser's language.
Navigating between routes keeps the current clock.

## Run and regenerate

Use the Python environment in this worktree. From the repository root:

```bash
uv sync
uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/
uv run proofline run --mode studio --match m01 --replay tests/fixtures/studio/m01
# the three agents' side of the comparison is the Studio take's own 63' case file
uv run python -c "import json; d = json.load(open('runs/studio/m01/ledger.json')); f = next(f for f in d['case_files'] if f['case']['case_id'] == 'case-m01-063-pressure_shift'); open('runs/case-m01-063-pressure_shift-A.json', 'w').write(json.dumps(f, indent=2) + '\n')"
uv run proofline case --match m01 --minute 63 --variant B --replay tests/fixtures/cases/m01-063-B
uv run python surfaces/web/scripts/export_web_replay.py \
  --source data/m01 --match m01 --out surfaces/web/public/fixtures/m01 \
  --studio-ledger runs/studio/m01/ledger.json \
  --answers tests/fixtures/questions/m01/A/answers.jsonl \
  --case-files runs/case-m01-063-pressure_shift-A.json runs/case-m01-063-pressure_shift-B.json
uv run python surfaces/web/scripts/export_scoreboard.py   # the evaluation tab, from eval/records
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
The exporter also runs `ambient/` over the same delivered events the pitch
draws and adds the validated `AmbientFeed` (`contracts/ambient.py`) under
`ambient`; the Python tests require it to equal a fresh computation from the
committed inputs. The generated event feed stays in ignored
`public/fixtures/m01/`; `data/`, `runs/`, browser screenshots and build output
are also ignored.

## The ambient layer

Spec 8.2's always-on layer, computed in Python by `ambient/` from events alone
and only formatted here. Every item carries the clock from which it is known,
and the app shows nothing before that clock. The rules travel with the feed, so
the numbers the UI states come from it.

- **Speed tags.** A sprint over 32 km/h or a shot over 110 km/h is tagged on the
  pitch with its speed. In m01 no shot reaches 110 km/h (the fastest is
  106.7), so only sprint tags appear.
- **Pass difficulty.** `50 × min(distance / 40 m, 1) + 50 × pressure on the
  passer`, from the pass's own qualifiers. Completed passes of 80 or more get a
  badge on the pitch and a ticker line.
- **Momentum strip.** Each minute, each side's attacking threat (a shot 3
  points, a completed pass, carry or dribble into the final third 1 point),
  summed with a two-minute half-life; the strip shows `(home − away) /
  max(home + away, 3)`, from −1 to +1. It restarts each half.
- **Control vs chaos.** Over the last five minutes of the half, on-ball actions
  per possession (`actions / (possession changes + 1)`): 10 or more reads
  control, 3 or fewer chaos. Fewer than 10 actions gives no reading. Harbour
  City's raised press after 58' pushes the m01 gauge to chaos.
- **Ticker.** Kick-off, goals with the score, shots with their speed, fouls, free
  kicks, cards, substitutions, half-time and full time, and standout passes,
  from the EN/ES templates in `ambient/i18n/`.

## Views and demo beats

- **Fan companion (`#/fan`).** The first screen holds the match header, the
  live pitch, the current card and the ambient strip; Ask, the ticker, the
  numbers and recent activity follow. On a phone the order is header, pitch,
  current card, ambient strip, earlier cards, then the rest. The pitch shows
  the last 25 seconds of play by both teams. Player Focus highlights the
  followed player's events and names them, and says when they last touched the
  ball; it never empties the pitch. Cards appear at `published_at`, falling
  back to `verified_at`. Cards with neither timestamp are withheld, including
  fast-lane records; detection time never publishes a card. The current card
  is the one whose current revision appeared last, with How we know at a
  glance: its first two recorded numbers against their baselines, and the
  causes ruled out. The other cards follow in their usual order, newest first,
  as compact rows that open to the same evidence. At 68:00 the press
  explanation leads; at 70:00 the flank card's withdrawal leads and the press
  explanation follows it untouched. All evidence and checks, rejected
  alternatives and the case file stay one tap away.
- **Ask Proofline (fan and console).** Rendered below each route's main
  content: under the first screen on the fan view, under the case list and
  investigation on the console. Five localized suggestion chips jump to
  the recorded question time. The response uses the narrator's locale, explains
  the premise in plain words, shows code's measured premise test and, when
  explained, the verified card with How we know, shown from the minute the
  question was asked. Rewinding hides a future answer.
- **Live questions.** A typed question no recording holds is sent to the live
  API (`src/live.ts`, `VITE_PROOFLINE_API` at build time, set by
  `make deploy-web`) at the replay's current second-half minute. The page polls
  the job and lists each stage as the API reports it (the Lead's premise, code's
  test, registration, tests, cross-examination, synthesis, the Verifier), with
  a timer beside them while the job is queued or running ("0:42 · usually 1–3
  min", counted from when the API admitted it; a `timer` role with
  `aria-live="off"`, so screen readers announce stages, not seconds), then renders the answer exactly like a recorded one. Each refusal (a viewer's
  share of the day, the day's budget, a question still running, a busy queue, an outage, a first-half clock) has its
  own localized message. Without an API configured, the page says so and sends
  nothing.
- **Investigation (`#/analyst`).** The case list and the investigation open the
  console; Evaluation is a tab. Select any recorded case, including the faded
  51-minute detection. Each investigation opens with a funnel tallied from its
  case file: the causes the specialists pre-registered, how many code's tests
  kept, the counter-tests' recorded results (held, weakened, refuted, and those
  refused or not measurable), and the outcome with its primary cause and the
  Verifier's verdict and support from the case's own card. It counts recorded
  verdicts and re-scores nothing; a faded case has no funnel. Confirmation, both
  teams' readings, agent columns,
  pre-registered predictions, test verdicts, refusals, directed counter-tests,
  synthesis and checkpoints come from its case file. Challenge buttons scroll
  to the target hypothesis. The tool-call log is collapsed initially. Overview,
  verification and history remain available; the flank's history includes the
  evidence diff, amendment a1 and its affected event IDs.
- **Same-moment comparison.** On the 63-minute case, Compare with one agent
  places the Studio take's own 63-minute case beside the single agent's
  recording of the same moment, clearly labelled as one recorded A/B pair. It
  does not claim a winner. The scoreboard link opens Evaluation, which renders
  `src/fixtures/scoreboard.json`, exported from `eval/records/`.
- **Broadcast (`#/broadcast`) and overlay (`#/overlay`).** The real withdrawal
  cue is pending at 70:25. Approve it to put its recorded fields on screen for
  eight seconds. Hold, approve and kill affect only the local browser session;
  rewinding removes later decisions. The four insight cues are recorded as
  expired because no eligible dead ball occurred in their slots. Their fields
  remain inspectable under Preview fields, explicitly separate from on-air
  output; no cue or airing time is fabricated.

All views were checked in Chrome at 1440×900 and with phone emulation at 360,
390 and 430 px, with no horizontal scroll. Check phone widths with device
emulation (DevTools, or the DevTools protocol's
`Emulation.setDeviceMetricsOverride`): headless Chrome's `--window-size=390,844`
renders a 500 px-wide viewport, its minimum window width, and crops it, which
looks like an overflow that a phone never shows.

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
read ignored `data/` or `runs/`; they also require the committed ambient feed to
equal `ambient/` over the freshly built match. Web tests cover clock and
verification guards, revisions, cue controls, localized questions, case-file
investigations, comparison pairing, deep links, the ambient strip and ticker
(nothing shown before its clock, EN and ES), the pitch (both teams, the followed
player, ambient tags, labels that never overlap) and the current card. No
dependencies were added.

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
- Trace URLs are not supplied; the UI shows the recorded trace identifier.
