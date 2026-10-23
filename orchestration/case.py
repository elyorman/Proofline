"""Run one detected case end to end: investigate, propose a card, verify it."""

import os
from dataclasses import dataclass
from pathlib import Path

from agents import single
from agents.llm import FoundryModel, Model, Recording, Replay, Usage
from agents.propose import propose
from agents.single import Finding
from agents.verifier.checks import Record
from agents.verifier.verify import Verdict, verify
from contracts.case import Case, CaseStage
from contracts.case_file import CaseFile, CaseRanking, RefusedProposal, ToolCall
from contracts.eval_run import Variant
from contracts.taxonomy import AgentRole
from orchestration import workflow
from state.tools import Feed


@dataclass
class Outcome:
    finding: Finding
    verdict: Verdict | None  # None when the case closed without a card


async def run_case(
    variant: Variant,
    agents: Model,
    verifier: Model,
    case: Case,
    feed: Feed,
    stop: dict[AgentRole, int] | None = None,
) -> Outcome:
    """Investigate with variant A (the workflow) or B (one agent), then propose and verify."""
    if variant == Variant.A_PROOFLINE:
        finding = await workflow.investigate(agents, case, feed, stop)
    elif variant == Variant.B_SINGLE_AGENT:
        finding = await single.investigate(agents, case, feed)
    else:
        raise NotImplementedError(f"variant {variant} is a stretch, not built")
    card = propose(finding, feed)
    if card is None:
        return Outcome(finding, None)
    record = Record.of(finding.tools.log, finding.evidence)
    return Outcome(finding, await verify(verifier, card, record, feed, finding.exams))


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


def models(record: Path | None = None, replay: Path | None = None) -> tuple[Model, Model]:
    """(agents' model, verifier's model): live, live and recorded, or replayed."""
    if replay is not None:
        return Replay(replay), Replay(replay)
    agents = FoundryModel.from_env()
    deployment = os.environ["AZURE_VERIFIER_DEPLOYMENT"]
    verifier = FoundryModel(agents.project_endpoint, deployment, structured=False)
    if record is None:
        return agents, verifier
    return Recording(agents, record), Recording(verifier, record)
