# Proofline synthetic match dataset

Every club, player and competition here is fictional. Matches come from the Match Engine (`engine/`), a possession-chain simulator driven by tactical scripts that declare mechanisms, never causes. The schema, the script DSL, the amendment format, the paired-run method and the realism report join this file with the dataset release.

## The demo match

[`engine/scripts/planted/m01.yaml`](engine/scripts/planted/m01.yaml) plants one tactical change and one feed error:

- **s1** raises Harbour City's press height from 0.3 to 0.9 from 56:00, reaching it at 58:00.
- **a1** is a provider error: the feed first shows Northvale's 45:00–65:00 passes, carries and dribbles whose true start and end lie within 46 m of the left touchline (in Northvale's frame) 22 m to the right of where they happened, and a batch amendment at 70:00 moves them back. The error lasts to 65:00 so the flank card it causes outlasts the five minutes Proofline waits to confirm a change.

Its seed is chosen by a stated rule, never by eye: **the first seed from 4417 upwards on which, in that one match, every observable in the table below changes by at least its median over validation seeds 100–139 and clears two natural standard deviations, and on which the corrected right-channel change does not clear them.** Medians, means and standard deviations all come from those validation seeds. The scan starts at 4417 because that was the demo match's seed before any of this was measured. [`tests/test_engine_planted_signal.py`](tests/test_engine_planted_signal.py) applies the rule and fails if the script's seed is not the one it picks. The demo match is therefore a clear instance of each story rather than an average one, and no evaluation or scoreboard number comes from it. The visibility and realism figures use validation seeds 100–139, which played no part in tuning the engine; the evaluation suites draw their dev and held-out seeds from 1000 up, which none of this touches (spec §11.1). If a later demo beat needs another condition, the rule is extended here openly and the seed it replaces is recorded.

## Is a planted story visible in one match?

The detector watches a single match, so a paired-run effect whose confidence interval clears zero is not enough. For an observable and a detection window, a match's **change** is the observable over the window minus its value over the same match's first half. The **natural change** is the same quantity without the story: the same seed with the intervention removed or, for a feed error, the corrected events. **Separation** is the mean change with the story minus the mean natural change, in sample standard deviations of the natural change across seeds ([`engine/visibility.py`](engine/visibility.py)). A match **clears** when its own change is at least two natural standard deviations past the mean natural change, in the way the observable moves with its story. Windows include their start and exclude their end; on-ball actions are passes, carries and dribbles; coordinates are in the acting team's attacking frame, so the right third is y > 45.33 m.

The windows are the demo cards' windows. Scoring a planted suite uses each script's ground-truth observable window instead (spec §7.2).

| Story | Observable | Card window |
|---|---|---|
| s1 | Pressure rate: Harbour City pressures in Northvale's first 60% of the pitch, divided by Northvale on-ball actions starting in that same zone (x < 63 in Northvale's frame, x > 42 in Harbour City's) | 58:00–63:00 |
| s1 | Share of Northvale's passes longer than 30 m | 58:00–63:00 |
| a1 | Share of Northvale's on-ball actions starting in the right third of the width, as first delivered | 45:00–65:00 |

## Planted and decoy suites

The evaluation suites live in `engine/suites/<suite>/<split>/`. `scripts/` holds one match script per match. `ground_truth.yaml` records what each match planted, or that it planted nothing. The planted suite's `ground_truth_flags.json` holds its frozen `not_observable` flags. Product code never opens any of them: the CI isolation guard refuses product code that names `engine/scripts` or `engine/suites`, as text or as a joined path, and only `eval/` reads the ground truth. `uv run proofline-engine suite --suite planted|decoys --split dev|heldout` builds them.

Each planted match carries one intervention whose mechanism belongs to one of the six classes the engine can plant. The class appears only in the ground truth. Match ids (`m417`) come from one shuffle across both suites and both splits, so an id says neither what was planted, nor whether anything was, nor which split it belongs to. Each class's observables, and the way each moves when the class is present, are fixed in [`contracts/planted.py`](contracts/planted.py):

| Class | Mechanism in the script | Observables |
|---|---|---|
| `tactical.press_intensity_up` | press height rises sharply, from between 55:00 and 65:00 | the team's pressure rate up; the opponent's long-ball share up |
| `tactical.press_intensity_down` | press height drops sharply, from between 55:00 and 65:00 | the team's pressure rate down; the opponent's long-ball share down |
| `game_state.chasing_result` | from between 55:00 and 64:00, once trailing: press higher, play more directly | the team's pressure rate up; its long-ball share up |
| `game_state.protecting_lead` | from between 55:00 and 64:00, once leading: drop the press, play more directly | the team's pressure rate down; its long-ball share up |
| `physical.unit_fatigue` | the defence or midfield tires quickly, from between 55:00 and 62:00 | the unit's sprints per minute down; its mean sprint speed down |
| `physical.player_fatigue` | one midfielder or forward tires quickly, from between 55:00 and 62:00 | the player's sprints per minute down; their mean sprint speed down |

**Pressing is sprint work.** A team's off-ball sprints per minute scale with its press height: they rise by half the press height's distance above 0.5 and fall by half its distance below it (`PRESS_SPRINTS` in [`engine/sim.py`](engine/sim.py)). A press of 0.9 therefore sprints 20% more than one of 0.5, so a press, a chase or a team dropping off to protect a lead moves its sprints as well as its observables. Until 24 October 2026 sprints depended on energy alone. Agents who reasoned, correctly for real football, that a heavier press means more sprints were refuted by the engine every time. Inspecting why true causes failed on the dev questions found this. Sprints draw from their own random streams, so the fix moved no on-ball event. The season baselines, the suites and the demo match's sprints were regenerated with it, before any held-out run. Sprint count is no press or game-state class's observable, so it decides no score; it is evidence an agent may look for.

A class's window opens when its change starts: minutes 0–8 after it for the press and game-state classes, 7–27 for fatigue, which takes time to show. Every change starts in the second half and by 65:00, so its change is measured against the first half, and the start time never tells a score-triggered class apart. Dev holds two matches per class and four decoys; held-out holds five per class and ten decoys. Decoys are the same two clubs with nothing planted, so every swing in them is natural. Each decoy sets a team up in the starting style of one class's template, the classes taken in turn, so a low or high press before the change never tells a planted match from a decoy.

**Seeds** stay inside each split's range (spec §11.1, `SEED_RANGES` in [`contracts/eval_run.py`](contracts/eval_run.py)), and no two matches share one. Planted match *i* of *n* tries seeds *i*, *i* + *n*, *i* + 2*n*, … above the split's first seed (1000 for dev, 2000 for held-out), staying below 300 above it. Decoys take consecutive seeds from 300 above it, and paired runs search from 500 above it.

**Hygiene.** A planted match takes the first seed on which its class is the only fair answer, from the change's start to the end of its window. A press rise is planted only while the team is not trailing, and a press drop only while it is not leading, so chasing the result or protecting a lead is never also right. A chasing or protecting change starts with the first possession, from its `at`, in which the team trails or leads, by 65:00 at the latest, and keeps that score through its window.

**Flags.** Each planted match is run with and without its change, on seeds from 500 above the split's first, until every observable has a value on 30 of them. Sprint speed has none when nobody in the subject sprints in the window. The paired-effect interval is a 95% t-interval on the per-seed differences, and separation is as defined above. A match is excluded under the first rule of spec §7.2 it meets. `ground_truth_flags.json` lists every planted match, the seeds measured for it, and each excluded match with its class, its rule and each observable's numbers. Its `flag_set_id` is a digest of that content, and every planted evaluation run embeds the flag set.

## The season behind normal variation

`state/season_baselines.json` is how far each metric moves in ordinary play: 200 matches with nothing planted, seeds 3000–3199 (a range nothing else draws from), each with one team set up in the starting style of one class's template in turn, as the decoys are. For every metric and subject level (team, unit, player), and every second-half window of 5, 10, 15 or 20 minutes ending at 50' to 90', it records the mean and standard deviation of the change from the first half, in the metric's threshold units, leaving out measurements on fewer events than a card needs. Sprints fall late in every match (a team's rate is about 30% below its first half by 80'), so the mean matters as much as the spread. `uv run proofline-engine season` rebuilds it.
