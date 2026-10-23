"""The steps of one case's investigation (spec §9.1): pre-register, test, rank.

Every tool call goes through the MCP server fixed at the case's cutoff, so each one is
logged and counted against the case's budget. A prediction is judged by code on the tool
results, never by the agent that made it.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from agents import prompts
from agents.llm import Model, Usage
from agents.outputs import Proposal, Ranking, Registration
from agents.verifier.rules import MIN_SAMPLE
from contracts.case import Case
from contracts.meta import MatchMeta
from contracts.planted import CAUSE_OBSERVABLES
from contracts.prediction import Direction, Hypothesis, HypothesisTest, Prediction, TestOutcome
from contracts.taxonomy import AgentRole, BaselineScope, CaseOutcome, Cause, Metric, ThresholdKind
from contracts.tool_result import ToolResult
from state.subjects import opponent, resolve
from state.tools import MEASURED

# A game-state cause needs the score to give its team the reason.
SCORE_NEEDED = {Cause.CHASING_RESULT: "behind", Cause.PROTECTING_LEAD: "ahead"}


class BudgetSpent(RuntimeError):
    pass


@dataclass
class Tools:
    """The State Builder's tools for one case, through MCP, within the case's budget. A call
    identical to an earlier one is answered from it and not charged again."""

    server: MCPServer
    match_id: str
    budget: int
    log: list[dict[str, Any]] = field(default_factory=list)
    _answers: dict[str, ToolResult] = field(default_factory=dict)

    @property
    def used(self) -> int:
        return len(self.log)

    async def call(self, tool: str, **arguments: Any) -> ToolResult:
        request = {"match_id": self.match_id, **arguments}
        key = json.dumps([tool, request], sort_keys=True, default=str)
        if key in self._answers:
            return self._answers[key]
        if self.used >= self.budget:
            raise BudgetSpent(f"the case's {self.budget} tool calls are spent")
        entry: dict[str, Any] = {"tool": tool, "arguments": request}
        self.log.append(entry)
        try:
            response = await self.server.call_tool(tool, request)
        except ToolError as exc:
            entry["error"] = str(exc)
            raise
        result = ToolResult.model_validate(response.structured_content)
        entry["result"] = result.model_dump(mode="json", exclude_none=True)
        self._answers[key] = result
        return result


@dataclass
class Refused:
    proposal: Proposal
    agent: AgentRole
    reason: str


@dataclass
class Tested:
    hypothesis: Hypothesis
    test: HypothesisTest
    during: ToolResult | None = None
    before: ToolResult | None = None

    @property
    def supported(self) -> bool:
        return self.test.outcome == TestOutcome.SUPPORTED


def cause_team(meta: MatchMeta, hypothesis: Hypothesis) -> str:
    """The team a cause is about. A class's signature says whose metric each observable is:
    a press shows in the pressing team's pressure rate and in its opponent's long balls."""
    p = hypothesis.prediction
    team = resolve(meta, p.subject).team
    roles = {o.metric: o.subject for o in CAUSE_OBSERVABLES.get(hypothesis.taxonomy, ())}
    return opponent(meta, team) if roles.get(p.metric) == "opponent" else team


def _goal_difference(meta: MatchMeta, team: str, score: dict[str, float]) -> float:
    side = next(s for s, t in meta.teams.items() if t.name == team)
    other = "away" if side == "home" else "home"
    return score[f"{side}_goals"] - score[f"{other}_goals"]


def _facts_allow(meta: MatchMeta, hypothesis: Hypothesis, state: dict[str, float]) -> None:
    """Refuse a cause the match's facts rule out (`state` is game_state's values): chasing
    needs the team behind and protecting a lead needs it ahead; a change in numbers needs a
    sending-off, and fresh legs need a substitution by the team."""
    cause, team = hypothesis.taxonomy, cause_team(meta, hypothesis)
    side = next(s for s, t in meta.teams.items() if t.name == team)
    if needed := SCORE_NEEDED.get(cause):
        lead = _goal_difference(meta, team, state)
        if (lead >= 0) if needed == "behind" else (lead <= 0):
            raise ValueError(f"{team} is not {needed}, so the score gives no reason for this cause")
    if cause == Cause.NUMERICAL_CHANGE and not any(
        state.get(f"{s}_sent_off", 0) for s in meta.teams
    ):
        raise ValueError("no one has been sent off, so the numbers on the pitch have not changed")
    if cause == Cause.FRESH_LEGS_SUBSTITUTION and not state.get(f"{side}_substitutions", 0):
        raise ValueError(f"{team} have made no substitution, so no fresh legs came on")


def predicts_the_detected_change(case: Case, p: Prediction) -> bool:
    """Whether a prediction is the change the detector saw: it shows the change happened, not
    which cause made it."""
    return any(
        t.metric == p.metric
        and t.subject == p.subject
        and (t.value > t.baseline_value) == (p.direction == Direction.UP)
        for t in case.triggers
    )


async def register(
    model: Model,
    role: AgentRole,
    case: Case,
    meta: MatchMeta,
    score: dict[str, float],
    max_hypotheses: int,
) -> tuple[list[Hypothesis], list[Refused], Usage]:
    """Ask `role` for its hypotheses and keep those the contracts accept."""
    answer, usage = await model.ask(
        role.value,
        prompts.instructions(role, max_hypotheses),
        prompts.case_prompt(case, meta, score),
        Registration,
    )
    accepted: list[Hypothesis] = []
    refused: list[Refused] = []
    for proposal in answer.hypotheses[:max_hypotheses]:
        try:
            if proposal.metric not in MEASURED:
                raise ValueError(f"{proposal.metric} is not measurable yet")
            resolve(meta, proposal.subject)
            hypothesis = Hypothesis(
                hypothesis_id=f"hyp-{role.value}-{len(accepted) + 1:02d}",
                case_id=case.case_id,
                agent=role,
                taxonomy=proposal.cause,
                prediction=Prediction(
                    metric=proposal.metric,
                    subject=proposal.subject,
                    window=case.window,
                    compare_to=BaselineScope.FIRST_HALF,
                    direction=proposal.direction,
                    min_change=proposal.min_change,
                ),
            )
            _facts_allow(meta, hypothesis, score)
        except (ValidationError, ValueError) as exc:
            refused.append(Refused(proposal, role, str(exc).splitlines()[0][:200]))
            continue
        accepted.append(hypothesis)
    return accepted, refused, usage


def change_of(prediction: Prediction, during: float, before: float) -> float | None:
    """The signed change in the prediction's threshold units, or None if undefined."""
    if prediction.threshold_kind == ThresholdKind.ABSOLUTE:
        return during - before
    if prediction.threshold_kind == ThresholdKind.RELATIVE and before > 0:
        return (during - before) / before
    return None  # sigma needs the distribution tool, which is not built yet


def too_few(metric: Metric, during: ToolResult, before: ToolResult) -> str | None:
    """Why a measurement rests on fewer events than a card may (the Verifier's minimum
    samples), or None. Code judges nothing on data a card could not be published on."""
    n = before.baseline.n_events if metric == Metric.SPRINT_COUNT else during.n_events
    minimum = MIN_SAMPLE.get(metric, 0)
    return f"{n} events, fewer than the {minimum} a claim needs" if n < minimum else None


async def run_test(tools: Tools, hypothesis: Hypothesis) -> Tested:
    """Measure the prediction's metric over its window and its baseline, and judge it."""
    p = hypothesis.prediction

    def failed(reason: str, **results: ToolResult) -> Tested:
        call_id = results["during"].tool_call_id if "during" in results else "none"
        record = HypothesisTest(
            hypothesis_id=hypothesis.hypothesis_id,
            tool_call_id=call_id,
            observed_change=0.0,
            outcome=TestOutcome.FAILED,
            reason=reason,
        )
        return Tested(hypothesis, record, **results)

    try:
        during = await tools.call("metric", name=p.metric, subject=p.subject, window=str(p.window))
        before = await tools.call("baseline", name=p.metric, subject=p.subject, scope=p.compare_to)
    except (ToolError, BudgetSpent) as exc:
        return failed(str(exc))
    if during.value is None or before.baseline is None:
        why = during.insufficient_data or before.insufficient_data
        return failed(f"insufficient data: {why}", during=during, before=before)
    if thin := too_few(p.metric, during, before):
        return failed(f"too little data: {thin}", during=during, before=before)
    change = change_of(p, during.value, before.baseline.value)
    if change is None:
        return failed("no change defined from a zero baseline", during=during, before=before)
    held = p.supported_by(change)
    claim = f"{p.direction} by {p.min_change:g}"
    record = HypothesisTest(
        hypothesis_id=hypothesis.hypothesis_id,
        tool_call_id=during.tool_call_id,
        observed_change=change,
        outcome=TestOutcome.SUPPORTED if held else TestOutcome.FAILED,
        reason=f"{p.metric} of {p.subject}: {before.baseline.value:.3f} in the first half, "
        f"{during.value:.3f} in {p.window}, a change of {change:+.3f} against a claim of "
        f"{claim}",
    )
    return Tested(hypothesis, record, during, before)


def _summary(t: Tested, case: Case) -> dict[str, Any]:
    p = t.hypothesis.prediction
    return {
        "hypothesis_id": t.hypothesis.hypothesis_id,
        "cause": t.hypothesis.taxonomy.value,
        "agent": t.hypothesis.agent.value,
        "prediction": f"{p.metric} of {p.subject} {p.direction} by at least {p.min_change:g}",
        "predicts_the_detected_change": predicts_the_detected_change(case, p),
        "result": t.test.reason,
    }


async def rank(
    model: Model,
    role: AgentRole,
    case: Case,
    meta: MatchMeta,
    score: dict[str, float],
    survivors: list[Tested],
    extra: dict[str, dict[str, Any]] | None = None,
) -> tuple[Ranking, Usage]:
    """Order the survivors; with none, the outcome is `none` and no model is asked."""
    if not survivors:
        return Ranking(outcome="none", primary=None, secondary=[], why="nothing survived"), Usage()
    listed = [
        _summary(t, case) | (extra or {}).get(t.hypothesis.hypothesis_id, {}) for t in survivors
    ]
    try:
        answer, usage = await model.ask(
            role.value, prompts.RANKING, prompts.ranking_prompt(case, listed, score, meta), Ranking
        )
    except ValueError as exc:  # no answer, or none in time: ranked like an answer that fits none
        answer, usage = Ranking(outcome="", primary=None, secondary=[], why=str(exc)), Usage()
    ids = [t.hypothesis.hypothesis_id for t in survivors]
    valid = (
        answer.outcome in {o.value for o in CaseOutcome}
        and (answer.outcome != "explained" or answer.primary in ids)
        and all(s in ids and s != answer.primary for s in answer.secondary)
    )
    if not valid:  # an answer that names nothing real falls back to the strongest margin
        best = max(
            survivors,
            key=lambda t: abs(t.test.observed_change) / t.hypothesis.prediction.min_change,
        )
        answer = Ranking(
            outcome="explained",
            primary=best.hypothesis.hypothesis_id,
            secondary=[],
            why=f"ranking answer did not fit the survivors; strongest margin chosen ({answer.why})",
        )
    if answer.outcome != "explained":
        answer = Ranking(outcome=answer.outcome, primary=None, secondary=[], why=answer.why)
    return answer, usage
