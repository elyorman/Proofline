"""Variant A, the Why Engine proper, as a Microsoft Agent Framework workflow (spec §9.1):
three domain agents pre-register in parallel, code tests every hypothesis, the agents
cross-examine each other's survivors in parallel, code scores the counter-tests, and a
synthesis agent ranks what is left. A checkpoint closes every stage.

An agent that fails or times out is retried once from its stage's checkpoint; if it fails
again the case completes with the others, and either way the case is flagged
`recovered_from_checkpoint` (spec §14).
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Never

from agent_framework import (
    Executor,
    InMemoryCheckpointStorage,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)

from agents.cross_exam import Refusal, challenge, run_counter
from agents.investigation import Refused, Tested, Tools, rank, register, run_test
from agents.llm import MissingFixture, Model, Usage
from agents.outputs import Ranking
from agents.single import Finding, case_tools
from contracts.case import Case, CaseStage, Checkpoint
from contracts.prediction import CrossExamination, Hypothesis
from contracts.taxonomy import AgentRole
from state.tools import Feed

AGENTS = (AgentRole.TACTICS, AgentRole.PHYSICAL, AgentRole.GAME_STATE)
PER_AGENT = 2  # hypotheses each domain agent may register
AGENT_TIMEOUT_S = 240


class AgentDown(RuntimeError):
    """An agent stopped mid-case (the recovery demo injects this)."""


@dataclass
class Run:
    """What every stage of one case shares."""

    model: Model
    case: Case
    feed: Feed
    tools: Tools
    evidence: dict
    stop: dict[AgentRole, int] = field(default_factory=dict)  # failures to inject, per agent
    score: dict[str, float] = field(default_factory=dict)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    retried: set[AgentRole] = field(default_factory=set)
    failed: set[AgentRole] = field(default_factory=set)
    usage: Usage = field(default_factory=Usage)
    tested: "TestedAll | None" = None
    exams: list[CrossExamination] = field(default_factory=list)
    unrun: list[str] = field(default_factory=list)

    def finding(self, ranking: Ranking) -> Finding:
        return Finding(
            case=self.case,
            agents=[a for a in AGENTS if a not in self.failed],
            hypotheses=self.tested.hypotheses,
            refused=self.tested.refused,
            tested=self.tested.tested,
            ranking=ranking,
            score=self.score,
            tools=self.tools,
            evidence=self.evidence,
            usage=self.usage,
            exams=self.exams,
            checkpoints=self.checkpoints,
            unrun=self.unrun,
            recovered=bool(self.retried),
        )

    def checkpoint(self, stage: CaseStage, note: str = "") -> None:
        self.checkpoints.append(
            Checkpoint(
                stage=stage,
                wall_clock_ms=int(time.time() * 1000),
                agents_completed=[a for a in AGENTS if a not in self.failed],
                agents_failed=sorted(self.failed),
                note=note,
            )
        )

    async def attempt(self, role: AgentRole, step: Callable[[], Awaitable[Any]]) -> Any | None:
        """Run an agent's step; retry it once from the stage's checkpoint if it fails."""
        for tries in range(2):
            try:
                if self.stop.get(role, 0) > 0:
                    self.stop[role] -= 1
                    raise AgentDown(f"{role} stopped")
                return await asyncio.wait_for(step(), AGENT_TIMEOUT_S)
            except MissingFixture:
                raise
            except Exception:  # any agent failure is what recovery is for
                self.retried.add(role)
                if tries == 1:
                    self.failed.add(role)
        return None


@dataclass
class Start:
    pass


@dataclass
class Opened:
    pass


@dataclass
class Registered:
    role: AgentRole
    hypotheses: list[Hypothesis]
    refused: list[Refused]


@dataclass
class TestedAll:
    hypotheses: list[Hypothesis]
    refused: list[Refused]
    tested: list[Tested]


@dataclass
class Challenged:
    role: AgentRole
    exams: list[CrossExamination]
    refusals: list[Refusal]


class Opener(Executor):
    def __init__(self, run: Run) -> None:
        super().__init__(id="open")
        self.run = run

    @handler
    async def open(self, _: Start, ctx: WorkflowContext[Opened]) -> None:
        self.run.score = (await self.run.tools.call("game_state")).values
        await ctx.send_message(Opened())


class Specialist(Executor):
    """A domain agent pre-registering its hypotheses."""

    def __init__(self, run: Run, role: AgentRole) -> None:
        super().__init__(id=f"register-{role.value}")
        self.run, self.role = run, role

    @handler
    async def register(self, _: Opened, ctx: WorkflowContext[Registered]) -> None:
        r = self.run

        async def step():
            return await register(r.model, self.role, r.case, r.feed.meta, r.score, PER_AGENT)

        done = await r.attempt(self.role, step)
        hypotheses, refused, usage = done if done else ([], [], Usage())
        r.usage = r.usage + usage
        await ctx.send_message(Registered(self.role, hypotheses, refused))


class Tester(Executor):
    """Code tests every registered hypothesis, once every agent has registered."""

    def __init__(self, run: Run) -> None:
        super().__init__(id="test")
        self.run = run

    @handler
    async def test(self, registered: list[Registered], ctx: WorkflowContext[TestedAll]) -> None:
        ordered = sorted(registered, key=lambda r: AGENTS.index(r.role))
        hypotheses = [h for r in ordered for h in r.hypotheses]
        self.run.checkpoint(CaseStage.PREREGISTERED, f"{len(hypotheses)} hypotheses")
        tested = [await run_test(self.run.tools, h) for h in hypotheses]
        self.run.checkpoint(CaseStage.TESTED, f"{sum(t.supported for t in tested)} supported")
        refused = [x for r in ordered for x in r.refused]
        self.run.tested = TestedAll(hypotheses, refused, tested)
        await ctx.send_message(self.run.tested)


class Challenger(Executor):
    """A domain agent proposing counter-tests to the other agents' survivors."""

    def __init__(self, run: Run, role: AgentRole) -> None:
        super().__init__(id=f"challenge-{role.value}")
        self.run, self.role = run, role

    @handler
    async def challenge(self, everything: TestedAll, ctx: WorkflowContext[Challenged]) -> None:
        r = self.run
        others = [t for t in everything.tested if t.supported and t.hypothesis.agent != self.role]
        if self.role in r.failed or not others:
            await ctx.send_message(Challenged(self.role, [], []))
            return

        async def step():
            return await challenge(r.model, self.role, r.case, r.feed.meta, r.score, others)

        done = await r.attempt(self.role, step)
        exams, refusals, usage = done if done else ([], [], Usage())
        r.usage = r.usage + usage
        await ctx.send_message(Challenged(self.role, exams, refusals))


class Synthesizer(Executor):
    """Code runs the counter-tests; the synthesis agent ranks what was not refuted."""

    def __init__(self, run: Run) -> None:
        super().__init__(id="synthesize")
        self.run = run

    @handler
    async def synthesize(
        self, challenges: list[Challenged], ctx: WorkflowContext[Never, Ranking]
    ) -> None:
        r = self.run
        proposed = [
            e for c in sorted(challenges, key=lambda c: AGENTS.index(c.role)) for e in c.exams
        ]
        scored = [(e, await run_counter(r.tools, e)) for e in proposed]
        exams = [x for _, x in scored if x is not None]
        r.exams = exams
        r.unrun += [
            f"{c.challenger} on {c.counter.hypothesis_id}: refused, {c.reason}"
            for ch in challenges
            for c in ch.refusals
        ]
        r.unrun += [
            f"{e.challenger} on {e.hypothesis_id}: not measurable" for e, x in scored if x is None
        ]
        refuted = {e.hypothesis_id for e in exams if e.result == "refuted"}
        r.checkpoint(
            CaseStage.CROSS_EXAMINED, f"{len(exams)} counter-tests, {len(refuted)} refuted"
        )
        everything = r.tested
        survivors = [
            t
            for t in everything.tested
            if t.supported and t.hypothesis.hypothesis_id not in refuted
        ]
        notes = {
            t.hypothesis.hypothesis_id: {
                "cross_examination": [
                    f"{e.challenger} ran a counter-test: {e.result} ({e.reason})"
                    for e in exams
                    if e.hypothesis_id == t.hypothesis.hypothesis_id
                ]
            }
            for t in survivors
        }
        ranking, usage = await rank(
            r.model, AgentRole.SYNTHESIS, r.case, r.feed.meta, r.score, survivors, r.tools, notes
        )
        r.usage = r.usage + usage
        r.checkpoint(CaseStage.SYNTHESIZED, ranking.outcome)
        await ctx.yield_output(ranking)


async def investigate(
    model: Model, case: Case, feed: Feed, stop: dict[AgentRole, int] | None = None
) -> Finding:
    """Run variant A on one case; `stop` makes agents fail, to exercise recovery."""
    tools, sink = case_tools(case, feed)
    run = Run(model, case, feed, tools, sink.evidence, dict(stop or {}))
    opener = Opener(run)
    specialists = [Specialist(run, a) for a in AGENTS]
    tester = Tester(run)
    challengers = [Challenger(run, a) for a in AGENTS]
    synthesizer = Synthesizer(run)
    workflow = (
        WorkflowBuilder(start_executor=opener, checkpoint_storage=InMemoryCheckpointStorage())
        .add_fan_out_edges(opener, specialists)
        .add_fan_in_edges(specialists, tester)
        .add_fan_out_edges(tester, challengers)
        .add_fan_in_edges(challengers, synthesizer)
        .build()
    )
    result = await workflow.run(Start())
    (ranking,) = result.get_outputs()
    return run.finding(ranking)
