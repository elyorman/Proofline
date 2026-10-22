# Proofline synthetic match dataset

Every club, player and competition here is fictional. Matches come from the Match Engine (`engine/`), a possession-chain simulator driven by tactical scripts that declare mechanisms, never causes. The schema, the script DSL, the amendment format, the paired-run method and the realism report join this file with the dataset release.

## The demo match

[`engine/scripts/planted/m01.yaml`](engine/scripts/planted/m01.yaml) plants one tactical change and one feed error:

- **s1** raises Harbour City's press height from 0.3 to 0.9 from 56:00, reaching it at 58:00.
- **a1** is a provider error: the feed first shows Northvale's 45:00–55:00 passes, carries and dribbles 22 m to the right of where they happened, and a batch amendment at 68:00 moves them back.

Its seed is chosen by a stated rule, never by eye: **the first seed from 4417 upwards on which, in that one match, each planted story's change is at least its median over the held-out seeds and clears two natural standard deviations, and on which the corrected flank change does not.** [`tests/test_engine_planted_signal.py`](tests/test_engine_planted_signal.py) applies the rule and fails if the script's seed is not the one it picks. The demo match is therefore a clear instance of each story, not a typical one, and no reported number comes from it: evaluation uses held-out seeds 100–139, which played no part in tuning the engine.

## Is a planted story visible in one match?

The detector watches a single match, so a paired-run effect whose confidence interval clears zero is not enough. For an observable and a detection window, a match's **change** is the observable over the window minus its value over the same match's first half. The **natural change** is the same quantity without the story: the same seed with the intervention removed or, for a feed error, the corrected events. **Separation** is the mean change with the story minus the mean natural change, in standard deviations of the natural change across seeds ([`engine/visibility.py`](engine/visibility.py)). A match **clears** when its own change is at least two natural standard deviations above the mean natural change.

| Story | Observable | Window |
|---|---|---|
| s1 | Harbour City pressures per Northvale on-ball action in Northvale's first 60% | 58:00–63:00 |
| s1 | Share of Northvale's passes longer than 30 m | 58:00–63:00 |
| a1 | Share of Northvale's on-ball actions starting in the right third of the width, as first delivered | 45:00–55:00 |
