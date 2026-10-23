# Backlog

The one list of open work, grouped in the order the work is expected to reach it and ranked within each group. Items come from the plans' follow-up sections (kept there as history), the audits and the reviews; the source is in brackets. Close an item by deleting it in the commit that fixes it.

## State Builder, detector and Verifier

1. **`meta.json` and qualifier contracts.** A `contracts/` model for `meta.json` (match, teams, roster; `period_lengths_s` with integer keys, scheduled or actual end stated) and typed qualifiers (a set-piece `kind` enum; sprint `speed_kmh` and `distance_m`), exported, before product code reads either. Have the Match Clock check the event count against it. [engine-core]
2. **A suite match's seed must not reach product code.** `write_match` puts `seed` in `meta.json`, and the seed ranges tell planted matches from decoys. Leave it out for suite matches. [final review]
3. **The State Builder measures what the engine planted.** Pressure rate uses the same zone on both sides of the ratio (x < 63 in the opponent's frame, x > 42 in the presser's); sprints read `distance_m` and `speed_kmh`; possessions are segmented on team changes, set pieces included; period markers stay out of per-team counts. A test in `tests/` checks that `state/` agrees with `engine/visibility.py` on a few suite matches. [engine-core, planted-signal, audit 10-23]
4. **Support rules** (`docs/support-rules.md`). Per-metric minimum thresholds for hypotheses and counter-tests, after which `check_counter_test` also checks counters on other metrics. Sample-size minimums set knowing the demo's 58–63' window holds 17 Northvale passes and 18 in-zone actions (or the card uses the ground-truth 56–64' window). Channel-share bands set on the dev split, never to make the demo come out a particular way. [contract-hygiene, planted-signal]
5. **Detector.** Compare thresholds tuned on dev with the validation hit rates: the press story clears on pressure rate in 82% of matches, on long-ball share in 85%, on either in 100%; the flank story in 50%. Check the 74' honest-silence beat on seed 4434 (Harbour City score at 77:09). [planted-signal]
6. **A season baseline for physical claims.** Ordinary tiredness makes sprint falls common (Harbour City's 58–63' sprints fall by at least 15% in 70% of validation matches), so the Physical agent and its challengers need a same-window season baseline. `state/season_baselines.json` needs a seed range no evaluation split uses (spec §11.1). [contract-hygiene, audit 10-22]
7. **`MatchSim.run()` is single-use**: a second call appends a second match. Refuse it. [engine-core]

## Agents and evaluation

1. **Chasing the result or a press change.** Synthesis makes chasing the result primary only if the team's own long-ball share rises; otherwise press intensity is primary and the score is a secondary cause. Once agents exist, a fixture test pins m01's 63' card: press intensity up primary, chasing the result secondary. The suites never plant a press rise by a trailing team, so tuning on dev would otherwise learn the opposite. [audit 10-23]
2. **Evaluator matching.** Match the planted team as well as the class. Fixed metric names for headline and all-script recall, with a check that the headline count plus the exclusions equals the all-script count. [planted-suites, contract-hygiene]
3. **Flag sets in comparisons.** `VariantComparison` carries the `flag_set_id` and refuses two runs whose flag sets differ. An `Exclusion`'s observables must be its class's `CAUSE_OBSERVABLES`. [planted-suites]
4. **Name the suite version a run scored**: a digest of the scripts and ground truth that an `EvalRun` cites, as it cites its flag set. [planted-suites]
5. **Cross-examination.** One counter-test per challenger per hypothesis, recorded by the orchestrator. `HypothesisTest.outcome` computed from the prediction, not set freely. `check_counter_test` groups a team with its players ("NV-03") as well as its units. [contract-hygiene]
6. **Suite size.** About 28 held-out matches count toward recall, so a recall of 75% has a 95% CI of about ±16 points, and an A-vs-B difference will rarely exclude zero. Size the held-out suite from the per-case cost after the first full run; plan the proof narration on the "reported as measured" variant. [audit 10-23]
7. **Team identity.** The display name is used as a team's identifier across contracts and engine; give teams a stable id. [audit 10-22]

## Ledger and surfaces

1. **Re-validate a card before every write.** `InsightCard` has no `validate_assignment`, so a status set after construction skips the rule-6 gate. [contract-hygiene, audit 10-23]
2. **A document per card revision**, so a withdrawn card keeps its earlier passing verification (spec §10). [contract-hygiene]
3. **Fast-lane cards.** Check the lane and moment type before the outcome, so a goal is never "No clear cause"; refuse `investigating`, `cross_examined`, `verified` and `rejected` if the Director ever sets them. [contract-hygiene]

## Azure

1. **Bicep.** Add the `azd-service-name` tags and the container-app `registries` settings; the first `azd deploy` of a service fails without them. [audit 10-22]
2. **Keep `engine/suites/` out of container images** (`.dockerignore`), as the wheel and sdist already do. [engine-core]

## Corrections

1. **Amendment output.** Write the v1 feed (`first_delivered`) and an `amendments.jsonl` of `EventAmendment` records, one per batch; the Match Clock replays v1 and emits each batch at its `at`. Refuse an amendment that selects nothing; state the 0.1 m rounding rule and require `dy_m` to be a multiple of 0.1. `dump_script` then writes amendments (it refuses them today). Until this exists, `data/m01` has no feed error to correct. [planted-signal, audit 10-23, final review]
2. **The v1 feed's own consistency.** a1 moves only Northvale's actions, so v1 has 22 m jumps between consecutive Northvale actions and Harbour City pressing 22 m from the ball. Revisit if the State Builder or the Verifier checks v1 consistency. [planted-signal]

## Engine, realism and tooling

1. **Realism report.** Record or fix: every shot ends at (105, 34); dribbles go straight ahead; sprint starts use the ball at the minute tick; sprint events depend on the seed alone, not on play; about 27 goal kicks a match and no corners; about 28% of throw-ins start with a carry or dribble; about 22% of on-ball actions reflect off x = 97 and 38.5% start in the last 30 m; long-ball shares near 40% under a strong press. Fixing any of these changes the random draws: recalibrate and re-pick the demo seed by its rule. [engine-core, planted-signal, audit 10-23]
2. **First-half changes.** Planted changes before half-time are refused: spec §7.2's minutes-before baseline is not implemented. A first-half `at` after the played stoppage applies only at the second-half kick-off; refuse an `at` after 45+1:00 or document it. [planted-suites, engine-core]
3. **Per-observable seed counts** are not recorded in `ObservableCheck`; the flag set lists every seed run. [planted-suites]
4. **The isolation guard reads text**, so `Path("engine").joinpath("suites")` still passes it. [final review]
5. **Schemas.** The schema check misses a stale file for a model removed from `SCHEMAS`; export `CrossExamination` in serialization mode when it is exported, or its computed `result` is missing. [contract-hygiene]
6. **Test time.** About 75 s, most of it engine statistics. Mark those tests slow and run `-m "not slow"` locally, everything in CI; `tests/test_engine_mechanisms.py` runs the same 40 m01 simulations for each of its three tests. [planted-signal, audit 10-23]
7. **Engine hardening.** Derive the parameter sets and `PARAM_RANGES` from one table; list the `EDGES` interventions out of time order in `tests/test_engine_params.py`; catch `UnicodeDecodeError` in the CLI's load step; rename `Streams`' `minute` argument to `bucket`; import the pitch constants from `contracts`; give `--seed` a metavar. [engine-core]
