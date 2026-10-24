"""The plain baseline (spec §11.2): what a viewer's question gets from one tool-using agent
without Proofline's design. The same model, the State Builder's tools over MCP, the case
budget and the same lists of metrics and causes, but no premise check, no normal variation,
no pre-registration, no cross-examination and no Verifier: it calls the tools it likes and
answers. It is measured beside variants A and B, never shown to a viewer.
"""

import json
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field, ValidationError

from agents import prompts
from agents.investigation import BudgetSpent, Tools
from agents.llm import ToolModel
from contracts.question import PlainAnswer, Question
from contracts.taxonomy import Cause
from state.tools import Feed
from tools_server.server import FeedSource, MemorySink, build_server

BUDGET = 16  # the tool calls a case or a question may spend in variants A and B
CAUSES = "\n".join(f"- {c.value}" for c in Cause if c.domain != "fallback")

INSTRUCTIONS = f"""\
You answer a football fan's question about a match in progress, from its event data. Use the \
tools to look before you answer: metric(name, subject, window) measures a metric over a \
window of the second half such as "60:00-70:00"; baseline(name, subject, scope) measures it \
over "first_half" or "match_so_far"; game_state() gives each team's goals, players sent off \
and substitutions. You may make at most {BUDGET} tool calls.

Metrics (subjects are a team, "Team.defence", "Team.midfield", "Team.attack" or a player id):
{prompts.METRIC_LIST}

Then say whether what the question assumes is happening. If it is, name the one cause below \
that explains it and whose cause it is (the team), or no cause if none fits:
{CAUSES}
Answer the fan in one or two sentences, in the language of the question."""


class Reply(BaseModel):
    happening: bool = Field(description="whether what the question assumes is happening")
    cause: str | None = Field(description="one cause from the list, or null")
    team: str | None = Field(description="whose cause it is, or null")
    answer: str = Field(description="one or two sentences for the fan")


def _tools(tools: Tools) -> list:
    async def call(tool: str, **arguments: Any) -> str:
        try:
            result = await tools.call(tool, **arguments)
        except (ToolError, BudgetSpent, ValidationError) as exc:
            return f"error: {str(exc).splitlines()[0][:200]}"
        return result.model_dump_json(
            include={"value", "baseline", "values", "n_events", "insufficient_data"},
            exclude_none=True,
        )

    async def metric(name: str, subject: str, window: str) -> str:
        """One metric for a team, unit or player over a finished window, e.g. '60:00-70:00'."""
        return await call("metric", name=name, subject=subject, window=window)

    async def baseline(name: str, subject: str, scope: str) -> str:
        """One metric over 'first_half' or 'match_so_far'."""
        return await call("baseline", name=name, subject=subject, scope=scope)

    async def game_state() -> str:
        """Each team's goals, players sent off and substitutions so far."""
        return await call("game_state")

    return [metric, baseline, game_state]


async def answer(model: ToolModel, question: Question, feed: Feed) -> PlainAnswer:
    """The plain agent's answer, with the tool calls it spent."""
    meta = feed.meta
    server = build_server(
        FeedSource({meta.match_id: feed}), MemorySink(), {meta.match_id: question.asked_at}
    )
    tools = Tools(server, meta.match_id, BUDGET)
    prompt = "Answer this question.\n" + json.dumps(
        {
            "question": question.text,
            "asked_at": str(question.asked_at),
            "match": prompts.roster(meta),
        },
        indent=1,
    )
    reply, usage = await model.ask_with_tools("plain", INSTRUCTIONS, prompt, Reply, _tools(tools))
    try:
        cause = Cause(reply.cause) if reply.cause else None
    except ValueError:  # a cause outside the list names nothing the suite can score
        cause = None
    return PlainAnswer(
        question=question,
        happening=reply.happening,
        cause=cause,
        team=reply.team,
        text=reply.answer,
        tool_calls=tools.used,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
