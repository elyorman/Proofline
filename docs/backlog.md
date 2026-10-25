# Known limits and open work

What is still open, so that nothing here contradicts the README. Close an item by deleting it in the commit that fixes it. The README's Limitations section lists what a viewer or judge should know; this list is the engineering behind it.

## Reasoning

1. **The multi-agent split.** Three specialists measured the same as one agent running the same design on held-out cases and questions. Untested: whether their independence shows up in cost, latency or what cross-examination refutes.
2. **A cause can survive on evidence unrelated to the change.** A hypothesis is tested on what its cause predicts, not on its link to the change it explains: the demo's 62' flank card names "chasing the result" because Harbour City's pressing really rose. A test that ties the cause to the change itself is not built.
3. **Detected moments.** Proofline names the planted cause on about a third of detected moments, and the follow-up did not improve that on held-out. Player fatigue is not watched by the detector.
4. **Which team a card is about** is still decided by a cause-to-team table (`cause_team`), not by the agent that registered the cause.
5. **Narration** is templates: they repeat the team's name and read the same every time. A case ranked `other` closes without a card.
6. **Spanish** sentences get the deterministic number check but not the semantic check; Foundry's evaluators read them instead (`eval/foundry_evals.py`).

## Runtime

1. **Recovery is in memory.** A failed agent is retried inside its stage, but a process that dies starts its open cases over; resuming from Agent Framework's stored checkpoints, and idempotent writes for cards, cues and amendments, are not built.
2. **The ledger.** The live API writes each answer's cards and an audit record to Cosmos DB, and `proofline ingest` writes events and detector cases; hypotheses, tests and tool calls live in case files, not in Cosmos.
3. **A strict publication boundary.** A card's status and verification are validated when built; validating every serialised card at each write, with explicit status transitions, is not built.
4. **Amendments end to end.** The Correction Watcher withdraws and revises cards in Studio and replay; amendments on the Event Hubs feed, the Watcher on the Cosmos change feed, and an Evaluator-scored correction suite are not built.
5. **The live API** runs one replica with its jobs and daily budget in memory; a restart forgets both.

## Evaluation and data

1. **Suite size.** 28 scored held-out planted matches and 10 decoys give wide intervals; an A-versus-B difference will rarely exclude zero.
2. **The question set's languages follow its order**: every true-premise question is English. Regenerating it would break the held-out freeze.
3. **Team identity.** A team's display name is its identifier, and unit and player membership is read from string prefixes.
4. **Engine realism.** Every shot ends at (105, 34); dribbles go straight ahead; sprint events depend on the seed, not on play; there are about 27 goal kicks a match and no corners; long-ball shares near 40% under a strong press. Fixing any of these changes the random draws, so the demo seed would be re-picked by its rule. Planted changes are second-half only.
5. **The demo feed's own consistency.** The flank amendment moves only Northvale's actions, so the first-delivered feed has 22 m jumps between consecutive Northvale actions.
