"""Cross-examination (spec §9.1 step 4): each domain agent may put one counter-test to each
other agent's surviving hypothesis. The contracts refuse any counter-test that could not
fairly contradict it (`check_counter_test`); code runs the rest and scores them.
"""

import json
from dataclasses import dataclass

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field, ValidationError

from agents import prompts
from agents.investigation import BudgetSpent, Tested, Tools, change_of
from agents.llm import Model, Usage
from contracts.case import Case
from contracts.meta import MatchMeta
from contracts.prediction import CrossExamination, Direction, Prediction, check_counter_test
from contracts.taxonomy import AgentRole
from contracts.tool_result import ToolResult
from state.subjects import resolve

RULES = """\
You cross-examine other specialists' hypotheses for one detected moment. For each one you \
doubt, you may put one test; code runs and scores it, and refuses an unfair one. A test is \
over the hypothesis's own window, and is one of:
- corollary: something else the hypothesis's cause would move if it were real, on another \
metric, against the first half: whose metric, which way, and the smallest move that would \
count. If it moved that way, the hypothesis holds; if it moved the other way by as much, it \
is refuted; anything in between weakens it. Ask for the sign the cause would leave and its \
rivals, your own domain's included, would not.
- control: the same claim on another subject (the other team, or another team's unit). If \
it moves as much, the change is shared and does not single out the hypothesis's subject. \
Same baseline and threshold as the claim.
- flat: the hypothesis's own subject compared with another baseline ('match_so_far'), \
predicting no change beyond a tolerance smaller than the claim.
- opposite: the hypothesis's own subject against another baseline, moving the other way by \
at least as much as the claim.
Challenge only what your own expertise gives you reason to doubt; leave the rest."""


class Counter(BaseModel):
    hypothesis_id: str
    kind: str = Field(description="'corollary', 'control', 'flat' or 'opposite'")
    metric: str | None = Field(description="a corollary's metric; null for the other kinds")
    direction: str | None = Field(description="a corollary's 'up' or 'down'; else null")
    subject: str = Field(
        description="whose metric a corollary is; for a control, the other subject; "
        "else the hypothesis's subject"
    )
    compare_to: str = Field(
        description="'first_half' for a corollary or a control; else 'match_so_far'"
    )
    min_change: float = Field(description="for flat, the tolerance; else the threshold")
    reason: str = Field(description="one short sentence")


class Counters(BaseModel):
    counters: list[Counter]


@dataclass
class Refusal:
    counter: Counter
    challenger: AgentRole
    reason: str


@dataclass
class Examined:
    """A counter-test as measured, with the tool results its score rests on."""

    exam: CrossExamination
    during: ToolResult
    before: ToolResult


def kind_of(e: CrossExamination) -> str:
    return (
        "corollary"
        if e.corollary
        else "control"
        if e.hypothesis_change is not None
        else "counter-test"
    )


def describe(e: CrossExamination) -> str:
    """The test, what code measured and the result, as a ranker or an analyst reads it."""
    p = e.counter_prediction
    return (
        f"{e.challenger} {kind_of(e)}: {p.metric} of {p.subject} {p.direction} by "
        f"{p.min_change:g}, measured {e.observed_change:+.3f}; result: {e.result} ({e.reason})"
    )


def _counter_prediction(t: Tested, c: Counter) -> Prediction:
    claim = t.hypothesis.prediction
    if c.kind == "corollary":
        return Prediction(
            metric=c.metric,
            subject=c.subject,
            window=claim.window,
            compare_to=claim.compare_to,
            direction=c.direction,
            min_change=c.min_change,
        )
    opposite = Direction.DOWN if claim.direction == Direction.UP else Direction.UP
    direction = {"control": claim.direction, "flat": Direction.FLAT, "opposite": opposite}[c.kind]
    return Prediction(
        metric=claim.metric,
        subject=c.subject,
        window=claim.window,
        compare_to=claim.compare_to if c.kind == "control" else c.compare_to,
        direction=direction,
        threshold_kind=claim.threshold_kind,
        min_change=claim.min_change if c.kind == "control" else c.min_change,
    )


def _claim(p: Prediction) -> str:
    return (
        f"{p.metric} of {p.subject} {p.direction} by at least {p.min_change:g} in {p.window} "
        "against the first half"
    )


async def challenge(
    model: Model,
    role: AgentRole,
    case: Case,
    meta: MatchMeta,
    score: dict[str, float],
    others: list[Tested],
) -> tuple[list[CrossExamination], list[Refusal], Usage]:
    """Ask `role` for counter-tests against other agents' survivors; keep the fair ones."""
    if not others:
        return [], [], Usage()
    listed = [
        {
            "hypothesis_id": t.hypothesis.hypothesis_id,
            "by": t.hypothesis.agent.value,
            "cause": t.hypothesis.taxonomy.value,
            "claim": _claim(t.hypothesis.prediction),
            "result": t.test.reason,
        }
        for t in others
    ]
    answer, usage = await model.ask(
        role.value,
        f"{prompts.instructions(role, 2)}\n\n{RULES}",
        "Cross-examine these hypotheses.\n"
        + json.dumps(
            {
                "moment": str(case.window),
                "score_at_detection": prompts.scoreline(meta, score),
                "hypotheses": listed,
                "match": prompts.match(meta),
            },
            indent=1,
        ),
        Counters,
    )
    by_id = {t.hypothesis.hypothesis_id: t for t in others}
    kept: list[CrossExamination] = []
    refused: list[Refusal] = []
    for c in answer.counters:
        t = by_id.get(c.hypothesis_id)
        try:
            if t is None:
                raise ValueError(f"{c.hypothesis_id} is not a hypothesis under examination")
            if any(e.hypothesis_id == c.hypothesis_id for e in kept):
                raise ValueError("one counter-test per challenger per hypothesis")
            resolve(meta, c.subject)
            exam = CrossExamination(
                hypothesis_id=c.hypothesis_id,
                challenger=role,
                counter_prediction=_counter_prediction(t, c),
                tool_call_id="pending",
                observed_change=0.0,
                hypothesis_change=t.test.observed_change if c.kind == "control" else None,
                corollary=c.kind == "corollary",
                reason=c.reason,
            )
            check_counter_test(t.hypothesis, exam)
        except (ValidationError, ValueError, KeyError) as exc:
            refused.append(Refusal(c, role, str(exc).splitlines()[0][:200]))
            continue
        kept.append(exam)
    return kept, refused, usage


async def run_counter(tools: Tools, exam: CrossExamination) -> Examined | None:
    """Measure a counter-test and score it; None if it could not be measured."""
    p = exam.counter_prediction
    try:
        during = await tools.call("metric", name=p.metric, subject=p.subject, window=str(p.window))
        before = await tools.call("baseline", name=p.metric, subject=p.subject, scope=p.compare_to)
    except (ToolError, BudgetSpent):  # an unmeasurable counter-test leaves the hypothesis standing
        return None
    if during.value is None or before.baseline is None:
        return None
    change = change_of(p, during.value, before.baseline.value)
    if change is None:
        return None
    data = exam.model_dump(mode="json", exclude={"result"})
    scored = CrossExamination.model_validate(
        data | {"observed_change": change, "tool_call_id": during.tool_call_id}
    )
    return Examined(scored, during, before)
