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
from state.subjects import resolve

RULES = """\
You cross-examine other specialists' hypotheses for one detected moment. For each one you \
doubt, you may put one counter-test that would contradict it if it held; code runs and \
scores it, and refuses an unfair one. A counter-test is on the hypothesis's own metric and \
window, and is one of:
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
    kind: str = Field(description="'control', 'flat' or 'opposite'")
    subject: str = Field(description="for a control, the other subject; else the same subject")
    compare_to: str = Field(description="'first_half' for a control; else 'match_so_far'")
    min_change: float = Field(description="for flat, the tolerance; else the threshold")
    reason: str = Field(description="one short sentence")


class Counters(BaseModel):
    counters: list[Counter]


@dataclass
class Refusal:
    counter: Counter
    challenger: AgentRole
    reason: str


def _counter_prediction(t: Tested, c: Counter) -> Prediction:
    claim = t.hypothesis.prediction
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
            {"moment": str(case.window), "hypotheses": listed, "match": prompts.match(meta)},
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
                reason=c.reason,
            )
            check_counter_test(t.hypothesis, exam)
        except (ValidationError, ValueError, KeyError) as exc:
            refused.append(Refusal(c, role, str(exc).splitlines()[0][:200]))
            continue
        kept.append(exam)
    return kept, refused, usage


async def run_counter(tools: Tools, exam: CrossExamination) -> CrossExamination | None:
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
    return CrossExamination.model_validate(
        data | {"observed_change": change, "tool_call_id": during.tool_call_id}
    )
