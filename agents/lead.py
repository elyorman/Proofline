"""The Lead (spec §9.1): states what a viewer's question assumes, as one measurable change,
so code can test it before any specialist looks for a cause. In variant B the single agent
frames its own question. The Lead never measures and registers no cause.
"""

import json

from pydantic import ValidationError

from agents import prompts
from agents.llm import Model, Usage
from agents.outputs import Framing
from contracts.meta import MatchMeta
from contracts.question import Premise, Question
from contracts.taxonomy import AgentRole
from state.subjects import resolve
from state.tools import MEASURED

INSTRUCTIONS = f"""\
A viewer asks about a football match in progress; you work from its event data. You never \
compute or estimate a number and you do not explain causes: specialists do that once code \
has checked what the question assumes. Your one job is to state that assumption as one \
measurable change, so code can test it first:
- the metric, whose metric it is, and the way the question assumes it moved;
- since when: a second-half minute as mm:00, at least five minutes before the question. Take \
the minute the question names; if it names none, the stretch of play it describes.
A question that assumes a change ("why are they tiring?", "why so many long balls?") assumes \
that change, even when you doubt it: code will check. Choose whose metric shows it: a team, \
"Team.defence", "Team.midfield", "Team.attack" or a player id from the roster. A question \
these metrics cannot measure (who will win, who is better) is not answerable: say so.

Measurable metrics:
{prompts.METRIC_LIST}"""


async def frame(
    model: Model, role: AgentRole, question: Question, meta: MatchMeta
) -> tuple[Premise | None, str, Usage]:
    """(the question's premise, or None with why not; the model's usage)."""
    answer, usage = await model.ask(
        role.value,
        INSTRUCTIONS,
        "State what this question assumes.\n"
        + json.dumps(
            {
                "question": question.text,
                "asked_at": str(question.asked_at),
                "match": prompts.match(meta),
            },
            indent=1,
        ),
        Framing,
    )
    if not answer.answerable:
        return None, answer.why, usage
    try:
        if answer.metric not in MEASURED:
            raise ValueError(f"{answer.metric} is not measurable")
        resolve(meta, answer.subject)
        premise = Premise(
            metric=answer.metric,
            subject=answer.subject,
            direction=answer.direction,
            since=answer.since,
        )
        premise.window(question.asked_at)
    except (ValidationError, ValueError, TypeError) as exc:
        return None, f"the premise does not fit: {str(exc).splitlines()[0][:200]}", usage
    return premise, answer.why, usage
