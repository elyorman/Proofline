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
failed checks for every trial, including controls. Confidence intervals resample
whole cards with all their seed types together. False rejection is the fraction
of answered unchanged controls rejected. No-answer trials and controls are reported
separately, outside caught, missed and false-rejection denominators. The headline
catch rate uses only trials whose unchanged control passed; the all-cards rate is
reported beside it. A verifier that rejects every control has an undefined headline
rate. The number of live semantic calls is lower than
the Verifier invocation count when deterministic checks reject early; the
backend may retry a malformed semantic response.

No measured agent scoreboard or live seeded result ships with this implementation.
Tests use scripted models and the committed demo replay exchanges.

## Owner integration

Add `SeededRun` from `contracts.eval_run` to `scripts/export_schemas.py` as
`"seeded-run": SeededRun`, then export its JSON Schema. Add the README markers
and the scoreboard check to CI. Keep the backend's `started_at_ms` in every batch
file; the scorer uses the earliest recorded start (or an earlier explicit start)
for the flag-freeze check. Selecting a single suite from a combined batch folder
now ignores the other suite's files while still requiring every selected match.
