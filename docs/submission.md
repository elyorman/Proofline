# Proofline: submission kit

Everything the project page needs: the pitch, the description, and testing instructions for judges. Figures are quoted from the evaluation records in [`eval/records/`](../eval/records/), as the README quotes them.

- **Public link (no sign-in):** https://nice-coast-044d8740f.5.azurestaticapps.net
- **Repository:** https://github.com/elyorman/Proofline
- **Video:** added after recording
- **Category:** Best Multi-Agent System

## Elevator pitch

Proofline is match intelligence that shows its evidence, knows its limits, and corrects itself. Statistics decides what is real; agents decide why. Code checks every change, and every viewer's premise, against a season of normal variation before any model sees it. Three specialist agents on Microsoft Foundry pre-register what their causes would predict. Code tests each prediction through our MCP server, and the agents cross-examine each other's survivors. An independent Verifier recomputes every number and checks every sentence. When the feed is corrected, every card that relied on it is revised or withdrawn on every screen. On held-out matches it made far fewer false claims than a plain tool-using agent.

## Description

### The problem

A stats feed can tell you a team's pressing jumped after 58'. It cannot tell you why: a decision to press higher, a team chasing a 1-3 scoreline, or the opponent pushing up into the press all move the same numbers. A language model will pick one and explain it fluently. It will just as fluently explain a change that never happened, if the viewer's question assumes it. For broadcasters, one confident wrong claim on air costs more trust than ten right ones earn.

### What Proofline does

- **Code decides what is real.** A detected change must stay beyond normal variation for five more minutes. A viewer's question is turned into one measurable premise and tested the same way. "Is Ambrel tiring?" gets "not beyond ordinary play" when the numbers say so.
- **Specialist agents decide why, and code scores them.** Tactics, Physical and Game-State each register causes in their own domain, with predictions in numbers, before any tool runs. Code runs every test through the State Builder's tools. The agents then cross-examine each other's survivors with counter-tests they design, and code refuses unfair ones. A synthesis step ranks what survived.
- **It keeps watching when the evidence can't decide.** If two causes still fit, the card says so. Each side bets on the next 15 minutes, and code settles the bet in a new revision.
- **Nothing reaches a viewer unverified.** The Verifier recomputes every number from the exact events it came from and checks every sentence against the facts at the wording the evidence allows.
- **It corrects itself.** When the feed amends events, the Correction Watcher finds every dependent card and revises or withdraws it on the fan view, the analyst console and the broadcast cue feed. History stays visible.
- **One verified insight, three experiences.** A fan view in English or Spanish around your club and player, with a live pitch, momentum and control-vs-chaos. An analyst console with the full case file. Broadcast cues with approve, hold and kill.
- **Ask anything, live.** A typed question no recording holds runs through the real agents in Azure, and the page shows each stage as it is reached.

### Built on Microsoft

- **Microsoft Foundry:** gpt-5-mini for every role, the Verifier's semantic check, and Foundry's built-in evaluators judging the published text.
- **Microsoft Agent Framework:** the Why Engine workflow (parallel specialists, code tests, cross-examination, synthesis) with checkpointed recovery, and its OpenTelemetry instrumentation.
- **A custom MCP server** for the State Builder's tools, and the **Azure MCP Server** to check the deployment.
- **Azure Container Apps and Container Registry:** the live question API, keyless, through a managed identity.
- **Application Insights:** a trace of every live question, with the workflow, each agent and every model call.
- **Event Hubs and Cosmos DB:** the match feed and the ledger of events, cases, cards and audit records.
- **Static Web Apps:** the public replay.
- **azd, Bicep and GitHub Actions:** one-command provisioning and CI that fails if the README quotes a number no evaluation record holds.

### What we measured

All on a held-out split with sealed ground truth, run once after the agents were frozen:

- **False causes:** after the follow-up, 3.8% of questions get one from Proofline, against 34.6% from a plain tool-using agent with the same model and tools.
- **False premises:** Proofline turns away 98.0%, against 70.0% for the plain agent.
- **The price is coverage.** The plain agent names the planted cause for more true premises.
- **Three specialists measured the same as one agent running the same design.** We publish that too. The gain over the plain agent comes from the design: statistics first, pre-registration, and independent verification by a role that shares none of the agents' context.

## Testing instructions for judges

No sign-in is needed. The replay starts paused at 68:00, viewed as a Northvale fan reading Spanish; the language switch is in the top bar. Each link below opens a view at a given minute and language:

1. **Fan view**, at https://nice-coast-044d8740f.5.azurestaticapps.net/#/fan?t=68:00&lang=en.
   - The pitch shows the last moments of play; the card beside it says why Harbour City are pressing harder, and what it will check by 83'.
   - Open "All evidence and checks" on the card.
   - Use the moment chips, or press play.
2. **The correction**, at https://nice-coast-044d8740f.5.azurestaticapps.net/#/fan?t=70:00&lang=en.
   - The feed corrects Northvale's coordinates, and the right-flank card is withdrawn in place.
   - At 77' and 83' the follow-ups settle.
3. **Ask Proofline** (fan view, below the cards).
   - The five suggestions replay recorded answers.
   - Then type your own question about the match so far, in the second half. It is answered live in Azure, and you can watch the stages:
     - "Is Ambrel running out of legs?" at 76:00 is turned away in seconds.
     - "Why have Harbour City been pressing so high since 58?" at 68:00 runs the full investigation in one to three minutes.
   - Ask as many as you like, one at a time. A generous daily budget only stops a single visitor from scripting through it.
4. **Analyst console**, at https://nice-coast-044d8740f.5.azurestaticapps.net/#/analyst?t=68:00&lang=en.
   - The 63' case shows each specialist's pre-registered causes and code's verdicts, the cross-examination, the refusals and the Verifier's checks.
   - "Compare with one agent" sets it beside the single-agent run.
   - The Evaluation tab shows the scoreboard.
5. **Broadcast studio**, at https://nice-coast-044d8740f.5.azurestaticapps.net/#/broadcast?t=70:30&lang=en.
   - Approve the pending withdrawal cue, then switch to **Overlay** in the sidebar to see it on air. Decisions live in this browser tab only.
6. **The code.**
   - The README's "Run it" section replays everything without Azure: `uv sync`, `uv run pytest`.
   - It also lists the commands that run the agents live on your own subscription.

Every club, player and competition is fictional, and all match data is synthetic.
