"""Cross-examination (spec §9.1 step 4): each domain agent may put one counter-test to each
other agent's surviving hypothesis. The contracts refuse any counter-test that could not
fairly contradict it (`check_counter_test`); code runs the rest and scores them.
"""

import json
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field, ValidationError

from agents import prompts
from agents.investigation import (
    BudgetSpent,
    Tested,
    Tools,
    change_of,
    predicts_the_detected_change,
    too_few,
)
from agents.llm import Model, Usage
from contracts.case import Case
from contracts.meta import MatchMeta
from contracts.prediction import CrossExamination, Prediction, check_counter_test
from contracts.taxonomy import AgentRole
from contracts.tool_result import ToolResult
from state.subjects import resolve

OPENING = {
    "others": "You cross-examine other specialists' hypotheses for one detected moment.",
    "own": "Before ranking, you cross-examine your own hypotheses for one detected moment, as "
    "a rival specialist would: look for the test that would expose each one if it were wrong.",
}

RULES = """\
For each hypothesis you doubt, you may put one test; code runs and scores it, and refuses an \
unfair one. A test is \
over the hypothesis's own window, against the first half, in standard deviations of normal \
variation, and is one of:
- corollary: something else the hypothesis's cause would move if it were real, on another \
metric: whose metric, which way, and the smallest move in sd that would count. If it moved \
that way, the hypothesis holds; if it moved the other way by as much, it is refuted; anything \
in between weakens it. It must follow from the hypothesis's own cause, not from a rival: to \
show your own cause fits better, ask the hypothesis for a sign its cause needs and yours does \
not, and if that sign is missing it weakens.
- control: the same claim on another subject (the other team, or another team's unit). If \
it moves as much, the change is shared and does not single out the hypothesis's subject. \
Same threshold as the claim.
A hypothesis whose prediction is the detected change has only shown that the change \
happened, not which cause made it: if you doubt it, ask it for a corollary.
Challenge only what your own expertise gives you reason to doubt; leave the rest."""

KINDS = ("corollary", "control")


class Counter(BaseModel):
    hypothesis_id: str
    kind: str = Field(description="'corollary' or 'control'")
    metric: str | None = Field(description="a corollary's metric; null for a control")
    direction: str | None = Field(description="a corollary's 'up' or 'down'; null for a control")
    subject: str = Field(
        description="whose metric a corollary is; for a control, the other subject"
    )
    min_change: float = Field(
        description="a corollary's threshold in sd; a control uses the claim's"
    )
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
    unit = " sd" if p.threshold_kind == "sigma" else ""
    return (
        f"{e.challenger} {kind_of(e)}: {p.metric} of {p.subject} {p.direction} by "
        f"{p.min_change:g}{unit}, measured {e.observed_change:+.2f}{unit}; result: {e.result} "
        f"({e.reason})"
    )


def _counter_prediction(t: Tested, c: Counter) -> Prediction:
    claim = t.hypothesis.prediction
    if c.kind not in KINDS:
        raise ValueError(f"a counter-test is a corollary or a control, not {c.kind!r}")
    if c.kind == "corollary":
        return Prediction(
            metric=c.metric,
            subject=c.subject,
            window=claim.window,
            compare_to=claim.compare_to,
            direction=c.direction,
            threshold_kind=claim.threshold_kind,
            min_change=c.min_change,
        )
    return Prediction(
        metric=claim.metric,
        subject=c.subject,
        window=claim.window,
        compare_to=claim.compare_to,
        direction=claim.direction,
        threshold_kind=claim.threshold_kind,
        min_change=claim.min_change,
    )


def _claim(p: Prediction) -> str:
    return (
        f"{p.metric} of {p.subject} {p.direction} by at least {p.min_change:g} sd in "
        f"{p.window} against the first half"
    )


async def challenge(
    model: Model,
    role: AgentRole,
    case: Case,
    meta: MatchMeta,
    score: dict[str, float],
    others: list[Tested],
) -> tuple[list[CrossExamination], list[Refusal], Usage]:
    """Ask `role` for counter-tests against other agents' survivors, or the single agent
    against its own; keep the fair ones."""
    if not others:
        return [], [], Usage()
    opening = OPENING["own" if role == AgentRole.SINGLE else "others"]
    listed = [
        {
            "hypothesis_id": t.hypothesis.hypothesis_id,
            "by": t.hypothesis.agent.value,
            "cause": t.hypothesis.taxonomy.value,
            "claim": _claim(t.hypothesis.prediction),
            "predicts_the_detected_change": predicts_the_detected_change(
                case, t.hypothesis.prediction
            ),
            "result": t.test.reason,
        }
        for t in others
    ]
    answer, usage = await model.ask(
        role.value,
        f"{prompts.instructions(role, 2)}\n\n{opening}\n{RULES}",
        "Cross-examine these hypotheses.\n"
        + json.dumps(
            {
                "moment": str(case.window),
                "state_at_detection": prompts.state_at(meta, score),
                "both_teams": prompts.both_teams(case),
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


async def run_counter(tools: Tools, exam: CrossExamination, meta: MatchMeta) -> Examined | None:
    """Measure a counter-test and score it; None if it could not be measured."""
    p = exam.counter_prediction
    try:
        during = await tools.call("metric", name=p.metric, subject=p.subject, window=str(p.window))
        before = await tools.call("baseline", name=p.metric, subject=p.subject, scope=p.compare_to)
    except (ToolError, BudgetSpent):  # an unmeasurable counter-test leaves the hypothesis standing
        return None
    if during.value is None or before.baseline is None or too_few(p.metric, during, before):
        return None
    change = change_of(p, during.value, before.baseline.value, meta)
    if change is None:
        return None
    data = exam.model_dump(mode="json", exclude={"result"})
    scored = CrossExamination.model_validate(
        data | {"observed_change": change, "tool_call_id": during.tool_call_id}
    )
    return Examined(scored, during, before)


@dataclass
class Settled:
    """Cross-examination once code has scored it: what still stands, and why."""

    exams: list[CrossExamination]
    corroborations: list[Examined]  # corollaries that held
    unrun: list[str]  # counter-tests refused or not measurable
    survivors: list[Tested]  # supported and not refuted
    notes: dict[str, dict[str, Any]]  # each survivor's counter-tests, for the ranker


async def settle(
    tools: Tools,
    meta: MatchMeta,
    tested: list[Tested],
    proposed: list[CrossExamination],
    refusals: list[Refusal],
) -> Settled:
    """Run every fair counter-test and keep the hypotheses none refuted. Both variants settle
    their cross-examination here, so the single agent's self-check is scored as the three
    agents' is."""
    scored = [(e, await run_counter(tools, e, meta)) for e in proposed]
    exams = [x.exam for _, x in scored if x is not None]
    unrun = [f"{c.challenger} on {c.counter.hypothesis_id}: refused, {c.reason}" for c in refusals]
    unrun += [
        f"{e.challenger} on {e.hypothesis_id}: not measurable" for e, x in scored if x is None
    ]
    refuted = {e.hypothesis_id for e in exams if e.result == "refuted"}
    survivors = [t for t in tested if t.supported and t.hypothesis.hypothesis_id not in refuted]
    return Settled(
        exams=exams,
        corroborations=[
            x for _, x in scored if x is not None and x.exam.corollary and x.exam.result == "holds"
        ],
        unrun=unrun,
        survivors=survivors,
        notes={
            t.hypothesis.hypothesis_id: {
                "cross_examination": [
                    describe(e) for e in exams if e.hypothesis_id == t.hypothesis.hypothesis_id
                ]
            }
            for t in survivors
        },
    )
