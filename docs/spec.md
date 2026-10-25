# Proofline — Product Spec

**Match intelligence that shows its evidence, knows its limits, and corrects itself.**

> Scoped for the "Inside the Game" hackathon (submission 27 October, judging to 10 November). All clubs, players, competitions and brands are fictional. Working name; trademark check before the video.

---

## 1. Summary

Proofline is a multi-agent match-intelligence engine. It ingests a live stream of synthetic football events, detects moments where the game shifts, and lets three specialist agents investigate and cross-examine competing explanations on a shared ledger. An independent verifier recomputes every number before publication, and every published claim stays accountable: if later data no longer supports it, Proofline corrects or withdraws it on every surface that showed it.

One verified insight, three experiences:

| Surface | Audience | What they get |
|---|---|---|
| **Fan Companion** | Casual and core fans, any market | A live match view that is never empty (player tags, momentum, ticker), a few plain-language insight cards in their language, shaped around their club and player, and a "Why?" tap on anything |
| **Analyst Console** | Analysts, pundits, studio researchers | The full case file: pre-registered predictions, tool calls, cross-examination, rejected explanations, verification results, provenance for every number, revision history, and the ledger itself |
| **Broadcast Cue Feed** | Broadcast and streaming producers | Timed, machine-readable cues drawn as synchronized overlays, with approve, hold and kill controls and correction cues |

**Entry.** Grand Prize, plus category **Best Multi-Agent System**.

**Deliberately out of scope.** Scenario Author, blind set, out-of-vocabulary suite, calibration report, ablations C and D, rehearsal mode, delayed/dropped-event faults. Each would score under at most one judging criterion and none appears in a two-minute video. The effort goes to the fan surface, the video, and visible use of every hero technology, which together move four of the five criteria.

---

## 2. The problem

Football coverage has plenty of data and a growing amount of AI. What it lacks is explanation people can trust over the course of a match, delivered with restraint.

1. **Stats without the why.** Live stats, xG, win probability, automated graphics and archive Q&A are commodities. A credible live explanation of *why* the game changed, with context, is still the gap.
2. **Trust in generated narrative.** Fans report rising AI use but declining trust in AI-generated sports content, and rank accuracy above speed. Broadcast technologists name provenance, accuracy and reliable real-time behavior as barriers to AI on air.
3. **Claims don't stay accountable.** Live data gets amended. A claim that was right at 63' can be unsupported at 70'. Once shown, AI-generated claims are rarely tracked, corrected or withdrawn.
4. **Overload.** Casual and core fans watch differently, yet most data experiences are one-size-fits-all.

---

## 3. Product principles

1. **No unverified number reaches a viewer.** LLMs never compute statistics. Every number comes from a deterministic tool and is re-checked.
2. **Explain, don't just report.** Every insight names its primary cause, the evidence, and the alternatives it ruled out.
3. **Wording matches support.** Causal language is earned by the support level, never chosen by style.
4. **Show the receipts.** Provenance is a first-class field: full on the Analyst Console, one tap away for fans.
5. **Less, but better.** Each audience has an attention budget. Silence is a valid output.
6. **One truth, many voices.** Personalization changes framing, depth, language and timing, never the facts.
7. **Accountable over time.** Published claims are versioned, depend on specific evidence, and are corrected or withdrawn when that evidence changes. History is never erased.
8. **Measured, not claimed.** Attribution quality is scored against sealed ground truth and compared against a single-agent baseline. Numbers are published as measured.
9. **Every agent earns its place.** If a rule table could do the job, it is a tool, not an agent.
10. **Time is a first-class constraint.** Deterministic layers never wait on an LLM; insights are scheduled against the match clock.
11. **Visible by construction.** Every technology and every rubric clause maps to something a judge can see in the video, the public link or the README.

---

## 4. Users and jobs to be done

| User | Job | What they need |
|---|---|---|
| Casual fan | "Help me follow what's happening without homework." | A view that feels alive; two or three insights per half in plain language and their own language; their club and players at the centre |
| Core fan | "Show me the hidden game." | More metrics with meaning, Player Focus, "Why?" on anything that moves |
| Analyst / pundit | "Give me something I can say on air and defend." | Claims with numbers, baselines and sample sizes; rejected explanations; support levels; revision history |
| Broadcast producer | "Give me graphics I can trust, on time, without flooding the screen." | Timed machine-readable cues, approve/hold/kill, correction cues, audit trail, graceful degradation |

---

## 5. Insight Card

The Insight Card is the single unit of truth every surface renders. The example is the demo match's 63' card, with the numbers seed 4434 measures.

```json
{
  "id": "ins-m01-063-01",
  "revision": 1,
  "match_id": "m01",
  "case_id": "case-063-pressure",
  "origin": "auto",
  "lane": "full",
  "moment_type": "pressure_shift",
  "subject": { "team": "Harbour City", "players": [] },

  "timing": {
    "change_window": "58:00-63:00",
    "detected_at": "63:12",
    "verified_at": "63:31",
    "published_at": "63:40"
  },

  "case_outcome": "explained",

  "propositions": [
    { "id": "p1", "type": "change", "metric": "pressure_rate", "subject": "Harbour City",
      "direction": "up", "window": "58:00-63:00", "baseline": "first_half" },
    { "id": "p2", "type": "change", "metric": "long_ball_share", "subject": "Northvale",
      "direction": "up", "window": "58:00-63:00", "baseline": "first_half" },
    { "id": "p3", "type": "attribution", "cause": "tactical.press_intensity_up",
      "effect": "p2", "role": "primary", "hypothesis_id": "hyp-tactics-02", "agent": "tactics" },
    { "id": "p4", "type": "attribution", "cause": "game_state.chasing_result",
      "effect": "p1", "role": "secondary", "hypothesis_id": "hyp-gamestate-01", "agent": "game_state" }
  ],

  "claim": "Harbour City have raised their press since around the hour, and Northvale have started going long far more often.",

  "evidence": [
    { "metric": "pressure_rate", "subject": "Harbour City", "window": "58:00-63:00",
      "value": 0.83, "baseline": { "window": "first_half", "value": 0.32 },
      "n_events": 18, "tool_call_id": "tc-8841" },
    { "metric": "long_ball_share", "subject": "Northvale", "window": "58:00-63:00",
      "value": 0.59, "baseline": { "window": "first_half", "value": 0.11 },
      "n_events": 17, "tool_call_id": "tc-8842" }
  ],

  "depends_on": { "evidence_sets": ["es-tc-8841", "es-tc-8842"], "data_version": "feed-1" },

  "rejected_alternatives": [
    { "hypothesis_id": "hyp-physical-01", "taxonomy": "physical.unit_fatigue", "agent": "physical",
      "reason": "Harbour City's sprints fell too (-21%, against Northvale's -30% since the first half): the 9 points that single out Northvale are less than half the 20% fall the hypothesis claimed.",
      "rejected_by": "cross_examination", "tool_call_id": "tc-8850" }
  ],

  "investigation": {
    "agents": ["tactics", "physical", "game_state"],
    "preregistered_predictions": 4,
    "tool_calls": 11,
    "budget": 16,
    "cross_examination": "tactics refuted fatigue with a Harbour City control; physical challenged tactics; tactics held",
    "recovered_from_checkpoint": false
  },

  "verification": {
    "status": "passed",
    "recompute": "match",
    "baseline_check": "passed",
    "sample_size_check": "passed",
    "contradiction_check": "passed",
    "number_check": "passed",
    "semantic_check": "passed",
    "verifier_model_family": "family-b",
    "support_level": "moderate",
    "language_level": "measured",
    "rejection_reason": null
  },

  "salience": "high",

  "variants": {
    "casual": {
      "en": "Harbour City are pressing much higher now, and Northvale are going long far more often.",
      "es": "El Harbour City presiona mucho más arriba y el Northvale juega en largo mucho más a menudo."
    },
    "analyst": {
      "en": "Pressure rate 0.32 → 0.83 since 58'. Northvale long-ball share 11% → 59%. Consistent with the press disrupting their build-up. Fatigue ruled out: Harbour City's sprints fell almost as much. Support: moderate."
    }
  },

  "broadcast_cue": {
    "template": "pressure_shift_bar", "priority": "normal",
    "show_at": "next_dead_ball", "max_delay_s": 45, "duration_s": 8,
    "fields": { "team": "Harbour City", "headline": "PRESS RAISED",
      "stat_label": "Pressures per Northvale action", "before": 0.32, "after": 0.83 }
  },

  "revisions": [],
  "supersedes": null,
  "superseded_by": null,

  "provenance": { "trace_id": "otel-5f2c", "foundry_eval_run": "ev-2210-07" }
}
```

**Key fields**
- `case_outcome` — `explained`, `other` (real effect, cause outside the taxonomy) or `none` (no clear cause). A `none` card carries only change propositions and a templated claim; the fan surface renders it as a "No clear cause — normal variation" card with no model call.
- `propositions` — the structured claims. Semantic verification checks every sentence in every variant against these. The primary cause lives **only** here, as the attribution proposition with `role: primary`; the Evaluator, Verifier and Narrator all read it from the same place. No numeric shares.
- `support_level` — `strong`, `moderate` or `weak`, from deterministic rules (§9.2). `language_level` derives from it.
- `depends_on` — references to evidence sets. Each tool call stores the event IDs and versions it read once; a dependency index maps every event ID to the evidence sets and cards that used it, so the Correction Watcher finds dependents with one indexed lookup.
- `investigation.recovered_from_checkpoint` — true when an agent failed and the case resumed; shown on the console.
- `provenance` — the OpenTelemetry trace and the Foundry evaluation run, both linked from the console.

**Lifecycle**
`proposed → investigating → cross_examined → verified | rejected → scheduled → shown | expired | killed`
After `shown`: `→ revised` (still holds, numbers updated) or `→ withdrawn` (no longer supported).

---

## 6. System overview

```
 Match Engine ──► Match Clock ──► Event Hubs ──► State Builder ──► Ambient Layer ──────────┐
   (sealed ground truth ─────────────────────────────────────────────► Evaluator)          │
         └──(stretch) Fabric Eventstream ──► Eventhouse ──► Real-Time Dashboard             │
                                                   │                                        │
                                                   ▼                                        │
                                            Moment Detector ── key events ─► Fast Lane ──┐  │
                                                   │                                     │  │
                                                   ▼                                     │  │
                     Why Engine (Agent Framework): pre-register → test → cross-examine   │  │
                                      → synthesize, checkpointed per stage               │  │
                                                   │                                     │  │
                                                   ▼                                     │  │
                     Verifier: deterministic checks + semantic check (Foundry-hosted)     │  │
                                                   │                                     │  │
                                                   ▼                                     │  │
                                Narrator ─► Director ◄───────────────────────────────────┘  │
                                                   │                                        │
                       ┌───────────────────────────┼───────────────────────────┐            │
                       ▼                           ▼                           ▼            │
                Fan Companion              Analyst Console           Broadcast Cue Feed ◄──┘
                                           (+ Ops panel via Azure MCP)

 Correction Watcher: event amended → dependency index → re-verify → revise or withdraw → Director
 Shared state: Match Ledger (Cosmos DB) · change feeds trigger Director and Correction Watcher
 Push: Web PubSub · Traces: App Insights + OpenTelemetry · Evals: Foundry
```

Deterministic layers never wait on an LLM. The Why Engine is the only place agents reason. Nothing reaches a surface without the Verifier. Only the Evaluator reads the sealed ground truth.

---

## 7. Data and time

### 7.1 Match Engine

A stochastic possession-chain simulator for two fictional teams, with a lightweight positional model so events and player positions always agree. Pressing is sprint work: a team's off-ball sprints rise and fall with its press height as well as its players' energy (DATASET.md). Published as a downloadable dataset (§11.4).

**Event types:** pass, carry, dribble, shot, tackle, interception, clearance, pressure, duel, foul, card, substitution, possession change, set piece, goal, sprint, period start/end, event amendment.

**Every event carries:** `event_id`, `version`, `clock` (period, minute, second; first-half stoppage prints as `45+2:10`), `wall_clock`, `team`, `player_id`, `position`, start and end x/y on a 105×68 pitch, `outcome`, `body_part`, qualifiers. **Coordinates are the truth:** pitch zones are derived from x/y by the State Builder and never stored as input. Coordinates are in the attacking frame of the event's `team`: x=0 its own goal line, x=105 the opponent's; y=0 the left touchline and y=68 the right, looking towards the opponent's goal. A point in the other team's frame is (105 − x, 68 − y).
- Passes add `distance_m`, `ball_speed_kmh`, `pressure_on_passer` (0–1), `receiver_id`.
- Shots add `shot_speed_kmh`, `distance_m`, `angle_deg`, `defenders_in_cone`.
- Tracking samples at 5–10 Hz, in the player's own team frame: position, speed, cumulative distance. Tracking is **not written to Cosmos** (it would exceed the free tier at Studio speed); it lives in Blob or in memory per match and the State Builder reduces it to per-window `player_load` aggregates, which are what the ledger stores.

**Tactical scripts declare mechanisms, not labels.** Each change ramps in over a few minutes and every probability carries noise:

```yaml
# Demo match. Mechanisms only: which cause each intervention represents lives in
# the planted suite's sealed ground truth, never here.
match_id: m01
# Picked by the rule in DATASET.md, enforced by tests/test_engine_planted_signal.py: the
# first seed from 4417 up on which every planted observable changes by at least its
# median over validation seeds 100-139 and clears two natural standard deviations, and
# the corrected flank change does not clear them.
seed: 4434
teams:
  home: { name: "Harbour City", code: HC, formation: "4-3-3", press_height: 0.3 }
  away: { name: "Northvale", code: NV, formation: "4-2-3-1", press_height: 0.55 }

scripts:
  - id: s1
    at: "56:00"   # at full height by 58:00, so the 58-63' card window sees all of it
    ramp: "2m"
    team: home
    set: { press_height: 0.9 }

amendments:
  - id: a1
    at: "70:00"   # after the press card, confirmed at 68', so the demo shows a card withdrawn
    batch:
      # Northvale's on-ball events whose true start and end both lie in y 0-46;
      # the feed first showed them 22 m to the right.
      filter:
        types: [pass, carry, dribble]
        team: away
        window: "45:00-65:00"   # long enough to outlast the flank card's confirmation
        y_min: 0
        y_max: 46
      shift: { dy_m: -22 }
    reason: "provider coordinate recalibration"
```

For the demo match the sequence is: a smaller card about Northvale attacking down the right (`tactical.flank_overload`, **moderate** support: a weak card never reaches the casual demo fan, whose minimum language level is `measured`, so there would be no fan Update card to show) detected at 57' and published at 62', once confirmed; the press change detected at 63' and its card published at 68'; the amendment at 70' relocating Northvale's 45–65' passes, carries and dribbles; the flank card withdrawn; the press card re-checked and untouched. The demo match's seed is chosen by a stated rule (`DATASET.md`): the first seed from 4417 upwards on which, in that one match, every planted observable changes by at least its median over validation seeds 100–139 and clears two natural standard deviations, and the corrected flank change does not clear them. No evaluation or scoreboard number comes from it.

Amendments are **batches**, as real feed corrections usually are. A single amended event rarely moves a windowed metric enough to change a verdict, so the correction suite uses batch amendments and includes claims near their support boundary.

An intervention can also target a whole unit with a player parameter (`unit: defence`), and can wait for the score (`when: trailing` or `leading`): it then starts with the first possession from `at` in which the condition holds (after a goal, at the restart), and the engine records when it started.

The mapping from script to cause-taxonomy class (for example `s1 → tactical.press_intensity_up`, observable 56:00–64:00) lives in a sealed ground-truth file that no product package can read. A CI check enforces this.

### 7.2 Counterfactual paired runs

For every scripted match, the engine also runs the match **without each script**; the difference is the measured effect of that intervention.

- Random streams are keyed by **decision type and match-minute bucket** (`pass_choice@61`), so draws stay aligned after a script changes who has the ball. This reduces divergence; it cannot remove it.
- Effects are measured on **windowed aggregates** over the script's observable window, never event by event.
- Each script is estimated over **20–30 seed pairs**; the simulator uses no LLM, so this costs seconds.
- A script is `not_observable`, and excluded from recall (never from precision), when either rule below holds. The detector sees one match: a paired effect can clear zero and still be invisible in every match it happens in. Each class's observables, and the direction each moves when the class is present, are fixed in `DATASET.md` before any script of that class runs.
  - No observable of its class has a paired effect whose confidence interval clears zero in that observable's direction.
  - No observable of its class separates from natural variation by two standard deviations in its own direction. A match's change is the observable over the ground truth's observable window minus its value before the script (the first half, or the minutes before the script for one that starts before half-time). The natural change is the same quantity in the paired run without the script. Separation is the mean change minus the mean natural change, divided by the natural change's standard deviation across the script's paired-run seeds (`DATASET.md`, `engine/visibility.py`); it belongs to the script, never to an evaluated match.
- `not_observable` flags come from engine runs alone, on dev seeds while a script is designed and on held-out seeds for the reported scoreboard, and are frozen before either variant runs; both variants use the same flags. The scoreboard lists every excluded script with its class and each observable's separation and paired-effect interval, counts each excluded script once under the first rule it meets, and shows recall over all planted scripts beside the headline, all from `eval_runs` records.

Paired runs are an evaluation tool only. Live, agents reason from the single match.

### 7.3 Test suites

| Suite | Contents | Correct behavior | Status |
|---|---|---|---|
| Planted | One scripted cause per moment | Find it, in time, with the right class | Build |
| Decoys | Natural variance swings with no scripted cause | Stay silent or close the case as `none` | Build |
| Corrections | Amendments that remove support for a published claim, and amendments that don't | Withdraw or revise exactly the affected cards, leave the rest alone | Build |
| Confounded | Two causes overlapping in time | Attribute both, primary and secondary in a sensible order | Stretch: added if it is what opens the single-agent gap |

The planted suite plants the six classes the engine has a mechanism for (`contracts/planted.py`): press intensity up and down, chasing the result, protecting a lead, unit fatigue and player fatigue. Dev holds two matches per class and four decoys; held-out holds five per class and ten decoys. From the change's start to the end of its window, a press change is planted only where the score gives no game-state reason for it, and a score-triggered change only where the score that triggered it holds. Match ids name neither the cause nor the suite or split, and every planted change starts by 65:00, so its timing gives no class away. Block height, formation, flank, substitution and numerical-change causes are not planted; an agent may still name them, and precision counts it. `proofline-engine suite` builds both suites, sealed from product code.

**Realism controls:** seed, team quality ratings, noise on every probability, calibration of match totals (passes, completion rate, shots, goals) against typical top-flight ranges, and a realism report shipped with the dataset.

**Feed faults:** amended events only.

### 7.4 Match Clock and run modes

| Mode | Clock | Used for | How insights stay in sync |
|---|---|---|---|
| Replay | 1× | Public judging link | Surfaces replay a recorded ledger, clock running, no model calls. A rate-capped **Run live** button on the console runs one new case on real agents per viewer per minute, same code path |
| Studio | 4×, pipeline-paced | Demo video, quick runs | The clock drops to 1× while a case is in flight, then speeds up, so each insight lands at the right match minute |
| Batch | As fast as possible, no UI | Evaluation and ablation | Cases run concurrently; timing scored in match time |

**Latency budgets:** fast lane under 2 s; full lane p95 under 25 s from detection to verified card; correction re-verification under 10 s; broadcast cues within `max_delay_s` or they expire to the recap.

---

## 8. Analytics layer

### 8.1 Match State Builder

Pure analytics, exposed as MCP tools. Every call returns the value, window, event IDs and versions used, `n_events` and a `tool_call_id`, as a `ToolResult` whose required fields depend on the tool: `compare` adds the second window and an effect size, `shape`, `player_load` and `game_state` return named `values`, and `events` returns the events at their versions. A call that cannot compute a value (an empty window, a zero denominator, no sprints) says so in `insufficient_data` with its `n_events`, and carries no numbers; no tool result holds NaN or infinity.

| Metric | Definition | Status |
|---|---|---|
| PPDA | Opponent passes allowed per defensive action in the opponent's 60% of the pitch | Build |
| Press intensity | Pressure events per minute in the opponent half | Build |
| Pressure rate | A team's pressures in the opponent's first 60% of the pitch per opponent on-ball action there (passes, carries and dribbles starting at x < 63 in the opponent's frame); metric `pressure_rate` | Build |
| Long-ball share | Share of passes over 30 m | Build |
| Field tilt | Share of final-third touches per team | Build |
| Channel share | Share of a team's passes, carries and dribbles starting in the left, centre or right third of the 68 m width (left y < 22.67, right y > 45.33, in the team's own attacking frame); metrics `channel_share_left`, `channel_share_centre`, `channel_share_right` | Build |
| Pass accuracy | Completed / attempted, overall and under pressure | Build |
| Pass difficulty rating | 0–100 from distance, pressure on passer, angle, receiver marking, line-breaking | Build |
| xG | Shot-quality model over distance, angle, body part, defenders in cone | Build |
| Sprint count and high-intensity run rate | From sprint events and tracking, per player and unit; a count compared across windows of different lengths is a rate per minute of play, a half's length including its stoppage time | Build |
| Momentum | Exponentially weighted threat differential (xG plus final-third entries) | Build |
| Control vs chaos index | Composite of sequence length, turnover rate, duel frequency and transitions | Build |
| Rhythm | Actions per minute and its variance (named in the challenge) | Build |
| Average positions and line height | Mean positions and defensive line depth per window | Build |
| Ball and shot speed | From event qualifiers | Build |
| Possession share | Share of on-ball time | Stretch |
| Distance covered | Per player, cumulative | Stretch |

**MCP tool catalog** (general-purpose by design, so agents decide what to test):

| Tool | Purpose |
|---|---|
| `metric(name, subject, window)` | Any metric for a team, unit or player over a window |
| `compare(name, subject, window_a, window_b)` | Change between windows, with effect size and sample sizes |
| `baseline(name, subject, scope)` | First half, match so far, or synthetic season average (read from `state/season_baselines.json`, generated once by the engine in batch mode and committed as plain data; product code never reaches into `engine/`) |
| `events(filter, window)` | Raw events, with versions, for drill-down |
| `shape(team, window)` | Average positions, line height, width, compactness |
| `player_load(player, window)` | Sprints, high-intensity runs, distance, involvement |
| `game_state(at)` | Score, time, cards, substitutions, stakes |
| `distribution(name, subject, window)` | Normal variation: how far a metric moves from the first half to a second-half window in ordinary play, by subject level, window length and minute, from a synthetic season of 200 matches with nothing planted (`state/natural.py`, `state/season_baselines.json`). Every test reads its change in these standard deviations, so "unusual" is measured, never guessed |

### 8.2 Ambient Layer

Always-on and deterministic, so the fan view is never empty.
- Player name tags on the 2D pitch when a player is involved in play.
- Speed and distance tags when thresholds fire (sprint above 32 km/h, shot above 110 km/h).
- Momentum strip, control-vs-chaos gauge, pass difficulty badge on standout passes.
- Event ticker of templated, localized one-liners ("Goal — Diallo, 67'").

Every ambient element is tappable: "Why?" opens an on-demand case for that window, rate-limited per viewer.

### 8.3 Moment Detector

- Online change-point detection per metric (CUSUM-style, per-half baselines), hysteresis, minimum event count per window.
- Moment types: `pressure_shift`, `momentum_swing`, `control_to_chaos` / `chaos_to_control`, `shape_change`, `fatigue_signal`, `individual_spike`, `milestone`, `key_event` (goal, red card, penalty → fast lane).
- On-demand "Why?" reuses an existing case covering the window, or opens one with `origin: on_demand`.
- The detector will fire on decoys. Deciding that a swing has no clear cause is the Why Engine's job, and it is scored.

---

## 9. Reasoning layer

### 9.1 Why Engine

**Agents:** Tactics, Physical, Game-State, and a Lead for viewer questions. Each specialist gets a role prompt, the MCP tool catalog, the cause taxonomy, and an investigation budget (default 6 tool calls per agent, 16 per case, 20 s wall time).

**Statistics decides what is real; agents decide why** (principle 9). Whether a change is beyond normal variation is a measurement, so code makes it before any agent looks for a cause: a detected change must last (step 1), and a question's premise must hold (Questions, below). What a change means, which causes are worth considering, which evidence would tell them apart, and which survives are judgements, so agents make them, and code scores every one.

**Cause taxonomy** (scripts never use these names):

| Domain | Classes |
|---|---|
| Tactical | press_intensity_up, press_intensity_down, block_deeper, block_higher, formation_change, flank_overload |
| Physical | unit_fatigue, player_fatigue, fresh_legs_substitution |
| Game state | protecting_lead, chasing_result, numerical_change |
| Fallback | other (real effect, cause outside the taxonomy), none (no clear cause) |

**Structured pre-registration.** Before calling any tool, an agent writes each prediction to the ledger as a typed object. The orchestrator validates it and rejects vague predictions before testing starts.

```json
{
  "hypothesis_id": "hyp-physical-01",
  "taxonomy": "physical.unit_fatigue",
  "prediction": {
    "metric": "sprint_count",
    "subject": "Northvale",
    "window": "58:00-63:00",
    "compare_to": "first_half",
    "direction": "down",
    "threshold_kind": "relative",
    "min_change": 0.15
  }
}
```

Agents register in `sigma`: a change in standard deviations of normal variation (`distribution`), so a claim says how unusual it must be rather than guessing a metric's units; a claim under 1 sd is refused as ordinary play. Validation: metric exists, subject resolves, window and baseline are standard scopes, direction and threshold present. `threshold_kind` is `relative` (ratios and counts with a baseline well above zero), `absolute` (the metric's own units) or `sigma` (standard deviations from the `distribution` tool, the default for signed or near-zero metrics such as momentum); each metric has a pinned default, and an agent may switch to `absolute` or `sigma` but never to `relative` on a metric not pinned relative. Changes are signed: a prediction holds only when the change points the predicted way by at least `min_change`; a `flat` prediction holds when the change stays within `min_change` either way, which is how a counter-test says "no change". A hypothesis itself never predicts flat. The prediction is judged mechanically against the tool result (`Prediction.supported_by`), not by the agent.

**Protocol:**
1. **Confirm, then open.** The detector picks the most unusual window among many, so many changes it fires on are swings that fade. Five match minutes after it fires, code re-measures each trigger over those five minutes alone, events the detector never read: a change that moved its way by at least 1.5 sd, on at least half the events a card needs (the change itself can thin the window), is confirmed, and the case opens over its window run on to that minute. Otherwise it closes as `none` with no model asked. On the dev split this kept 10 of 18 detector cases in planted windows and none of the 10 in decoys or before a planted change. The card is ready when the change is confirmed.
2. **Pre-register** (agents in parallel). Each agent decides whether the case touches its domain and registers up to two hypotheses, each a cause in its own domain; `other` and `none` are synthesis outcomes, never hypotheses. An agent registers from the change it is asked to explain and the match's facts (score, sendings-off, substitutions), never from another number code has measured over the window, so a prediction cannot copy a reading it was shown. Challengers in step 4 see only the hypotheses and their results. A registration whose causes are all on one team's side is put back once ("a change in one team's numbers is often the other team's doing"), since a specialist left to itself looks only at the team the change is about; a second one-sided answer stands, so no cause is forced.
3. **Test.** Each agent spends its budget on tool calls of its choosing. Predictions are scored mechanically; failed hypotheses are discarded with the reason.
4. **Cross-examine.** Each surviving hypothesis goes to the other agents, who may each register and run one structured counter-test: a corollary or a control, in the claim's sigma units (flat and opposite counter-tests remain in the contract but are not offered, since normal variation is now measured directly). Before it runs, the orchestrator refuses a counter-test that cannot fairly contradict the hypothesis (`check_counter_test`). A counter-test on the hypothesis's own metric uses its threshold kind; if it predicts a move, the move is at least as large as the claim. A counter-test that moves the other way, or stays flat, keeps the hypothesis's subject (or a team it is a unit of, or a unit of it) and window and may change only the baseline; a flat one also needs a tolerance tighter than the claim. A counter-test that moves the same way is a control: the claim itself on a subject that is neither the hypothesis's subject, a team it is a unit of, nor a unit of it, with the same window, baseline and threshold. A counter-test on another metric is a corollary: something else the hypothesis's cause would move if it were real, over the same window and baseline, which the challenger names with its direction and threshold. It is how one specialist asks another's claim for the evidence that tells it apart from rival causes; agents are never given a table of what each cause moves. Code scores the result from the counter-test, not any agent: refuted when the counter-prediction holds; weakened when it reaches half its threshold (a flat one: when the change stays within twice its tolerance); holds otherwise. A corollary holds when it moved as predicted by its threshold, refutes when it moved the other way by as much, and weakens in between; one that holds on the primary cause joins the card's evidence. A control is scored on what it leaves of the hypothesis's own change, since another team tiring does not rule out a unit tiring more: the hypothesis holds if its claim still holds on its change minus the control's, is weakened if half of it does, and is refuted otherwise.
5. **Attribute.** A synthesis step ranks survivors into primary and secondary. Nothing survives: `none`. A real effect with no fitting class: `other`. Every agent failing is an error, never `none`.
6. **Propose.** The card, its propositions and the full trace go to the Verifier.
7. **Keep watching.** Over the card's window, two causes often fit the same change: a team pressing harder while behind may be pressing by design or chasing the result, and the evidence that tells them apart (here, whether the team also goes direct) only builds over the following minutes. So when survivors name another cause, or another team, than the primary (up to two of them, strongest first, are the **rivals**) and at least 10 minutes of the match remain, the case stays open (`agents/follow_up.py`). Before the card is verified, the agents that own the primary and each rival (in variant B, the single agent for each side) each pre-register one **decisive test** for the next 15 minutes, which nobody has seen: a metric its cause moves and the others' would leave at ordinary play (`up` or `down`), or one its cause leaves at ordinary play where the others' would move it (`flat`). Code refuses a test that is another side's own claim, another side's prediction, or the continuation of a change already beyond 1.5 sd over the card's window (every surviving cause fits what was seen), and puts it back once with why. Code fixes the bars: a move needs 1.5 sd, as a confirmation does, and ordinary play is within 1 sd, both against the first half. The card says it will be checked ("We'll check it against Harbour City chasing the result by 83'"), and the Verifier checks that sentence too. When those minutes are played, code measures every test: only the primary's holding **confirms** the card, only one rival's **overturns** it to that rival (which becomes primary, the old primary ruled out by its failed prediction), and anything else leaves it **unresolved**, saying it could be any of them. The result is a new revision, verified like any other (`contracts/card.py` `FollowUp`). A correction that revises a card before its follow-up settles drops the follow-up, which was set on the data the amendment corrected. The Evaluator scores both the first answer and the answer after follow-up (`--after-follow-up`), where an unresolved card claims no cause.

**Questions.** A viewer can ask anything about the match so far, in English or Spanish ("¿Por qué Northvale ya no presiona?"). A question carries an assumption, and a single model tends to accept it and find a reason. So the **Lead** states the question's premise as one measurable change since a minute (`contracts/question.py`) and registers no cause; code tests the premise over the viewer's own stretch of play, which nobody picked for being unusual, at the 1.5 sd a confirmation needs (2 sd turned away half the true premises on dev). A premise that does not hold is answered with what did happen ("Not beyond ordinary play: ...") and no specialist is asked. One that holds becomes a case with origin `question` and runs steps 2-7 above, with the same agents, Verifier and card; its follow-up predicts the 15 minutes after the question. In variant B the single agent frames its own question. `proofline ask` answers one; `proofline questions` answers a file of them.

**Orchestration:** a Microsoft Agent Framework workflow (parallel fan-out → cross-examination round → synthesis), with a checkpoint after each stage. A failed or timed-out agent is retried once from its stage's checkpoint, without re-running finished stages; if it still fails, the case completes with the remaining agents. Either way the case is flagged `recovered_from_checkpoint`, on the card and in the case file, and the checkpoint records why the agent failed. Checkpoints live for the run and are all written to the case file; a restarted process starts its open cases again. This path is exercised on purpose in the demo.

### 9.2 Verifier

An independent stage that sees only the propositions, claim text, variants and evidence references, never the agents' reasoning. The semantic check runs on Foundry through Agent Framework, on gpt-5-mini with its own prompt (it replaced Phi-4 after a measured comparison, §15); the deterministic checks run in code. It shares the agents' model but none of their context.

| Check | How | Model |
|---|---|---|
| Recompute | Each evidence number's tool call re-run over its evidence set at the recorded versions; exact match (below) | Deterministic |
| Baseline fairness | Comparison window must be a standard scope | Deterministic |
| Sample size | Minimum `n_events` per metric and window | Deterministic |
| Contradiction scan | Related metrics checked for an opposite-direction signal | Deterministic |
| Number check | Every number in every variant matches the evidence | Deterministic |
| Semantic entailment | Each sentence, in every language and headline, is entailed by the propositions at the allowed language level; flags overstatement | LLM on Foundry, the agents' model with its own prompt and none of their context; English at build, Spanish as stretch |

**Recompute, defined.** For each evidence number, the Verifier re-runs the tool call named by its `tool_call_id`, with the same arguments, over exactly the events in its evidence set at their recorded versions (never by re-querying the window or scope, which for `match_so_far` grows between the call and verification). The stored value must match exactly; rounding applies only to the number check on text. The Correction Watcher runs the same procedure at the amended versions. This proves each published number is what the tool computes from those events, not that the tool is correct; tool correctness comes from the `state/` unit tests. Evidence sets therefore record every event a tool read, including events it filtered out, so an amendment that moves events into a team or zone a tool filters on still reaches the dependency index.

**Support level** (deterministic rules):

| Support level | Rule | Language level | Allowed wording | Where shown |
|---|---|---|---|---|
| strong | Large effect, sample above 2× minimum, no counter-test weakened or refuted it, no contradictions | assertive | "is forcing", "has caused" | All surfaces |
| moderate | Clear effect, sample above minimum, survived or only weakened in cross-examination | measured | "is pushing", "looks like", "consistent with" | All surfaces |
| weak | Small effect or near-minimum sample, or weakened | tentative | "coincides with", "may be" | Analyst Console and core-fan mode |
| — | Anything less | not published | — | Analyst Console only |

Effect-size bands and minimum samples are pinned per metric in `docs/support-rules.md`, tuned on the dev split only.

**Outcomes:** `passed` (recompute matches and every check passed), `corrected` (every check passed or corrected, at least one corrected, none skipped; numbers or wording fixed then re-checked) or `rejected` (carries a `rejection_reason`, shown on the console). The contract refuses any other combination. The Evaluator injects seeded false claims to measure the catch rate. Foundry evaluations of groundedness and language quality were planned and are not built.

### 9.3 Narrator

Writes each variant from verified propositions only, at the card's language level.
- **Casual:** one sentence, no jargon, in the viewer's language, framed from their club's side.
- **Analyst:** compact and numeric, with baselines and the support level.
- **Broadcast fields:** headline and labels sized for a graphic.
- **Player Focus:** the same insight told through the followed player, when that player is in the evidence.
- **Update and withdrawal text** for corrections.
- **Recap:** full-time summary from current, verified revisions only.

Languages: English and Spanish. On any failed number or semantic check: regenerate once, then fall back to a template.

### 9.4 Director

Triggered by the Cosmos DB change feed whenever a card becomes verified, revised or withdrawn.

- **Ranking:** key events first; then salience; then relevance to the profile; then support level; then novelty; with a fatigue penalty for recent cards.
- **Attention budget:** casual about 3 cards per half; core fan about 6; analyst feed 10–15, console unlimited.
- **Phase gating:** broadcast cues wait for a dead ball; nothing interrupts an attack in the final third.
- **Expiry:** past `max_delay_s`, a card leaves live surfaces and goes to the recap.
- **Fast lane:** goals, red cards and penalties go out in under 2 s from deterministic facts and a localized template.
- **Human control:** producers approve, hold or kill any cue; every decision is logged.
- **Corrections:** withdrawals and revisions always pass the budget, to every surface that showed the original.

---

## 10. Corrections

Proofline's signature capability: a published claim stays accountable as the match evolves.

**Correction Watcher.** Listens on the Cosmos DB change feed for amended events (`version` > 1), usually a batch.

1. **Find dependents.** Look up each amended event ID in the dependency index.
2. **Re-verify.** Recompute the evidence at the new versions and re-run the Verifier.
3. **Decide:** still supported, same numbers → no action; still supported, numbers or support level changed → **revise**; no longer supported → **withdraw** and reopen the case.
4. **Propagate** to every surface that showed the card: fan Update card in place of the original; analyst revision diff with the amended events; broadcast pending cue cancelled, aired cue triggers a correction cue for approval.
5. **Preserve history.** Original revisions are immutable.

If the revise path slips, ship withdraw-only with full propagation; never ship propagation to fewer than three surfaces.

**Correction metrics:** dependents found (100%), correct revise/withdraw decisions, unaffected cards left alone, time from amendment to correction on screen.

---

## 11. Proof layer

### 11.1 Evaluator

**What it measures: intervention-attribution accuracy.** How reliably Proofline recovers planted simulator interventions, abstains when there is none, and corrects itself. It does not measure real-world causal accuracy, and the README says so.

**Matching rules**
- **Planted:** correct when the primary cause's class equals the ground-truth class, its window overlaps the observable window, and the direction matches. This is recall's rule: a card in time.
- **Precision:** a planted change runs from its start to full time (no script switches one off), so a published card is true when it names the planted class, team and direction anywhere after the change began, even after the observable window. Cards before it began, on another cause, team or direction, or on a decoy are false. The rule was fixed on 2026-10-24, before the runs it scores, and is the same for every variant.
- **Questions:** a true-premise question is right when its verified card names the planted class and team; a false-premise one when no cause is published. Every published cause that is not right is a false claim.
- **Decoys:** correct when nothing is published or the case closes as `none`.
- **Corrections:** correct when every affected card is revised or withdrawn appropriately and no unaffected card changes.
- **Confounded** (stretch): each ground-truth cause matched independently; headline number is both-found.
- Scripts marked `not_observable` (§7.2) are excluded from recall.

| Metric | Reported as |
|---|---|
| Planted cause recall (over scripts not marked `not_observable`, §7.2; exclusions and all-script recall beside it) | Point estimate with bootstrap 95% CI |
| Cause precision | Point estimate with bootstrap 95% CI |
| Decoy restraint | Point estimate with bootstrap 95% CI |
| Verifier catch rate (seeded false claims) | Point estimate with bootstrap 95% CI |
| Correction accuracy | Point estimate with bootstrap 95% CI |
| Numeric accuracy | Must be 100% |
| Time to insight | p50 / p95 in match minutes |
| Cards over budget | Must be 0 |
| Cost and latency | Per case and per match |

**Data splits.** A dev split (prompts, support bands, detector thresholds) and a held-out split (reporting only). Headline numbers come from the held-out split. Engine seeds are partitioned once: 0–79 tuned the engine; 100–139 check realism and visibility and set the demo-seed medians, so they are validation seeds; the demo match's seed is scanned from 4417 up; the evaluation suites draw dev seeds from 1000–1999 and held-out seeds from 2000–2999, which nothing else touches; the synthetic season behind normal variation draws 3000–3199. Football-specific scoring runs as custom Python evaluators logged to Foundry; groundedness and language quality run as Foundry evaluations.

### 11.2 Ablation

| Variant | What changes |
|---|---|
| A. Proofline | Full design |
| B. Single agent | One agent (role `single`, may register causes in any domain) with every tool and the same total budget. It cross-examines its own survivors with the same counter-tests, scored by the same code, so A's difference is independence: there the challenger has no stake in the cause it tests |
| C. No cross-examination | Parallel agents, straight to synthesis (stretch) |
| P. Plain agent | Question suite only: one model with the State Builder's tools over MCP and the same budget, asked the viewer's question directly, with none of Proofline's design (no premise check, no normal variation, no pre-registration, no cross-examination, no Verifier). It is what a single tool-using agent gives a viewer, so A and B against P measure the design, and A against B measures the extra agents (`agents/plain.py`) |

Same suites, same tools, same Verifier. B is built first in the dependency order and reported with CIs whichever way it falls. If B matches A on the planted suite, the confounded suite may be added with causes that require a second domain's counter-test, but **every suite run is reported, including those where B matched A**; no suite is dropped from the scoreboard because of its result. If no gap appears anywhere, the category case rests on cross-examination traces, corrections and recovery, and the README says the gap was not found.

### 11.3 Match Ledger

One Cosmos DB store, partitioned by `match_id`.

| Container | Holds |
|---|---|
| events | Events as received, every version kept |
| metrics | Metric snapshots per window, including `player_load` aggregates reduced from tracking |
| cases | Cases, status and stage checkpoints |
| hypotheses | Structured predictions, tests, cross-examination results |
| evidence_sets | Per tool call: the event IDs and versions it read, including events it filtered out; every tool returns a `ToolResult` that points at one |
| dependencies | Index from event ID to evidence sets and cards (partition key `event_id`) |
| cards | Insight Cards with all revisions |
| cues | Director schedules, cue log, correction cues |
| audit | Every agent action and human override |
| eval_runs | Evaluation and ablation results, each metric tagged with its suite, plus paired A-vs-B `VariantComparison` records; every README number comes from one of these records |

Change feeds on `cards` trigger the Director; on `events` the Correction Watcher. Director output reaches surfaces through Web PubSub. The ledger is browsable on the Analyst Console.

### 11.4 Published dataset

Synthetic data creation is the first bullet of the first judging criterion and the tie-breaker. The dataset ships as a GitHub release built by `gh release` in Actions:

- Two curated fixtures (the demo match and one more) as event streams with tracking, plus the planted, decoy and correction suites as scripts.
- `DATASET.md`: schema, script DSL, amendment format, paired-run method, the single-match visibility statistic with each class's observables and their directions, realism report with calibrated totals.
- A CLI: `proofline-engine generate --script <yaml> --seed <n>`.

---

## 12. Surfaces

### 12.1 Fan Companion (the broadcast-grade surface)
- Match view: 2D pitch, score, clock, Ambient Layer. This is the screen judges see first; it gets the frontend design pass.
- Insight cards at natural pauses, within budget, at the card's language level.
- "How we know": one sentence, two numbers with baselines, the support level and the rejected alternative.
- "Why?" on any ambient element.
- Modes: Casual, Data, Player Focus.
- Update and Withdrawal cards in place of corrected insights.
- Two curated fixtures; full-time recap screen.

### 12.2 Analyst Console
- Case timeline: open, explained, other, none, withdrawn, recovered.
- Case file: structured predictions, tool calls and results, cross-examination, winner, rejected alternatives.
- Verifier panel: every check, corrections, rejections, semantic flags, Foundry evaluation link.
- Revision history with diffs and the amended events behind them.
- Ledger view: browse containers for the current match.
- Ops panel: Cosmos and App Insights queried through **Azure MCP Server** (case throughput, latency, cost per case).
- Scoreboard tab: Evaluator results and Proofline vs single agent.
- **Run live** button (replay mode) with a visible daily budget.

### 12.3 Broadcast Cue Feed
- Machine-readable cues over WebSocket, plus an overlay renderer drawing them over the 2D pitch in time.
- Approve / hold / kill controls; correction cues for aired graphics; cue log with full provenance.

```json
{
  "cue_id": "cue-0412",
  "match_id": "m01",
  "insight_id": "ins-m01-063-01",
  "insight_revision": 1,
  "kind": "insight",
  "template": "pressure_shift_bar",
  "priority": "normal",
  "show_at": { "mode": "next_dead_ball", "not_before": "63:40", "not_after": "64:25" },
  "duration_s": 8,
  "fields": { "team": "Harbour City", "headline": "PRESS RAISED", "before": 0.32, "after": 0.83 },
  "locale": "en",
  "language_level": "measured",
  "status": "approved"
}
```

`kind` is `insight`, `key_event`, `update` or `withdrawal`.

**Overlay templates:** player name tag, speed and distance tag, shot speed, pass difficulty, pressure shift bar, momentum strip, control-vs-chaos gauge, shape change, fatigue warning, milestone badge, update banner, withdrawal banner.

---

## 13. Personalization model

Applied by the Director and Narrator; changes what is shown and how it is said, never the facts.

```json
{
  "profile_id": "fan-ana",
  "expertise": "casual",
  "language": "es",
  "favorite_club": "Northvale",
  "favorite_players": ["NV-10"],
  "mode": "player_focus",
  "attention_budget_per_half": 3,
  "min_language_level": "measured",
  "tone": "warm"
}
```

| Dimension | Effect |
|---|---|
| Expertise | Variant chosen, jargon level, budget size |
| Language | Variant language; numbers and names unchanged |
| Favorite club and players | Relevance boost; framing from that side |
| Mode | Which moment types and ambient elements are prioritized |
| Attention budget | Cards per half |
| Minimum language level | Casual viewers never see tentative claims; core fans can opt in |

---

## 14. Resilience and failure handling

Every failure degrades to silence or a correction, never to an unverified claim on screen.

| Failure | Behavior |
|---|---|
| Hypothesis agent times out or errors | Retry once from the last checkpoint; proceed with remaining agents; flag the case `recovered_from_checkpoint` |
| Investigation budget exhausted | Agent submits what it has; untested hypotheses are dropped |
| Invalid pre-registration | Rejected by the orchestrator; agent may re-register once |
| Verifier unavailable | Nothing publishes; cards wait as proposed or expire |
| Verifier rejects every hypothesis | Case closes as `none` or `other`; Analyst Console only |
| Event amended | Correction Watcher re-verifies dependents; revise or withdraw |
| Director overloaded | Lowest-priority cards expire first; fast lane and corrections always pass |
| Model rate limits or outage | Backoff and queue; Ambient Layer, State Builder and Detector keep the screen alive |
| Narrator check fails | Regenerate once, then template |

---

## 15. Microsoft technology and model routing

Every row leaves evidence a judge can see; use that leaves no trace is not claimed.

| Technology | Role | Visible evidence | Status |
|---|---|---|---|
| Microsoft Foundry | Hosts the Verifier semantic agent; runs groundedness and language evaluations; traces every case | Eval results and trace links on the console; portal in the video | Build |
| Microsoft Agent Framework (Python) | Orchestration, fan-out, cross-examination round, checkpoints | Workflow diagram in README; recovery beat in the video | Build |
| Custom MCP server (`tools_server/`) | State Builder catalog for every agent | Tool-call log per hypothesis | Build |
| Azure MCP Server | Ops panel on the console; provisioning during the build | Ops panel in the video; `docs/azure-mcp.md` transcripts | Build |
| GitHub Copilot coding agent / Agent Mode | Only if genuinely used for real work; never PRs created as evidence | Copilot-authored PRs in repo history where they exist; `docs/copilot.md` | Claim only if true |
| GitHub CLI in Actions | Publishes the dataset and demo build as releases | Release assets; workflow file | Build |
| Azure Event Hubs | Live event ingestion | Architecture diagram; throughput in App Insights | Build |
| Azure Cosmos DB | Match Ledger and change feeds | Ledger view on the console | Build |
| Azure Container Apps | State Builder, agent service, API | azd deploy | Build |
| Azure Web PubSub | Push to all three surfaces | Live update in the video | Build |
| Azure Static Web Apps | All three front ends | Public link | Build |
| Application Insights + OpenTelemetry | Agent traces, audit, latency | Trace ID on every card; latency on the scoreboard | Build |
| Key Vault + managed identity | No secrets in code or config | Bicep; README security section | Build |
| azd + Bicep + GitHub Actions | One-command deploy and CI | README badge; CI guard on engine imports | Build |
| Container Apps Jobs | Batch evaluation runs | Workflow file | Stretch |
| Microsoft Fabric Real-Time Intelligence | Eventstream from Event Hubs into an Eventhouse; one KQL query backs a Real-Time Dashboard of match totals | Dashboard screenshot in README; 3 s in the video | Stretch; only after trial access and cost are confirmed and the core demo records cleanly |

**Model routing**

| Role | Model |
|---|---|
| Hypothesis agents, synthesis, recap | gpt-5-mini |
| Verifier semantic check | gpt-5-mini, the agents' model, with its own prompt, seeing only the card's facts and sentences. It replaced Microsoft Phi-4, a non-OpenAI chat model sold directly by Azure, after Phi-4 rejected sound follow-up revisions and timed out under load in live runs. Re-measured on the fixed seeded harness (75 seeded false claims from 10 dev cards, records in `eval/records/`), the two tie: each catches 74 and rejects none of the 10 sound control cards. Re-verifying the demo match's recorded investigations with Phi-4 (`--reverify`) rejected a sound question card that states a strongly supported cause as fact beside a pending follow-up, which gpt-5-mini passes, so the Verifier stays on gpt-5-mini, the model the held-out runs used. Limitation, stated: the Verifier no longer runs on a different model family from the agents; it is independent by role and by what it sees, and the sentences it judges are written by code templates, not by the agents. (Marketplace models such as Mistral cannot be bought on the Free Trial; DeepSeek-V3.2-Speciale reasoned for minutes per card and was retired.) |
| Narrator variants | gpt-5-mini |
| Fast lane | Templates |
| Development runs | gpt-5-mini for all roles |

The subscription is a Free Trial whose only gpt-5 quota is gpt-5-mini; gpt-5.6-terra and gpt-5.6-luna have zero quota (checked 21 October). If gpt-5-mini proves too weak, upgrade to pay-as-you-go, request quota for a larger model, and switch with `PROOFLINE_MODEL_TIER=final`. Both ablation variants always run on the same model.

**Cost control:** every role on gpt-5-mini; a larger model only after an upgrade, for a bounded final evaluation; prompt caching for role prompts and tool schemas; budget alert at 60% of credit; replay mode for the public link so judging costs nothing by default. Confirm prices in the Azure portal before the first paid run.

---

## 16. Mapping to the hackathon

| Stage | Proofline |
|---|---|
| Ingest | Match Engine → Match Clock → Event Hubs → State Builder (→ Fabric, stretch) |
| Interpret | State Builder metrics, Ambient Layer, Moment Detector |
| Explain | Why Engine, Verifier, Narrator, Correction Watcher |
| Render | Broadcast Cue Feed, overlay renderer, Fan Companion, Analyst Console |
| Personalize | Director plus profiles |

| Feature the rules name | Where |
|---|---|
| Player identification with speed and distance thresholds | Ambient Layer tags |
| Pass distance, accuracy, difficulty rating | State Builder; pass difficulty badge |
| Ball and shot speed | State Builder; shot speed overlay |
| Narratives, milestones, recaps | Narrator, milestone moments, recap screen |
| Explainability: control vs chaos, tactical pressure, rhythm | Control-vs-chaos gauge, pressure shift cases, rhythm metric |
| Synthetic data creation | Match Engine, paired runs, suites, published dataset |
| Multi-language | Narrator variants, localized ticker |
| Favorite club, favorite player, player-focused mode | Profiles and Player Focus |
| Auto-eventing from video | Out of scope; the ingest contract accepts any event source |

**Best Multi-Agent System, clause by clause**

| Rubric clause | Where a judge sees it |
|---|---|
| Specialized agents with distinct roles | Three agents registering different predictions on the case file |
| Coordinate through shared state | Match Ledger; ledger view; change feeds driving Director and Correction Watcher |
| Effective handoffs | Pre-register → test → cross-examine → synthesize → verify, each a checkpointed stage |
| Recover from failures | The recovery beat in the video; `recovered_from_checkpoint` on the console |
| Outcome a single agent could not achieve as effectively | Ablation B on the same suites, tools and budget, with CIs on the scoreboard |

---

## 17. Scope and build order

### Build / stretch / cut

| Area | Build | Stretch | Cut |
|---|---|---|---|
| Match Engine | Events, tracking, script DSL, batch amendments, paired runs; planted, decoy, correction suites; realism report; dataset release | Confounded suite | OOV suite, blind set, delayed/dropped faults, Scenario Author |
| Match Clock | Replay, Studio, Batch | — | Variable studio speed |
| Analytics | Build metrics incl. Rhythm; MCP catalog; Ambient Layer; Moment Detector | Possession share, distance covered | Detector-vs-baseline scoring |
| Why Engine | Three agents; pre-registration; budgets; cross-examination; primary/secondary; checkpoint recovery | Player agent | — |
| Verifier | Deterministic checks; Foundry-hosted English semantic check; support rules | Spanish semantic check | Calibration report |
| Corrections | Watcher, dependency index, revise/withdraw, propagation to three surfaces | — | — |
| Narrator | Casual, analyst, broadcast, update, recap; EN and ES | Third language | Voice |
| Director | Budgets, phase gating, expiry, fast lane, change-feed trigger | — | — |
| Fan Companion | Pitch, ambient, cards, "How we know", "Why?", three modes, Update cards, recap | Single Metric mode | More fixtures |
| Analyst Console | Timeline, case file, Verifier panel, revision diff, ledger view, Ops panel, scoreboard, Run live | Halftime pack | Full-time pack |
| Broadcast | Cue feed, overlay renderer, approve/hold/kill, correction cues, cue log | — | Rehearsal mode |
| Proof | Evaluator on three suites with CIs; ablation B | Ablation C | Ablation D, calibration, blind set |
| Azure | Everything marked Build in §15 | Fabric, Container Apps Jobs | — |

### Dependency order

1. Contracts: pydantic schemas for event (with versions), card, proposition, prediction, cue, profile, taxonomy.
2. Public repo with CI, engine-import guard and azd skeleton deployed; Foundry models deployed.
3. Match Engine with the planted suite, paired runs and Batch mode; realism report.
4. State Builder and MCP server (`tools_server/`); `state/season_baselines.json` generated by the engine in batch mode.
5. Moment Detector.
6. Why Engine as a single agent (becomes ablation B), then three agents, then cross-examination, then checkpoint recovery.
7. Verifier and support rules; Foundry-hosted semantic check; Foundry evaluations.
8. Evaluator on planted and decoy suites: first scoreboard, A vs B.
9. Event versions, Correction Watcher, correction suite.
10. Narrator, Director, change-feed triggers.
11. Fan Companion with Ambient Layer and Studio mode.
12. Analyst Console (incl. Ops panel via Azure MCP), Broadcast Cue Feed and overlay renderer.
13. Dataset release; replay mode and public link; final evaluation on the final-tier model.
14. Frontend design pass; video; README; submission.

### Freeze order

If something slips, these drop first, in this order: confounded suite and ablation C; Fabric; Spanish semantic check; Game-State agent (ship two agents with cross-examination); revise path (ship withdraw-only); approve/hold/kill (auto mode, correction cues apply automatically). Nothing in the Fan Companion, the video or the README is dropped.

---

## 18. Success criteria

Targets are starting goals; final numbers are published as measured.

| Area | Criterion | Target |
|---|---|---|
| Accuracy | Published numbers matching recomputation | 100% |
| Attribution | Planted cause recall | ≥ 75% |
| Attribution | Cause precision | ≥ 85% |
| Honesty | Decoy restraint | ≥ 80% |
| Verification | Seeded false claims caught | ≥ 80% |
| Corrections | Dependent cards found | 100% |
| Corrections | Correct revise/withdraw decisions | ≥ 90% |
| Multi-agent value | Proofline vs single agent | Reported with CIs |
| Timing | Fast lane | < 2 s |
| Timing | Full lane detection to verified card | p95 < 25 s |
| Timing | Amendment to correction on screen | < 10 s |
| Restraint | Cards over budget | 0 |
| Demo | All eight beats in §19 shown, under two minutes | Yes |
| Judging | Public link up to 10 November with no model dependency in replay | Yes |

---

## 19. Two-minute demo script (1:58)

The script lives in [`docs/demo-script.md`](demo-script.md). It was rewritten from the one Studio take the surfaces show and from the held-out records, after the ablation ran: three agents measured the same as one, so the proof beat says so.

---

## 20. Submission package

**Elevator pitch.** Proofline is a multi-agent match-intelligence engine for live football. It ingests a synthetic event feed, detects moments where the game shifts, and lets three specialist agents investigate and cross-examine competing explanations on a shared ledger. An independent verifier recomputes every number before anything reaches a fan, an analyst or a broadcast overlay, and every published claim is corrected or withdrawn when the data changes. Built on Microsoft Foundry, Agent Framework, a custom MCP server, Azure MCP, Event Hubs, Cosmos DB, Container Apps, Web PubSub and Static Web Apps, scored against sealed synthetic ground truth. Category: Best Multi-Agent System.

**README order.** Pitch, video, public link, CI badge, licence → 90-second quickstart (`azd up`) → architecture and five-stage mapping → multi-agent category mapping → hero technology table → synthetic data and dataset download → scoreboard with CIs and what it does and does not measure → path to production (human controls, audit, provider adapter contract, cost per match) → software practices (tests, CI guard, managed identity, tracing, Copilot PRs) → limitations.

**Testing instructions.** Public Fan Companion link with two replay fixtures; console and cue-feed credentials; Run live button capped per viewer and per day; note that replay and live share one code path. Link stays up to 10 November on reserved credit.

**Compliance.** Fictional names on every screen and in the video; licence-free music; English materials; public repo; project created after 29 September; no real footage or data; category selected under its exact name on the form.

---

## 21. Risks and kill switches

| Risk | Trigger | Kill switch |
|---|---|---|
| Single agent matches three agents | A vs B gap absent on the planted suite | Add the confounded suite with causes needing a second domain's counter-test, report every suite run; if still flat, lead with cross-examination traces, corrections and recovery, and say the gap was not found |
| Why Engine not producing verified cards | Three agents not stable | Two agents with cross-examination; Game-State becomes stretch |
| Correction beat not working end to end | Revise path unstable | Withdraw-only; propagation to all three surfaces kept |
| Three surfaces not all demo-ready | Broadcast controls unfinished | Broadcast becomes overlay plus cue log; correction cues apply automatically |
| Non-OpenAI verifier model unavailable | Foundry catalog check | Second OpenAI model with a distinct prompt, stated as a limitation |
| Fabric blocked by trial or cost | Access or price check | Drop; keep a match-totals panel in the console |
| Model spend outruns credit | 60% budget alert | Stop development runs; final eval over fewer matches; state it |
| Public link fails during judging | Health alert | Replay path is static-first; reserved credit to 10 November |
| Video over two minutes | Final review against the rubric | Cut the proof beat to one number and architecture to five seconds before anything the rubric names |
| Scope creep | Any time | Nothing in the out-of-scope list is started; free time goes to the fan view and the README |
| Trademark or IP | Before video | Fictional clubs, players, competition, kits; original UI; name check |

---

## 22. Repository structure

```
proofline/
├── README.md
├── DATASET.md
├── contracts/              # pydantic schemas: event, card, proposition, prediction, cue, profile, taxonomy
├── engine/                 # Match Engine (never imported by product code; CI-enforced)
│   ├── scripts/            # tactical scripts and amendments per suite
│   ├── suites/             # planted, decoys, corrections (confounded: stretch)
│   ├── paired/             # counterfactual paired-run tooling
│   └── clock/              # Replay, Studio, Batch + streamer
├── state/                  # State Builder metrics and windows
├── ambient/                # tags, momentum, gauge, ticker
├── tools_server/           # MCP server exposing the tool catalog (not named `mcp`, which would shadow the SDK)
├── detector/               # Moment Detector
├── agents/
│   ├── tactics/
│   ├── physical/
│   ├── game_state/
│   ├── synthesis/
│   ├── verifier/           # deterministic checks + Foundry-hosted semantic agent
│   ├── narrator/
│   └── director/
├── corrections/            # Correction Watcher
├── orchestration/          # Agent Framework workflows, pre-registration validation, budgets, checkpoints
├── ledger/                 # Cosmos DB models, change-feed handlers
├── eval/                   # Evaluator, matching rules, ablation B, seeded errors, Foundry eval logging
├── surfaces/
│   ├── web/                # Fan Companion, Analyst Console, overlay renderer
│   └── api/                # cue feed, profiles, "Why?" endpoint, run-live endpoint
├── infra/                  # Bicep + azd (Key Vault, managed identity)
├── .github/workflows/      # CI, engine-import guard, dataset release via gh
└── docs/
    ├── architecture.md
    ├── taxonomy.md
    ├── support-rules.md
    ├── azure-mcp.md        # transcripts of Azure MCP use
    ├── copilot.md          # list of Copilot-authored PRs
    ├── insight-card.schema.json
    └── cue.schema.json
```

---

## 23. Before the first paid run

- [ ] Public GitHub repo created; CI with the engine-import guard
- [x] azd skeleton deployed: Container Apps, Container Registry, Cosmos (free tier), Event Hubs, Web PubSub, Static Web Apps, App Insights, Key Vault with managed identity
- [x] Quota checked in region (Free Trial: gpt-5-mini has quota; gpt-5.6-terra and gpt-5.6-luna have none)
- [x] gpt-5-mini deployed in Foundry
- [x] Non-OpenAI model deployed for the Verifier: Phi-4, chosen among models with quota that a Free Trial can deploy; replaced by gpt-5-mini after the seeded comparison (§15)
- [x] Budget alert at 60%
- [ ] Model prices confirmed in the Azure portal (the Retail Prices API lists only priority-processing meters for gpt-5-mini in eastus2)
- [x] Azure MCP Server connected to the development agent; transcript capture started (`docs/azure-mcp.md`)
- [ ] Fabric trial access and cost checked
- [ ] Trademark and domain search for "Proofline"
- [ ] Licence-free music chosen for the video
- [ ] Evidence sources re-checked before any are quoted in the README

---

## 24. Evidence base

- [Hackathon Official Rules](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md)
- [IBM 2026 sports fan study](https://newsroom.ibm.com/2026-08-24-ibm-study-sports-fans-want-streamlined-digital-experiences-as-platform-choices-expand)
- [SVG Europe — EVS on provenance, accuracy and speed](https://www.svgeurope.org/blog/headlines/trust-in-content-provenance-accuracy-and-speed-the-next-challenges-of-ai-adoption-in-sports-production-according-to-evs/)
- [Stats Perform — OptaAI Studio](https://www.statsperform.com/optaai-studio/)
- [xGuff — Football fans are drowning in data](https://xguff.substack.com/p/football-fans-are-drowning-in-data)
- [Adweek — casual vs core fan behavior](https://develop.adweek.com/?p=1943074)
- [gpt-5.6-terra in Foundry](https://ai.azure.com/catalog/models/gpt-5.6-terra)
- [gpt-5.6-luna in Foundry](https://ai.azure.com/catalog/models/gpt-5.6-luna)
