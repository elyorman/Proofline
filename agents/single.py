"""Variant B: one agent with every tool and the case's whole budget (spec §11.2).

It pre-registers causes from any domain, code tests each one, and the same agent ranks what
survives. There is no cross-examination: that is what variant A adds.
"""

from dataclasses import dataclass, field

from agents.investigation import Refused, Tested, Tools, rank, register, run_test
from agents.llm import Model, Usage
from agents.outputs import Ranking
from contracts.case import Case, Checkpoint
from contracts.prediction import CrossExamination, Hypothesis
from contracts.taxonomy import AgentRole
from contracts.tool_result import EvidenceSet
from state.tools import Feed
from tools_server.server import FeedSource, MemorySink, build_server

MAX_HYPOTHESES = 6  # what three domain agents may register between them


@dataclass
class Finding:
    """What an investigation concluded, with everything a card and the Verifier need."""

    case: Case
    agents: list[AgentRole]
    hypotheses: list[Hypothesis]
    refused: list[Refused]
    tested: list[Tested]
    ranking: Ranking
    score: dict[str, float]
    tools: Tools
    evidence: dict[str, EvidenceSet]
    usage: Usage
    exams: list[CrossExamination] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    unrun: list[str] = field(default_factory=list)  # counter-tests refused or not measurable
    recovered: bool = False  # an agent was retried from its checkpoint

    def tested_by_id(self, hypothesis_id: str) -> Tested:
        return next(t for t in self.tested if t.hypothesis.hypothesis_id == hypothesis_id)


def case_tools(case: Case, feed: Feed) -> tuple[Tools, MemorySink]:
    """The MCP tools for one case, fixed at the moment it was detected."""
    sink = MemorySink()
    server = build_server(FeedSource({case.match_id: feed}), sink, {case.match_id: case.window.end})
    return Tools(server, case.match_id, case.tool_call_budget), sink


async def investigate(model: Model, case: Case, feed: Feed) -> Finding:
    tools, sink = case_tools(case, feed)
    score = (await tools.call("game_state")).values
    role = AgentRole.SINGLE
    hypotheses, refused, usage = await register(model, role, case, feed.meta, score, MAX_HYPOTHESES)
    tested = [await run_test(tools, h) for h in hypotheses]
    survivors = [t for t in tested if t.supported]
    ranking, ranked = await rank(model, role, case, feed.meta, score, survivors)
    return Finding(
        case=case,
        agents=[role],
        hypotheses=hypotheses,
        refused=refused,
        tested=tested,
        ranking=ranking,
        score=score,
        tools=tools,
        evidence=sink.evidence,
        usage=usage + ranked,
    )
