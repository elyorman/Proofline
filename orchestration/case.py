"""Run one detected case end to end: investigate, propose a card, verify it, and keep
watching when a rival cause survived (agents/follow_up.py)."""

import os
from dataclasses import dataclass
from pathlib import Path

from agents import single
from agents.confirm import both_teams, confirm, explained, extended
from agents.follow_up import open_follow_up, resolved, settle
from agents.llm import FoundryModel, Model, Recording, Replay, Usage
from agents.outputs import Ranking
from agents.propose import propose
from agents.single import Finding, case_tools
from agents.verifier.checks import Record
from agents.verifier.verify import Verdict, verify
from contracts.card import InsightCard
from contracts.case import Case, CaseStage
from contracts.case_file import CaseFile, CaseRanking, RefusedProposal, ToolCall
from contracts.eval_run import Variant
from contracts.taxonomy import AgentRole, CardStatus
from orchestration import workflow
from state.tools import Feed


@dataclass
class Outcome:
    finding: Finding
    verdict: Verdict | None  # None when the case closed without a card
    followed: Verdict | None = None  # the card's next revision once its follow-up settled


async def keep_watching(
    agents: Model, verifier: Model, finding: Finding, card: InsightCard, feed: Feed
) -> tuple[Verdict, Verdict | None]:
    """Verify the card, opening a follow-up first if a rival survived, so its promise is
    verified too; then settle the follow-up and verify the revision it makes."""
    opened = await open_follow_up(agents, finding, card, feed)
    finding.usage = finding.usage + opened.usage
    if opened.follow_up:
        card = InsightCard.model_validate(card.model_dump() | {"follow_up": opened.follow_up})
    record = Record.of(finding.tools.log, finding.evidence)
    verdict = await verify(verifier, card, record, feed, finding.exams)
    if not opened.follow_up or verdict.card.status != CardStatus.VERIFIED:
        return verdict, None
    settled = await settle(opened.follow_up, feed)
    candidate = resolved(verdict.card, settled, finding, feed)
    both = Record.of(
        finding.tools.log + settled.tools.log, finding.evidence | settled.sink.evidence
    )
    followed = await verify(verifier, candidate, both, feed, finding.exams)
    if followed.card.status == CardStatus.VERIFIED:  # a later revision of a shown card
        followed.card = followed.card.model_copy(update={"status": CardStatus.REVISED})
    return verdict, followed


async def run_case(
    variant: Variant,
    agents: Model,
    verifier: Model,
    case: Case,
    feed: Feed,
    stop: dict[AgentRole, int] | None = None,
) -> Outcome:
    """Confirm the detected change on the minutes after it fired; if it held, investigate with
    variant A (the workflow) or B (one agent) over the window run on to that minute, then
    propose and verify. Both variants share the confirmation, which asks no model."""
    if variant not in (Variant.A_PROOFLINE, Variant.B_SINGLE_AGENT):
        raise NotImplementedError(f"variant {variant} is a stretch, not built")
    case = extended(case)
    opened = case_tools(case, feed)
    persisted = await confirm(opened[0], case, feed.meta)
    if not any(p.holds for p in persisted):
        best = max(persisted, key=lambda p: p.sigmas if p.sigmas is not None else -99)
        tools, sink = opened
        return Outcome(
            Finding(
                case=case,
                agents=[],
                hypotheses=[],
                refused=[],
                tested=[],
                ranking=Ranking(outcome="none", primary=None, secondary=[], why=best.reason),
                score={},
                tools=tools,
                evidence=sink.evidence,
                usage=Usage(),
                confirmation=persisted,
            ),
            None,
        )
    case = case.model_copy(update={"both_teams": both_teams(feed, case.window)})
    held = max((p for p in persisted if p.holds), key=lambda p: p.sigmas)
    change = await explained(opened[0], held.metric, held.subject, held.direction, case.window)
    if variant == Variant.A_PROOFLINE:
        finding = await workflow.investigate(agents, case, feed, stop, opened)
    else:
        finding = await single.investigate(agents, case, feed, opened)
    finding.confirmation, finding.explained = persisted, change
    card = propose(finding, feed)
    if card is None:
        return Outcome(finding, None)
    return Outcome(finding, *await keep_watching(agents, verifier, finding, card, feed))


def _call(entry: dict) -> ToolCall:
    result = entry.get("result", {})
    return ToolCall(
        tool=entry["tool"],
        arguments=entry["arguments"],
        tool_call_id=result.get("tool_call_id"),
        value=result.get("value"),
        baseline=(result.get("baseline") or {}).get("value"),
        n_events=result.get("n_events"),
        values=result.get("values", {}),
        insufficient_data=result.get("insufficient_data"),
        error=entry.get("error"),
    )


def case_file(outcome: Outcome, variant: Variant) -> CaseFile:
    """Everything a closed case's investigation did, for the Analyst Console (spec §12.2)."""
    f = outcome.finding
    card = outcome.verdict.card if outcome.verdict else None
    usage = f.usage + (outcome.verdict.usage if outcome.verdict else Usage())
    case = Case.model_validate(
        f.case.model_dump(mode="json")
        | {
            "stage": CaseStage.CLOSED,
            "outcome": f.ranking.outcome,
            "hypothesis_ids": [h.hypothesis_id for h in f.hypotheses],
            "checkpoints": [c.model_dump(mode="json") for c in f.checkpoints],
            "recovered_from_checkpoint": f.recovered,
            "tool_calls_used": f.tools.used,
            "card_id": card.id if card else None,
        }
    )
    return CaseFile(
        case=case,
        variant=variant,
        confirmation=f.confirmation,
        agents=f.agents,
        hypotheses=f.hypotheses,
        refused=[
            RefusedProposal(
                agent=r.agent,
                cause=r.proposal.cause,
                metric=r.proposal.metric,
                subject=r.proposal.subject,
                reason=r.reason,
            )
            for r in f.refused
        ],
        tests=[t.test for t in f.tested],
        cross_examinations=f.exams,
        unrun=f.unrun,
        ranking=CaseRanking(**f.ranking.model_dump()),
        tool_calls=[_call(e) for e in f.tools.log],
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )


def models(
    record: Path | None = None, replay: Path | None = None, reverify: Path | None = None
) -> tuple[Model, Model]:
    """(agents' model, verifier's model): live, live and recorded, or replayed; or, with
    `reverify`, the agents' recorded answers with only the Verifier live (and recorded). The
    Verifier runs on Foundry, on the deployment AZURE_VERIFIER_DEPLOYMENT names (spec §15),
    sent only the card's facts and sentences, never their reasoning."""
    if replay is not None:
        return Replay(replay), Replay(replay)
    endpoint, deployment = (
        os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"],
        os.environ["AZURE_VERIFIER_DEPLOYMENT"],
    )
    verifier = FoundryModel(endpoint, deployment, structured=False)
    if reverify is not None:
        return Replay(reverify), Recording(verifier, record) if record else verifier
    agents = FoundryModel.from_env()
    if record is None:
        return agents, verifier
    return Recording(agents, record), Recording(verifier, record)
