# Proofline scoreboard

Every evaluation record in [`eval/records/`](../eval/records/), rendered by `uv run python -m eval scoreboard --records eval/records` and rewritten by `make scoreboard`. CI checks that this block matches the records exactly, and that every rate, difference or interval the README quotes is one of them. The README's [What we measured](../README.md#what-we-measured) explains what these numbers mean and what they do not.

## Reproduce it

These make live model calls; the held-out split is meant to be run once.

```bash
uv run proofline-engine suite --suite planted --split heldout
uv run proofline-engine suite --suite decoys --split heldout
make heldout-feeds
uv run proofline batch --data data/heldout --variant A --out runs/held
uv run python -m eval --runs runs/held --split heldout --variant A --after-follow-up
uv run python -m eval.questions make --split heldout --out runs/held/questions.jsonl
uv run proofline questions --data data/heldout --questions runs/held/questions.jsonl --variant P --out runs/held/q
uv run python -m eval.questions score --runs runs/held/q --split heldout --compare A P --metric false_claims_per_question
make scoreboard
```

## Every record

<!-- scoreboard:start -->
Generated from evaluation records. Dev is tuning only; heldout is for reporting.


Questions: heldout — reporting; set 676bede2355ccff33f923fc87009aafd8925bb20a18c5a92dcba5114cc96e77d.

| Metric (95% CI; n) | A | B | P |
|---|---|---|---|
| true_premise_accuracy | questions-heldout-A-99e67b73770ed5b8: 32.1% ([17.9, 50.7]; n=28; Wilson); questions-heldout-A-after-follow-up-cb4d5eb905e48353: 32.1% ([17.9, 50.7]; n=28; Wilson) | questions-heldout-B-164d3953ee116a53: 32.1% ([17.9, 50.7]; n=28; Wilson); questions-heldout-B-after-follow-up-02d7a3c686c8c36d: 25.0% ([12.7, 43.4]; n=28; Wilson) | questions-heldout-P-7bbae1678cd512dd: 57.1% ([39.1, 73.5]; n=28; Wilson); questions-heldout-P-after-follow-up-1b5aac88b41a7f17: 57.1% ([39.1, 73.5]; n=28; Wilson) |
| false_premise_rejection | questions-heldout-A-99e67b73770ed5b8: 98.0% ([89.5, 99.6]; n=50; Wilson); questions-heldout-A-after-follow-up-cb4d5eb905e48353: 98.0% ([89.5, 99.6]; n=50; Wilson) | questions-heldout-B-164d3953ee116a53: 96.0% ([86.5, 98.9]; n=50; Wilson); questions-heldout-B-after-follow-up-02d7a3c686c8c36d: 96.0% ([86.5, 98.9]; n=50; Wilson) | questions-heldout-P-7bbae1678cd512dd: 70.0% ([56.2, 80.9]; n=50; Wilson); questions-heldout-P-after-follow-up-1b5aac88b41a7f17: 70.0% ([56.2, 80.9]; n=50; Wilson) |
| false_claims_per_question | questions-heldout-A-99e67b73770ed5b8: 15.4% ([9.0, 25.0]; n=78; Wilson); questions-heldout-A-after-follow-up-cb4d5eb905e48353: 3.8% ([1.3, 10.7]; n=78; Wilson) | questions-heldout-B-164d3953ee116a53: 15.4% ([9.0, 25.0]; n=78; Wilson); questions-heldout-B-after-follow-up-02d7a3c686c8c36d: 9.0% ([4.4, 17.4]; n=78; Wilson) | questions-heldout-P-7bbae1678cd512dd: 34.6% ([25.0, 45.7]; n=78; Wilson); questions-heldout-P-after-follow-up-1b5aac88b41a7f17: 34.6% ([25.0, 45.7]; n=78; Wilson) |
| claim_precision | questions-heldout-A-99e67b73770ed5b8: 42.9% ([24.5, 63.5]; n=21; Wilson); questions-heldout-A-after-follow-up-cb4d5eb905e48353: 75.0% ([46.8, 91.1]; n=12; Wilson) | questions-heldout-B-164d3953ee116a53: 42.9% ([24.5, 63.5]; n=21; Wilson); questions-heldout-B-after-follow-up-02d7a3c686c8c36d: 50.0% ([26.8, 73.2]; n=14; Wilson) | questions-heldout-P-7bbae1678cd512dd: 37.2% ([24.4, 52.1]; n=43; Wilson); questions-heldout-P-after-follow-up-1b5aac88b41a7f17: 37.2% ([24.4, 52.1]; n=43; Wilson) |

- questions-heldout-A-99e67b73770ed5b8: 80/80 answered; 0 failed; 0 missing; 0 unanswerable; 57 premise rejected; token usage complete.
- questions-heldout-A-after-follow-up-cb4d5eb905e48353: 80/80 answered; 0 failed; 0 missing; 0 unanswerable; 57 premise rejected; token usage complete.
- questions-heldout-B-164d3953ee116a53: 79/80 answered; 1 failed; 0 missing; 1 unanswerable; 56 premise rejected; token usage incomplete.
- questions-heldout-B-after-follow-up-02d7a3c686c8c36d: 79/80 answered; 1 failed; 0 missing; 1 unanswerable; 56 premise rejected; token usage incomplete.
- questions-heldout-P-7bbae1678cd512dd: 80/80 answered; 0 failed; 0 missing; 0 unanswerable; 36 premise rejected; token usage complete.
- questions-heldout-P-after-follow-up-1b5aac88b41a7f17: 80/80 answered; 0 failed; 0 missing; 0 unanswerable; 36 premise rejected; token usage complete.

Detector suites:

| Split | Variant | Run | Headline planted recall (95% CI) | All-planted recall (95% CI) | Cause precision (95% CI) | Decoy restraint (95% CI) | Verifier catch rate (95% CI) | Failed cases |
|---|---|---|---|---|---|---|---|---|
| heldout — reporting | A | batch-A-715af4adadbb1553-wilson | 35.7% ([20.7, 54.2]; n=28; Wilson) | 33.3% ([19.2, 51.2]; n=30; Wilson) | 32.6% ([20.5, 47.5]; n=43; Wilson) | 70.0% ([39.7, 89.2]; n=10; Wilson) | not run | 0 |
| heldout — reporting | A | batch-A-715af4adadbb1553-wilson-after-follow-up | 17.9% ([7.9, 35.6]; n=28; Wilson) | 16.7% ([7.3, 33.6]; n=30; Wilson) | 29.6% ([15.9, 48.5]; n=27; Wilson) | 70.0% ([39.7, 89.2]; n=10; Wilson) | not run | 0 |
| heldout — reporting | B | batch-B-ffa549873dee2dce-wilson | 32.1% ([17.9, 50.7]; n=28; Wilson) | 33.3% ([19.2, 51.2]; n=30; Wilson) | 40.0% ([27.0, 54.5]; n=45; Wilson) | 70.0% ([39.7, 89.2]; n=10; Wilson) | not run | 0 |
| heldout — reporting | B | batch-B-ffa549873dee2dce-wilson-after-follow-up | 21.4% ([10.2, 39.5]; n=28; Wilson) | 23.3% ([11.8, 40.9]; n=30; Wilson) | 36.1% ([22.5, 52.4]; n=36; Wilson) | 70.0% ([39.7, 89.2]; n=10; Wilson) | not run | 0 |

Exclusions for batch-A-715af4adadbb1553-wilson (2):
- m752: tactical.press_intensity_down; no_separation; pressure_rate/Northvale: separation -1.719 SD, paired-effect CI [-0.236, -0.153]; long_ball_share/Harbour City: separation -1.429 SD, paired-effect CI [-0.168, -0.104]
- m544: tactical.press_intensity_down; no_separation; pressure_rate/Northvale: separation -1.893 SD, paired-effect CI [-0.275, -0.173]; long_ball_share/Harbour City: separation -1.801 SD, paired-effect CI [-0.187, -0.121]

Exclusions for batch-A-715af4adadbb1553-wilson-after-follow-up (2):
- m752: tactical.press_intensity_down; no_separation; pressure_rate/Northvale: separation -1.719 SD, paired-effect CI [-0.236, -0.153]; long_ball_share/Harbour City: separation -1.429 SD, paired-effect CI [-0.168, -0.104]
- m544: tactical.press_intensity_down; no_separation; pressure_rate/Northvale: separation -1.893 SD, paired-effect CI [-0.275, -0.173]; long_ball_share/Harbour City: separation -1.801 SD, paired-effect CI [-0.187, -0.121]

Exclusions for batch-B-ffa549873dee2dce-wilson (2):
- m752: tactical.press_intensity_down; no_separation; pressure_rate/Northvale: separation -1.719 SD, paired-effect CI [-0.236, -0.153]; long_ball_share/Harbour City: separation -1.429 SD, paired-effect CI [-0.168, -0.104]
- m544: tactical.press_intensity_down; no_separation; pressure_rate/Northvale: separation -1.893 SD, paired-effect CI [-0.275, -0.173]; long_ball_share/Harbour City: separation -1.801 SD, paired-effect CI [-0.187, -0.121]

Exclusions for batch-B-ffa549873dee2dce-wilson-after-follow-up (2):
- m752: tactical.press_intensity_down; no_separation; pressure_rate/Northvale: separation -1.719 SD, paired-effect CI [-0.236, -0.153]; long_ball_share/Harbour City: separation -1.429 SD, paired-effect CI [-0.168, -0.104]
- m544: tactical.press_intensity_down; no_separation; pressure_rate/Northvale: separation -1.893 SD, paired-effect CI [-0.275, -0.173]; long_ball_share/Harbour City: separation -1.801 SD, paired-effect CI [-0.187, -0.121]

Paired differences (first variant minus second; paired match bootstrap):

| Record | Split | Variants | Suite | Metric | Difference (95% CI) | Unverified configuration |
|---|---|---|---|---|---|---|
| batch-A-715af4adadbb1553-wilson-after-follow-up-vs-batch-B-ffa549873dee2dce-wilson-after-follow-up-cause_precision | heldout — reporting | A − B | combined | cause_precision | -6.5 pp ([-21.0, 9.4]; n=40; paired match bootstrap) | wall_time_budget_s |
| batch-A-715af4adadbb1553-wilson-after-follow-up-vs-batch-B-ffa549873dee2dce-wilson-after-follow-up-planted_recall | heldout — reporting | A − B | planted | planted_recall | -3.6 pp ([-14.3, 7.1]; n=28; paired match bootstrap) | wall_time_budget_s |
| batch-A-715af4adadbb1553-wilson-vs-batch-B-ffa549873dee2dce-wilson-cause_precision | heldout — reporting | A − B | combined | cause_precision | -7.4 pp ([-20.9, 7.0]; n=40; paired match bootstrap) | wall_time_budget_s |
| batch-A-715af4adadbb1553-wilson-vs-batch-B-ffa549873dee2dce-wilson-planted_recall | heldout — reporting | A − B | planted | planted_recall | +3.6 pp ([-14.3, 21.4]; n=28; paired match bootstrap) | wall_time_budget_s |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-B-164d3953ee116a53-claim_precision | heldout — reporting | A − B | questions | claim_precision | -2.9 pp ([-25.5, 20.8]; n=79; paired match bootstrap) | none recorded |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-B-164d3953ee116a53-false_claims_per_question | heldout — reporting | A − B | questions | false_claims_per_question | +0.0 pp ([-7.6, 6.8]; n=77; paired match bootstrap) | none recorded |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-B-164d3953ee116a53-false_premise_rejection | heldout — reporting | A − B | questions | false_premise_rejection | +2.0 pp ([0.0, 6.4]; n=50; paired match bootstrap) | none recorded |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-B-164d3953ee116a53-true_premise_accuracy | heldout — reporting | A − B | questions | true_premise_accuracy | -3.7 pp ([-19.4, 12.9]; n=27; paired match bootstrap) | none recorded |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-P-7bbae1678cd512dd-claim_precision | heldout — reporting | A − P | questions | claim_precision | +5.6 pp ([-20.0, 33.3]; n=80; paired match bootstrap) | none recorded |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-P-7bbae1678cd512dd-false_claims_per_question | heldout — reporting | A − P | questions | false_claims_per_question | -19.2 pp ([-33.3, -5.2]; n=78; paired match bootstrap) | none recorded |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-P-7bbae1678cd512dd-false_premise_rejection | heldout — reporting | A − P | questions | false_premise_rejection | +28.0 pp ([15.9, 40.4]; n=50; paired match bootstrap) | none recorded |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-P-7bbae1678cd512dd-true_premise_accuracy | heldout — reporting | A − P | questions | true_premise_accuracy | -25.0 pp ([-51.7, 0.0]; n=28; paired match bootstrap) | none recorded |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-B-after-follow-up-02d7a3c686c8c36d-claim_precision | heldout — reporting | A − B | questions | claim_precision | +22.7 pp ([-10.0, 57.5]; n=79; paired match bootstrap) | none recorded |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-B-after-follow-up-02d7a3c686c8c36d-false_claims_per_question | heldout — reporting | A − B | questions | false_claims_per_question | -5.2 pp ([-11.7, 0.0]; n=77; paired match bootstrap) | none recorded |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-B-after-follow-up-02d7a3c686c8c36d-false_premise_rejection | heldout — reporting | A − B | questions | false_premise_rejection | +2.0 pp ([0.0, 6.4]; n=50; paired match bootstrap) | none recorded |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-B-after-follow-up-02d7a3c686c8c36d-true_premise_accuracy | heldout — reporting | A − B | questions | true_premise_accuracy | +3.7 pp ([-14.8, 23.8]; n=27; paired match bootstrap) | none recorded |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-claim_precision | heldout — reporting | A − P | questions | claim_precision | +37.8 pp ([3.8, 68.4]; n=80; paired match bootstrap) | none recorded |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-false_claims_per_question | heldout — reporting | A − P | questions | false_claims_per_question | -30.8 pp ([-42.9, -19.2]; n=78; paired match bootstrap) | none recorded |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-false_premise_rejection | heldout — reporting | A − P | questions | false_premise_rejection | +28.0 pp ([15.9, 40.4]; n=50; paired match bootstrap) | none recorded |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-true_premise_accuracy | heldout — reporting | A − P | questions | true_premise_accuracy | -25.0 pp ([-50.0, 0.0]; n=28; paired match bootstrap) | none recorded |
| questions-heldout-B-164d3953ee116a53-vs-questions-heldout-P-7bbae1678cd512dd-claim_precision | heldout — reporting | B − P | questions | claim_precision | +4.8 pp ([-22.4, 33.2]; n=79; paired match bootstrap) | none recorded |
| questions-heldout-B-164d3953ee116a53-vs-questions-heldout-P-7bbae1678cd512dd-false_claims_per_question | heldout — reporting | B − P | questions | false_claims_per_question | -18.2 pp ([-32.9, -3.9]; n=77; paired match bootstrap) | none recorded |
| questions-heldout-B-164d3953ee116a53-vs-questions-heldout-P-7bbae1678cd512dd-false_premise_rejection | heldout — reporting | B − P | questions | false_premise_rejection | +26.0 pp ([12.8, 38.9]; n=50; paired match bootstrap) | none recorded |
| questions-heldout-B-164d3953ee116a53-vs-questions-heldout-P-7bbae1678cd512dd-true_premise_accuracy | heldout — reporting | B − P | questions | true_premise_accuracy | -25.9 pp ([-52.2, 0.0]; n=27; paired match bootstrap) | none recorded |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-claim_precision | heldout — reporting | B − P | questions | claim_precision | +11.9 pp ([-21.4, 44.2]; n=79; paired match bootstrap) | none recorded |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-false_claims_per_question | heldout — reporting | B − P | questions | false_claims_per_question | -24.7 pp ([-38.0, -10.5]; n=77; paired match bootstrap) | none recorded |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-false_premise_rejection | heldout — reporting | B − P | questions | false_premise_rejection | +26.0 pp ([12.8, 38.9]; n=50; paired match bootstrap) | none recorded |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-true_premise_accuracy | heldout — reporting | B − P | questions | true_premise_accuracy | -33.3 pp ([-59.1, -7.4]; n=27; paired match bootstrap) | none recorded |

Seeded Verifier run: seeded-A-0b1d9364658a4e69 (dev — tuning only, A; 10 card clusters).
Sound-control catch rate: 98.7% ([92.8, 99.8]; n=75; Wilson). All-cards catch rate: 98.7% ([92.8, 99.8]; n=75; Wilson). Controls rejected: 0.0% ([0.0, 27.8]; n=10; Wilson).
No answer: 0 seeded trials; 0 controls.

| Type | Seeded | Caught | Deterministic | Semantic | Both | Unclassified | No answer | Sound-control trials | Headline rate (95% CI) | All-cards rate (95% CI) | Checks that rejected seeds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| evidence_value | 10 | 10 | 10 | 0 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | recompute: 10 |
| baseline_value | 10 | 10 | 10 | 0 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | recompute: 10 |
| unsupported_number | 10 | 10 | 10 | 10 | 10 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | number_check: 10, semantic_check: 10 |
| claim_direction | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | semantic_check: 10 |
| wrong_team | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | semantic_check: 10 |
| overcertainty | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 5 | 100.0% ([56.6, 100.0]; n=5; Wilson) | 100.0% ([56.6, 100.0]; n=5; Wilson) | semantic_check: 5 |
| unnamed_cause | 10 | 9 | 0 | 9 | 0 | 0 | 0 | 10 | 90.0% ([59.6, 98.2]; n=10; Wilson) | 90.0% ([59.6, 98.2]; n=10; Wilson) | semantic_check: 9 |
| primary_direction | 10 | 10 | 5 | 5 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | contradiction_check: 5, semantic_check: 5 |
| Total | 75 | 74 | 35 | 49 | 10 | 0 | 0 | 75 | 98.7% ([92.8, 99.8]; n=75; Wilson) | 98.7% ([92.8, 99.8]; n=75; Wilson) | See per-type checks |

| Card / case | Type | Result | Check / applicability |
|---|---|---|---|
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | control | passed | none |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | evidence_value | caught | recompute |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | baseline_value | caught | recompute |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | unsupported_number | caught | number_check, semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | claim_direction | caught | semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | wrong_team | caught | semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | overcertainty | caught | semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | unnamed_cause | caught | semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | primary_direction | caught | contradiction_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | control | passed | none |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | evidence_value | caught | recompute |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | baseline_value | caught | recompute |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | claim_direction | caught | semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | wrong_team | caught | semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | overcertainty | caught | semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | unnamed_cause | caught | semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | primary_direction | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | control | passed | none |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | evidence_value | caught | recompute |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | baseline_value | caught | recompute |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | claim_direction | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | wrong_team | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | overcertainty | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | unnamed_cause | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | primary_direction | caught | contradiction_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | control | passed | none |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | evidence_value | caught | recompute |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | baseline_value | caught | recompute |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | claim_direction | caught | semantic_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | wrong_team | caught | semantic_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | unnamed_cause | caught | semantic_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | primary_direction | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | control | passed | none |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | evidence_value | caught | recompute |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | baseline_value | caught | recompute |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | claim_direction | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | wrong_team | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | overcertainty | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | unnamed_cause | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | primary_direction | caught | contradiction_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | control | passed | none |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | evidence_value | caught | recompute |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | baseline_value | caught | recompute |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | claim_direction | caught | semantic_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | wrong_team | caught | semantic_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | unnamed_cause | missed | none |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | primary_direction | caught | semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | control | passed | none |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | evidence_value | caught | recompute |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | baseline_value | caught | recompute |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | claim_direction | caught | semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | wrong_team | caught | semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | unnamed_cause | caught | semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | primary_direction | caught | contradiction_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | control | passed | none |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | evidence_value | caught | recompute |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | baseline_value | caught | recompute |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | unsupported_number | caught | number_check, semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | claim_direction | caught | semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | wrong_team | caught | semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | overcertainty | caught | semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | unnamed_cause | caught | semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | primary_direction | caught | semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | control | passed | none |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | evidence_value | caught | recompute |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | baseline_value | caught | recompute |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | claim_direction | caught | semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | wrong_team | caught | semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | unnamed_cause | caught | semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | primary_direction | caught | contradiction_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | control | passed | none |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | evidence_value | caught | recompute |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | baseline_value | caught | recompute |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | claim_direction | caught | semantic_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | wrong_team | caught | semantic_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | unnamed_cause | caught | semantic_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | primary_direction | caught | semantic_check |

Seeded Verifier run: seeded-A-3ad5e530026dcede (dev — tuning only, A; 10 card clusters).
Sound-control catch rate: 98.7% ([92.8, 99.8]; n=75; Wilson). All-cards catch rate: 98.7% ([92.8, 99.8]; n=75; Wilson). Controls rejected: 0.0% ([0.0, 27.8]; n=10; Wilson).
No answer: 0 seeded trials; 0 controls.

| Type | Seeded | Caught | Deterministic | Semantic | Both | Unclassified | No answer | Sound-control trials | Headline rate (95% CI) | All-cards rate (95% CI) | Checks that rejected seeds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| evidence_value | 10 | 10 | 10 | 0 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | recompute: 10 |
| baseline_value | 10 | 10 | 10 | 0 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | recompute: 10 |
| unsupported_number | 10 | 10 | 10 | 10 | 10 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | number_check: 10, semantic_check: 10 |
| claim_direction | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | semantic_check: 10 |
| wrong_team | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | semantic_check: 10 |
| overcertainty | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 5 | 100.0% ([56.6, 100.0]; n=5; Wilson) | 100.0% ([56.6, 100.0]; n=5; Wilson) | semantic_check: 5 |
| unnamed_cause | 10 | 9 | 0 | 9 | 0 | 0 | 0 | 10 | 90.0% ([59.6, 98.2]; n=10; Wilson) | 90.0% ([59.6, 98.2]; n=10; Wilson) | semantic_check: 9 |
| primary_direction | 10 | 10 | 5 | 5 | 0 | 0 | 0 | 10 | 100.0% ([72.2, 100.0]; n=10; Wilson) | 100.0% ([72.2, 100.0]; n=10; Wilson) | contradiction_check: 5, semantic_check: 5 |
| Total | 75 | 74 | 35 | 49 | 10 | 0 | 0 | 75 | 98.7% ([92.8, 99.8]; n=75; Wilson) | 98.7% ([92.8, 99.8]; n=75; Wilson) | See per-type checks |

| Card / case | Type | Result | Check / applicability |
|---|---|---|---|
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | control | passed | none |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | evidence_value | caught | recompute |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | baseline_value | caught | recompute |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | unsupported_number | caught | number_check, semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | claim_direction | caught | semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | wrong_team | caught | semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | overcertainty | caught | semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | unnamed_cause | caught | semantic_check |
| m163/case-m163-081-fatigue_signal/ins-m163-081-fatigue_signal | primary_direction | caught | contradiction_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | control | passed | none |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | evidence_value | caught | recompute |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | baseline_value | caught | recompute |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | claim_direction | caught | semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | wrong_team | caught | semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | overcertainty | caught | semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | unnamed_cause | caught | semantic_check |
| m186/case-m186-065-pressure_shift/ins-m186-065-pressure_shift | primary_direction | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | control | passed | none |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | evidence_value | caught | recompute |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | baseline_value | caught | recompute |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | claim_direction | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | wrong_team | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | overcertainty | caught | semantic_check |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | unnamed_cause | missed | none |
| m186/case-m186-084-pressure_shift/ins-m186-084-pressure_shift | primary_direction | caught | contradiction_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | control | passed | none |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | evidence_value | caught | recompute |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | baseline_value | caught | recompute |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | claim_direction | caught | semantic_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | wrong_team | caught | semantic_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | unnamed_cause | caught | semantic_check |
| m193/case-m193-070-pressure_shift/ins-m193-070-pressure_shift | primary_direction | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | control | passed | none |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | evidence_value | caught | recompute |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | baseline_value | caught | recompute |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | claim_direction | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | wrong_team | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | overcertainty | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | unnamed_cause | caught | semantic_check |
| m193/case-m193-088-pressure_shift/ins-m193-088-pressure_shift | primary_direction | caught | contradiction_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | control | passed | none |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | evidence_value | caught | recompute |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | baseline_value | caught | recompute |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | claim_direction | caught | semantic_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | wrong_team | caught | semantic_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | unnamed_cause | caught | semantic_check |
| m194/case-m194-083-pressure_shift/ins-m194-083-pressure_shift | primary_direction | caught | semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | control | passed | none |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | evidence_value | caught | recompute |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | baseline_value | caught | recompute |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | claim_direction | caught | semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | wrong_team | caught | semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | unnamed_cause | caught | semantic_check |
| m216/case-m216-067-pressure_shift/ins-m216-067-pressure_shift | primary_direction | caught | contradiction_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | control | passed | none |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | evidence_value | caught | recompute |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | baseline_value | caught | recompute |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | unsupported_number | caught | number_check, semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | claim_direction | caught | semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | wrong_team | caught | semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | overcertainty | caught | semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | unnamed_cause | caught | semantic_check |
| m216/case-m216-073-shape_change/ins-m216-073-shape_change | primary_direction | caught | semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | control | passed | none |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | evidence_value | caught | recompute |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | baseline_value | caught | recompute |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | claim_direction | caught | semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | wrong_team | caught | semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | unnamed_cause | caught | semantic_check |
| m216/case-m216-077-pressure_shift/ins-m216-077-pressure_shift | primary_direction | caught | contradiction_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | control | passed | none |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | evidence_value | caught | recompute |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | baseline_value | caught | recompute |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | unsupported_number | caught | number_check, semantic_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | claim_direction | caught | semantic_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | wrong_team | caught | semantic_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | overcertainty | not applicable | strong support already permits assertive language |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | unnamed_cause | caught | semantic_check |
| m346/case-m346-073-pressure_shift/ins-m346-073-pressure_shift | primary_direction | caught | semantic_check |

Record provenance:

| Record | Split | Suite digest | Flag set | Model ID | Unverified |
|---|---|---|---|---|---|
| batch-A-715af4adadbb1553-wilson | heldout — reporting | 3302b1257b0ababd92e2aa3a80c1f3abce33561017b682ad9515ec0172928990 | flags-8f3cc9ec7424f5a1 | gpt-5-mini | wall_time_budget_s |
| batch-A-715af4adadbb1553-wilson-after-follow-up | heldout — reporting | 3302b1257b0ababd92e2aa3a80c1f3abce33561017b682ad9515ec0172928990 | flags-8f3cc9ec7424f5a1 | gpt-5-mini | wall_time_budget_s |
| batch-A-715af4adadbb1553-wilson-after-follow-up-vs-batch-B-ffa549873dee2dce-wilson-after-follow-up-cause_precision | heldout — reporting | 3302b1257b0ababd92e2aa3a80c1f3abce33561017b682ad9515ec0172928990 | flags-8f3cc9ec7424f5a1 | gpt-5-mini | wall_time_budget_s |
| batch-A-715af4adadbb1553-wilson-after-follow-up-vs-batch-B-ffa549873dee2dce-wilson-after-follow-up-planted_recall | heldout — reporting | 3302b1257b0ababd92e2aa3a80c1f3abce33561017b682ad9515ec0172928990 | flags-8f3cc9ec7424f5a1 | gpt-5-mini | wall_time_budget_s |
| batch-A-715af4adadbb1553-wilson-vs-batch-B-ffa549873dee2dce-wilson-cause_precision | heldout — reporting | 3302b1257b0ababd92e2aa3a80c1f3abce33561017b682ad9515ec0172928990 | flags-8f3cc9ec7424f5a1 | gpt-5-mini | wall_time_budget_s |
| batch-A-715af4adadbb1553-wilson-vs-batch-B-ffa549873dee2dce-wilson-planted_recall | heldout — reporting | 3302b1257b0ababd92e2aa3a80c1f3abce33561017b682ad9515ec0172928990 | flags-8f3cc9ec7424f5a1 | gpt-5-mini | wall_time_budget_s |
| batch-B-ffa549873dee2dce-wilson | heldout — reporting | 3302b1257b0ababd92e2aa3a80c1f3abce33561017b682ad9515ec0172928990 | flags-8f3cc9ec7424f5a1 | gpt-5-mini | wall_time_budget_s |
| batch-B-ffa549873dee2dce-wilson-after-follow-up | heldout — reporting | 3302b1257b0ababd92e2aa3a80c1f3abce33561017b682ad9515ec0172928990 | flags-8f3cc9ec7424f5a1 | gpt-5-mini | wall_time_budget_s |
| questions-heldout-A-99e67b73770ed5b8 | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-B-164d3953ee116a53-claim_precision | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-B-164d3953ee116a53-false_claims_per_question | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-B-164d3953ee116a53-false_premise_rejection | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-B-164d3953ee116a53-true_premise_accuracy | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-P-7bbae1678cd512dd-claim_precision | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-P-7bbae1678cd512dd-false_claims_per_question | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-P-7bbae1678cd512dd-false_premise_rejection | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-99e67b73770ed5b8-vs-questions-heldout-P-7bbae1678cd512dd-true_premise_accuracy | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353 | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-B-after-follow-up-02d7a3c686c8c36d-claim_precision | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-B-after-follow-up-02d7a3c686c8c36d-false_claims_per_question | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-B-after-follow-up-02d7a3c686c8c36d-false_premise_rejection | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-B-after-follow-up-02d7a3c686c8c36d-true_premise_accuracy | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-claim_precision | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-false_claims_per_question | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-false_premise_rejection | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-A-after-follow-up-cb4d5eb905e48353-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-true_premise_accuracy | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-B-164d3953ee116a53 | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin, token_usage |
| questions-heldout-B-164d3953ee116a53-vs-questions-heldout-P-7bbae1678cd512dd-claim_precision | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-B-164d3953ee116a53-vs-questions-heldout-P-7bbae1678cd512dd-false_claims_per_question | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-B-164d3953ee116a53-vs-questions-heldout-P-7bbae1678cd512dd-false_premise_rejection | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-B-164d3953ee116a53-vs-questions-heldout-P-7bbae1678cd512dd-true_premise_accuracy | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin, token_usage |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-claim_precision | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-false_claims_per_question | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-false_premise_rejection | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-B-after-follow-up-02d7a3c686c8c36d-vs-questions-heldout-P-after-follow-up-1b5aac88b41a7f17-true_premise_accuracy | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-P-7bbae1678cd512dd | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| questions-heldout-P-after-follow-up-1b5aac88b41a7f17 | heldout — reporting | 0a80210c7b057b4fddc062063dc718da2747301bd520aada25bda45f122f28df | not applicable / unrecorded | gpt-5-mini | suite_origin |
| seeded-A-0b1d9364658a4e69 | dev — tuning only | unverified | not applicable / unrecorded | gpt-5-mini | flag_set_id, suite_digest |
| seeded-A-3ad5e530026dcede | dev — tuning only | unverified | not applicable / unrecorded | Phi-4 | flag_set_id, suite_digest |
<!-- scoreboard:end -->
