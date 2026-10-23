"""Run one detected case end to end: investigate, propose a card, verify it."""

import os
from dataclasses import dataclass
from pathlib import Path

from agents import single
from agents.llm import FoundryModel, Model, Recording, Replay
from agents.propose import propose
from agents.single import Finding
from agents.verifier.checks import Record
from agents.verifier.verify import Verdict, verify
from contracts.case import Case
from contracts.eval_run import Variant
from state.tools import Feed


@dataclass
class Outcome:
    finding: Finding
    verdict: Verdict | None  # None when the case closed without a card


async def run_case(
    variant: Variant, agents: Model, verifier: Model, case: Case, feed: Feed
) -> Outcome:
    if variant != Variant.B_SINGLE_AGENT:
        raise NotImplementedError(f"variant {variant} is not built yet")
    finding = await single.investigate(agents, case, feed)
    card = propose(finding, feed)
    if card is None:
        return Outcome(finding, None)
    record = Record.of(finding.tools.log, finding.evidence)
    return Outcome(finding, await verify(verifier, card, record, feed, finding.exams))


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
