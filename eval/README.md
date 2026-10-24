# Record-backed scoreboard

Score a complete batch and retain both source runs and their paired comparison:

```bash
uv run python -m eval --runs runs/dev --split dev --compare A B --record-dir eval/records
uv run python -m eval scoreboard --records eval/records
uv run python -m eval scoreboard --records eval/records --check README.md
```

Records refuse overwrites. A comparison reuses already saved, identical input runs;
it does not rewrite their scoring timestamps. Commit the generated records before
quoting their numbers. Dev is labelled as tuning; heldout is reporting. Every run,
exclusion, seed type and missing provenance field remains visible. Missing model
and budget metadata are explicitly unverified; supply the corresponding CLI flags
only from the producer's recorded configuration.

The owner adds exactly one pair of `<!-- scoreboard:start -->` and
`<!-- scoreboard:end -->` markers to the README. Put a newline after the first
marker, followed by the exact generated output and the end marker. The check
compares this content byte for byte and never edits the README.

## Seeded Verifier benchmark

```bash
uv run python -m eval seeded --runs runs/dev --variant A --data data/dev \
  --exchanges runs/dev/exchanges-A --record runs/dev/seeded-exchanges-A \
  --limit 5 --concurrency 1 --record-dir eval/records

uv run python -m eval seeded --runs runs/dev --variant A --data data/dev \
  --exchanges runs/dev/exchanges-A --replay runs/dev/seeded-exchanges-A \
  --record-dir eval/records
```

Use a separate directory for the seeded Verifier's exchanges. To reproduce the
run without live model calls, use the replay command above. The saved settings
restore the model ID, explicit run ID, limit, and bootstrap settings. Replay
verifies an existing record without rewriting it. If the record is absent, it
prints the reproduced result and says that nothing was written. An
optional `--eval-run eval/records/<run_id>.json` links the exact source batch's
suite digest and frozen flag set. Otherwise those fields remain unverified.
Each card and seed has its own exchange namespace so identical prompts cannot
overwrite one another's responses. A live recording requires a fresh directory.

Each selected published card is reconstructed using only its batch exchanges.
The reconstructed card must equal the batch card except for `provenance.trace_id`.
All reconstructions must pass before seeded verification starts. Tool/evidence
references are deterministic; a mismatch indicates different feeds, exchanges or
producer code. Card digests omit only the trace ID, preserving record/replay identity.

There are up to eight single-field seeds plus one unchanged control per card.
Evidence and baseline perturbations are the first larger floating-point value
that changes the two-decimal display. Other seeds add an unsupported number,
reverse the claim's direction, name the other team, overstate certainty, name an
unattributed cause, or reverse the primary change proposition. Overcertainty is
inapplicable when strong support already permits assertive wording; its reason is
retained. Other applicable misses remain in the denominator.

The existing Verifier is called unchanged. Record its actual verification and
failed checks for every trial, including controls. Standalone proportions use two-sided 95% Wilson score intervals, including
all-success and all-failure samples. False rejection is the fraction
of answered unchanged controls rejected. No-answer trials and controls are reported
separately, outside caught, missed and false-rejection denominators. The headline
catch rate uses only trials whose unchanged control passed; the all-cards rate is
reported beside it. A verifier that rejects every control has an undefined headline
rate. The number of live semantic calls is lower than
the Verifier invocation count when deterministic checks reject early; the
backend may retry a malformed semantic response.

Tests use scripted models and the committed demo replay exchanges. A real-batch
regression reconstructs cards and compares record/replay results without patching
`run_case`. No live model calls are needed for validation.

## Question records and paired comparisons

Use fresh output directories for a new experiment. Generate questions before
running the product, so their manifest records the exact suite version:

```bash
for split in dev heldout; do
  root="runs/questions-${split}-v2"
  uv run python -m eval.questions make --split "$split" --out "$root/questions.jsonl"
  for variant in A B P; do
    uv run proofline questions --data "data/$split" --questions "$root/questions.jsonl" \
      --variant "$variant" --out "$root" --record "$root/exchanges-$variant"
    uv run python -m eval.questions score --runs "$root" --split "$split" \
      --variant "$variant" --model-id "$AZURE_OPENAI_DEPLOYMENT" \
      --tool-call-budget 16 --record-dir eval/records
  done
  uv run python -m eval.questions score --runs "$root" --split "$split" --compare A P \
    --model-id "$AZURE_OPENAI_DEPLOYMENT" --tool-call-budget 16 --record-dir eval/records
  uv run python -m eval.questions score --runs "$root" --split "$split" --compare A B \
    --model-id "$AZURE_OPENAI_DEPLOYMENT" --tool-call-budget 16 --record-dir eval/records
  uv run python -m eval.questions score --runs "$root" --split "$split" --compare B P \
    --model-id "$AZURE_OPENAI_DEPLOYMENT" --tool-call-budget 16 --record-dir eval/records
done
```

The data feeds must already exist. A and B use their normal agents and Verifier;
P is the plain tool-using baseline. All scoring commands are offline. Use model
and budget flags only when they describe the actual producer configuration.
`--out PATH` additionally writes a new JSON file. Records refuse overwrites.

Question metrics include missing and failed questions in their applicable
denominators. True-premise accuracy requires a verified card naming the planted
class and team. False-premise rejection requires an explicit `premise_false` response
(or `happening=false` for P). An `unanswerable` response is counted separately
and contributes zero to this rejection metric. Per-question `right` still retains
the spec's no-published-cause condition on false premises. False claims per question counts every wrong published cause; lower is
better. Claim precision counts right claims over all claims and is undefined
when there are no claims. Standalone rates use two-sided 95% Wilson intervals; per-run `n` is the metric
denominator. These binomial intervals treat denominator trials as independent.
Paired differences retain joint bootstrap draws over whole matches.

Comparisons pair only questions answered by both variants and retain unpaired
IDs. They require identical question sets, suites, splits, models and budgets;
two unknown model/budget values remain explicitly unverified. Select another
metric with `--metric false_premise_rejection`, `false_claims_per_question`, or
`claim_precision`. Comparison `n` is the eligible paired question count, or the
full paired question count for precision, whose two denominators may differ.

Older question files without a generation manifest can be scored when their
contents match the sealed suite, but their suite origin is labelled unverified.
Tokens sum recorded answer usage; missing/error replies make usage incomplete.
Copied runs, including the owner's q3 run, belong only in ignored storage. Tests
build their inputs from committed files and never depend on `runs/` or `data/`.

## Analyst Console JSON

```bash
uv run python -m eval scoreboard --records eval/records --json
```

The Markdown and JSON views use only saved records. Root `schema_version` is 1;
root `records` contains every record, and `question_suites` groups the A/B/P table
by split, question-set digest and suite digest. Values and confidence bounds are
fractions; a displayed percentage or percentage-point difference multiplies
those values by 100. No undefined rate is replaced with zero.

| Field | Content |
|---|---|
| `records[].id`, `record_type` | The saved ID; `detector_run`, `question_run`, `variant_comparison`, `question_comparison`, or `seeded_verifier` |
| `records[].metrics` | Estimates with `name`, `suite`, `value`, `ci_low`, `ci_high`, `n`, `ci_method`; `undefined_metrics` names absent estimates |
| `records[].exclusions` | Every frozen exclusion, including its cause, rule and observable checks |
| `records[].differences` | Recorded paired differences; question comparisons also retain paired/unpaired IDs |
| `records[].citations` | Record filename, suite/question digests, flag set, model ID, tool budget and `unverified` field names |
| `records[].bootstrap_unit` | `match` for paired differences; null for Wilson rates; legacy bootstrap records retain their unit |
| Seeded `catch_rate`, `all_cards_catch_rate`, `false_rejection_rate` | Headline, all-card and control estimates; each may be null |
| Seeded `types`, `cards` | Per-type counts/estimates; every trial's mutation, verification, `result` and rejecting `checks`; controls include their result/checks |
| Question `rows` | Every question's text, premise label, answer/claim outcome, missing/error state and available usage |
| `question_suites[].metrics[].variants` | A/B/P arrays of `{run_id, estimate}`; every run is retained, including multiple configurations |
| `question_suites[].coverage` | Answered, total, failed, missing, unanswerable and premise-rejected counts and token completeness per run |

Seeded `result` is `caught`, `missed`, `no_answer` or `not_applicable`. No-answer
counts stay separate for seeds and controls. Sound-control eligibility and
all-card counts are retained per type, so rejection-only behavior remains visible.

## Owner integration

The schema registry exports `SeededRun` and `QuestionRun`. Add the README markers
and the scoreboard check to CI when publishing records. Keep the backend's `started_at_ms` in every batch
file; the scorer uses the earliest recorded start (or an earlier explicit start)
for the flag-freeze check. Creating batch runs or comparisons requires
`started_at_ms` in every selected match file, including matches with no cases.
This applies to stdout JSON, `--out` and `--record-dir`; an explicit
`--started-at-ms` cannot replace missing source timestamps. Selecting a single
suite from a combined batch folder ignores the other suite's files while still
requiring every selected match.

New standalone rates record `ci_method: "wilson"`; paired differences record
`"paired_match_bootstrap"`. Older records without a method stay labelled
"method unrecorded" and are never silently recomputed. Fresh automatic run IDs
include the scoring revision, avoiding collisions with earlier bootstrap records.

Seeded catch columns distinguish deterministic checks (recompute, baseline,
sample size, contradiction, numeric grounding and support rules) from answered
semantic failures. A trial may appear in both columns: `both_caught` records the
overlap, so deterministic + semantic - both + unclassified equals total caught.
No-answer trials count in neither column. JSON retains these counts per type,
in `catch_counts` totals, and the two flags on each trial. These counts cover
all tested cards; the headline rate still conditions on sound controls.

Question record version 2 distinguishes explicit premise rejection from
unanswerable or other no-cause replies. Version 1 records retain their original
no-cause rate and carry a legacy-definition label; comparisons refuse to mix
versions. Structured unanswerable responses remain in paired cohorts, contributing
zero to premise rejection, while errors and missing replies are unpaired.

Answers join by `(match_id, exact question text)`, with matching asked time and
locale required. Question IDs may differ between the question file and answers;
they remain row labels, not join keys. Duplicate answer content is rejected even
when its IDs differ. Input question row labels must remain unique. New manifests
and question-set digests omit IDs; older ID-bearing manifests are still checked
using their original digest rule. Paired comparisons also join by match/text,
and their paired/unpaired ID lists use the first run's row labels.
