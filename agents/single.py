"""Variant B: one agent with every tool and the case's whole budget (spec §11.2).

It pre-registers causes from any domain, code tests each one, the same agent cross-examines
its own survivors with the counter-tests the three agents put to each other, code scores
them, and the agent ranks what is left. What variant A adds is independence: there, the
challenger has no stake in the cause it tests.
"""

from dataclasses import dataclass, field

from agents.cross_exam import Examined, challenge, settle
from agents.investigation import Refused, Tested, Tools, rank, register, run_test
from agents.llm import Model, Usage
from agents.outputs import Ranking
from contracts.case import Case, Checkpoint
from contracts.case_file import Persistence
from contracts.prediction import CrossExamination, Hypothesis, Prediction
from contracts.taxonomy import AgentRole
from contracts.tool_result import EvidenceSet, ToolResult
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
    corroborations: list[Examined] = field(default_factory=list)  # corollaries that held
    checkpoints: list[Checkpoint] = field(default_factory=list)
    unrun: list[str] = field(default_factory=list)  # counter-tests refused or not measurable
    recovered: bool = False  # an agent was retried from its checkpoint
    confirmation: list[Persistence] = field(default_factory=list)
    # The confirmed change the card explains, over the case's window (agents.confirm.explained).
    explained: tuple[Prediction, ToolResult, ToolResult] | None = None

    def tested_by_id(self, hypothesis_id: str) -> Tested:
        return next(t for t in self.tested if t.hypothesis.hypothesis_id == hypothesis_id)


def case_tools(case: Case, feed: Feed) -> tuple[Tools, MemorySink]:
    """The MCP tools for one case, fixed at the end of its window."""
    sink = MemorySink()
    server = build_server(FeedSource({case.match_id: feed}), sink, {case.match_id: case.window.end})
    return Tools(server, case.match_id, case.tool_call_budget), sink


async def investigate(
    model: Model, case: Case, feed: Feed, opened: tuple[Tools, MemorySink] | None = None
) -> Finding:
    tools, sink = opened or case_tools(case, feed)
    score = (await tools.call("game_state")).values
    role, meta = AgentRole.SINGLE, feed.meta
    hypotheses, refused, usage = await register(model, role, case, meta, score, MAX_HYPOTHESES)
    tested = [await run_test(tools, h, meta) for h in hypotheses]
    survivors = [t for t in tested if t.supported]
    try:
        proposed, refusals, checked = await challenge(model, role, case, meta, score, survivors)
    except ValueError:  # no answer in time: the survivors are ranked unchecked
        proposed, refusals, checked = [], [], Usage()
    settled = await settle(tools, meta, tested, proposed, refusals)
    ranking, ranked = await rank(model, role, case, meta, score, settled.survivors, settled.notes)
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
        usage=usage + checked + ranked,
        exams=settled.exams,
        corroborations=settled.corroborations,
        unrun=settled.unrun,
    )
