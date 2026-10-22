# Proofline synthetic match dataset

Every club, player and competition here is fictional. Matches come from the Match Engine (`engine/`), a possession-chain simulator driven by tactical scripts that declare mechanisms, never causes. The schema, the script DSL, the amendment format, the paired-run method and the realism report join this file with the dataset release.

## The demo match

[`engine/scripts/planted/m01.yaml`](engine/scripts/planted/m01.yaml) plants one tactical change and one feed error:

- **s1** raises Harbour City's press height from 0.3 to 0.9 from 56:00, reaching it at 58:00.
- **a1** is a provider error: the feed first shows Northvale's 45:00–55:00 passes, carries and dribbles whose true start and end lie within 46 m of the left touchline (in Northvale's frame) 22 m to the right of where they happened, and a batch amendment at 68:00 moves them back.

Its seed is chosen by a stated rule, never by eye: **the first seed from 4417 upwards on which, in that one match, every observable in the table below changes by at least its median over held-out seeds 100–139 and clears two natural standard deviations, and on which the corrected right-channel change does not clear them.** Medians, means and standard deviations all come from the held-out seeds. The scan starts at 4417 because that was the demo match's seed before any of this was measured. [`tests/test_engine_planted_signal.py`](tests/test_engine_planted_signal.py) applies the rule and fails if the script's seed is not the one it picks. The demo match is therefore a clear instance of each story rather than an average one, and no evaluation or scoreboard number comes from it. The visibility and realism figures use held-out seeds 100–139, which played no part in tuning the engine; the evaluation suites use seeds from 1000 up, which none of this touches (spec §11.1). If a later demo beat needs another condition, the rule is extended here openly and the seed it replaces is recorded.

## Is a planted story visible in one match?

The detector watches a single match, so a paired-run effect whose confidence interval clears zero is not enough. For an observable and a detection window, a match's **change** is the observable over the window minus its value over the same match's first half. The **natural change** is the same quantity without the story: the same seed with the intervention removed or, for a feed error, the corrected events. **Separation** is the mean change with the story minus the mean natural change, in sample standard deviations of the natural change across seeds ([`engine/visibility.py`](engine/visibility.py)). A match **clears** when its own change is at least two natural standard deviations above the mean natural change. Windows include their start and exclude their end; on-ball actions are passes, carries and dribbles; coordinates are in the acting team's attacking frame, so the right third is y > 45.33 m.

The windows are the demo cards' windows. Scoring a planted suite uses each script's ground-truth observable window instead (spec §7.2).

| Story | Observable | Card window |
|---|---|---|
| s1 | Pressure rate: Harbour City pressures in Northvale's first 60% of the pitch, divided by Northvale on-ball actions starting in that same zone (x < 63 in Northvale's frame, x > 42 in Harbour City's) | 58:00–63:00 |
| s1 | Share of Northvale's passes longer than 30 m | 58:00–63:00 |
| a1 | Share of Northvale's on-ball actions starting in the right third of the width, as first delivered | 45:00–55:00 |
