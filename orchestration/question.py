"""A viewer's question end to end (spec §8.2 "Why?", §9.1): the Lead states what it assumes,
code tests that premise against normal variation, and only a premise that holds is
investigated, by the same agents, Verifier and card as a detected moment. Variant B's single
agent frames its own question; everything after the framing is shared.
"""

import asyncio
import json
from pathlib import Path

from agents import lead, narrator, single
from agents.confirm import PREMISE_SD, both_teams, explained, measure
from agents.investigation import Tools
from agents.llm import Model, Usage
from agents.plain import answer as plain_answer
from agents.propose import propose
from contracts.case import Case, TriggerMetric
from contracts.eval_run import Variant
from contracts.question import Answer, Question
from contracts.taxonomy import AgentRole, CardStatus, Metric, MomentType
from orchestration import progress, workflow
from orchestration.case import keep_watching
from state.tools import Feed
from tools_server.server import DirectorySource, FeedSource, MemorySink, build_server

BUDGET = 16  # the tool calls a question may spend, as a detected case may
PLAIN = "P"  # the plain tool-using agent the questions are also put to (agents/plain.py)
MOMENT = {  # which kind of moment a question about each metric is
    Metric.PRESSURE_RATE: MomentType.PRESSURE_SHIFT,
    Metric.LONG_BALL_SHARE: MomentType.PRESSURE_SHIFT,
    Metric.SPRINT_COUNT: MomentType.FATIGUE_SIGNAL,
    Metric.SPRINT_SPEED: MomentType.FATIGUE_SIGNAL,
    Metric.CHANNEL_SHARE_LEFT: MomentType.SHAPE_CHANGE,
    Metric.CHANNEL_SHARE_CENTRE: MomentType.SHAPE_CHANGE,
    Metric.CHANNEL_SHARE_RIGHT: MomentType.SHAPE_CHANGE,
}


async def run_question(
    variant: Variant, agents: Model, verifier: Model, question: Question, feed: Feed
) -> Answer:
    if variant not in (Variant.A_PROOFLINE, Variant.B_SINGLE_AGENT):
        raise NotImplementedError(f"variant {variant} is a stretch, not built")
    meta = feed.meta
    role = AgentRole.LEAD if variant == Variant.A_PROOFLINE else AgentRole.SINGLE
    premise, why, usage = await lead.frame(agents, role, question, meta)
    progress.report("framed", why)

    def answered(
        outcome: str, reason: str, test=None, card=None, spent: Usage = usage, final=None
    ) -> Answer:
        return Answer(
            question=question,
            variant=variant,
            premise=premise,
            premise_test=test,
            outcome=outcome,
            reason=reason,
            card=card,
            text=narrator.answer(outcome, premise, test, card, meta),
            final=final,
            input_tokens=spent.input_tokens,
            output_tokens=spent.output_tokens,
        )

    if premise is None:
        return answered("unanswerable", why)
    window = premise.window(question.asked_at)
    sink = MemorySink()
    server = build_server(FeedSource({meta.match_id: feed}), sink, {meta.match_id: window.end})
    tools = Tools(server, meta.match_id, BUDGET)
    test = await measure(
        tools, meta, premise.metric, premise.subject, premise.direction, window, PREMISE_SD
    )
    progress.report("premise", test.reason)
    if not test.holds:
        return answered("premise_false", test.reason, test)
    case = Case(
        case_id=f"case-{meta.match_id}-{question.question_id}",
        match_id=meta.match_id,
        moment_type=MOMENT[premise.metric],
        origin="question",
        window=window,
        triggers=[
            TriggerMetric(
                metric=premise.metric,
                subject=premise.subject,
                value=test.value,
                baseline_value=test.baseline,
                n_events=test.n_events,
            )
        ],
        tool_call_budget=BUDGET,
        both_teams=both_teams(feed, window),
    )
    if variant == Variant.A_PROOFLINE:
        finding = await workflow.investigate(agents, case, feed, opened=(tools, sink))
    else:
        finding = await single.investigate(agents, case, feed, opened=(tools, sink))
    # The premise is the change the answer explains; its calls are answered from the cache.
    finding.explained = await explained(
        tools, premise.metric, premise.subject, premise.direction, window
    )
    card = propose(finding, feed)
    if card is None:
        spent = usage + finding.usage
        return answered(finding.ranking.outcome, finding.ranking.why, test, spent=spent)
    # Keep watching: a rival that survived is settled on the minutes after the question.
    verdict, followed = await keep_watching(agents, verifier, finding, card, feed)
    progress.report("verified", verdict.card.verification.status)
    spent = usage + finding.usage + verdict.usage + (followed.usage if followed else Usage())
    shown = verdict.card if verdict.card.status == CardStatus.VERIFIED else None
    final = followed.card if followed and followed.card.status == CardStatus.REVISED else None
    reason = (
        finding.ranking.why if shown else f"rejected: {verdict.card.verification.rejection_reason}"
    )
    return answered("explained", reason, test, shown, spent, final if shown else None)


async def answer_all(
    data: Path,
    questions: Path,
    variant: Variant | str,
    out: Path,
    agents: Model,
    verifier: Model,
    concurrency: int = 2,
) -> Path:
    """Every question in a questions file, answered into <out>/<variant>/answers.jsonl; a
    question already answered there is not asked again. The file holds no answers: whoever
    wrote it keeps them."""
    source = DirectorySource(data)
    plain = variant == PLAIN
    target = Path(out) / str(getattr(variant, "value", variant)) / "answers.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    done = {
        json.loads(line)["question"]["question_id"]
        for line in (target.read_text().splitlines() if target.exists() else [])
    }
    asked = [
        Question.model_validate_json(line)
        for line in Path(questions).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    gate = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    async def one(q: Question) -> None:
        async with gate:
            try:
                feed = source.feed(q.match_id)
                answer = (
                    await plain_answer(agents, q, feed)
                    if plain
                    else await run_question(variant, agents, verifier, q, feed)
                )
                line = answer.model_dump_json()
            except Exception as exc:  # one failed question is recorded, not the end of the run
                line = json.dumps({"question": q.model_dump(mode="json"), "error": repr(exc)})
            async with lock:
                with target.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            got = json.loads(line)
            print(
                f"{q.question_id} {target.parent.name}: {got.get('outcome', got.get('happening'))}"
            )

    await asyncio.gather(*(one(q) for q in asked if q.question_id not in done))
    return target
