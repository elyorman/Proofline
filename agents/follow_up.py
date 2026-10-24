"""Keep watching (spec §9.1): when a rival cause survives beside the primary, the case stays
open. The data over the card's window could not tell the two apart, so each side
pre-registers a decisive test for the minutes after the card, which nobody has seen; once
they are played, code measures both, and the card is confirmed, overturned or left open in a
new revision the Verifier checks like any other.

A prediction about minutes not yet played is blind by construction, which a prediction about
the window an agent was shown cannot be.
"""

from dataclasses import dataclass

from mcp.server.mcpserver.exceptions import ToolError

from agents import narrator, prompts
from agents.investigation import BudgetSpent, Tested, Tools, cause_team, too_few
from agents.llm import Model, Usage
from agents.outputs import Decisive
from agents.single import Finding
from contracts.card import (
    MOVE_SD,
    STILL_SD,
    AttributionProposition,
    Baseline,
    DecisiveTest,
    DependsOn,
    Evidence,
    FollowUp,
    InsightCard,
    RejectedAlternative,
    Revision,
    Subject,
)
from contracts.clock import MatchClock, Window
from contracts.prediction import Direction
from contracts.taxonomy import BaselineScope, CardStatus
from contracts.tool_result import ToolResult
from state import natural
from state.subjects import resolve
from state.tools import MEASURED, Feed
from tools_server.server import FeedSource, MemorySink, build_server

MINUTES = 15  # how far ahead each side predicts
LEAST = 10  # with fewer minutes left in the match, nothing can be settled
BUDGET = 4  # two tests, each a metric and its baseline


def survivors(finding: Finding) -> list[Tested]:
    """The hypotheses that passed their test and that no counter-test refuted."""
    refuted = {e.hypothesis_id for e in finding.exams if e.result == "refuted"}
    return [t for t in finding.tested if t.supported and t.hypothesis.hypothesis_id not in refuted]


def rival(finding: Finding, feed: Feed) -> Tested | None:
    """The strongest survivor naming another cause, or another team, than the primary."""
    primary = finding.tested_by_id(finding.ranking.primary)
    meta = feed.meta
    named = (primary.hypothesis.taxonomy, cause_team(meta, primary.hypothesis))
    others = [
        t
        for t in survivors(finding)
        if (t.hypothesis.taxonomy, cause_team(meta, t.hypothesis)) != named
    ]
    return max(
        others,
        key=lambda t: abs(t.test.observed_change) / t.hypothesis.prediction.min_change,
        default=None,
    )


def minutes_after(at: MatchClock) -> Window | None:
    """The minutes a follow-up predicts: from when the card is ready, up to full time."""
    end = min(at.minute + MINUTES, 90)
    if at.period != 2 or end - at.minute < LEAST:
        return None
    return Window(start=at, end=MatchClock(period=2, minute=end, second=0))


def _side(t: Tested, feed: Feed) -> dict:
    p = t.hypothesis.prediction
    return {
        "hypothesis_id": t.hypothesis.hypothesis_id,
        "cause": t.hypothesis.taxonomy.value,
        "team": cause_team(feed.meta, t.hypothesis),
        "its_test": f"{p.metric} of {p.subject} {p.direction} by at least {p.min_change:g} sd",
        "result": t.test.reason,
    }


def _test(
    answer: Decisive, side: str, own: Tested, against: Tested, taken: list[DecisiveTest], feed: Feed
) -> DecisiveTest:
    """The side's test, if it can decide: not the other side's own claim, which the other
    cause predicts too, and not the prediction the other side already made."""
    if answer.metric not in MEASURED:
        raise ValueError(f"{answer.metric} is not measurable")
    resolve(feed.meta, answer.subject)
    said = (answer.metric, answer.subject, answer.direction)
    p = against.hypothesis.prediction
    if said == (p.metric, p.subject, p.direction):
        raise ValueError("that is the rival's own claim, so the rival's cause predicts it too")
    if any(said == (t.metric, t.subject, t.direction) for t in taken):
        raise ValueError("the other side predicts the same, so it cannot tell the causes apart")
    return DecisiveTest(
        side=side,
        hypothesis_id=own.hypothesis.hypothesis_id,
        cause=own.hypothesis.taxonomy,
        agent=own.hypothesis.agent,
        metric=answer.metric,
        subject=answer.subject,
        direction=answer.direction,
        reason=answer.why,
    )


@dataclass
class Opened:
    follow_up: FollowUp | None
    usage: Usage
    refused: list[str]  # proposals code could not take, with why


async def open_follow_up(model: Model, finding: Finding, card: InsightCard, feed: Feed) -> Opened:
    """The decisive tests both sides pre-register, or None when no rival survived or too
    little of the match is left. Each side is asked by its own agent; in variant B the one
    agent answers for both."""
    window = minutes_after(card.timing.verified_at or card.timing.detected_at)
    other = rival(finding, feed) if finding.ranking.primary else None
    if window is None or other is None:
        return Opened(None, Usage(), [])
    primary = finding.tested_by_id(finding.ranking.primary)
    tests, usage, refused = [], Usage(), []
    for side, own, against in (("primary", primary, other), ("rival", other, primary)):
        prompt = prompts.follow_up_prompt(
            finding.case,
            feed.meta,
            finding.score,
            _side(own, feed),
            _side(against, feed),
            str(window),
        )
        for _ in range(2):  # a test code refuses is put back once, with why
            try:
                answer, used = await model.ask(
                    own.hypothesis.agent.value, prompts.FOLLOW_UP, prompt, Decisive
                )
            except ValueError as exc:  # no answer in time: this side has no test
                refused.append(f"{side}: {str(exc).splitlines()[0][:200]}")
                break
            usage = usage + used
            try:
                tests.append(_test(answer, side, own, against, tests, feed))
                break
            except ValueError as exc:
                why = str(exc).splitlines()[0][:200]
                refused.append(f"{side}: {why}")
                prompt += f"\nYour test was refused: {why}. Pre-register another."
    if not tests:
        return Opened(None, usage, refused)
    follow_up = FollowUp(
        window=window,
        rival_hypothesis_id=other.hypothesis.hypothesis_id,
        rival_cause=other.hypothesis.taxonomy,
        rival_agent=other.hypothesis.agent,
        rival_team=cause_team(feed.meta, other.hypothesis),
        tests=tests,
    )
    return Opened(follow_up, usage, refused)


@dataclass
class Settled:
    follow_up: FollowUp
    tools: Tools
    sink: MemorySink
    readings: list[tuple[DecisiveTest, ToolResult, ToolResult]]  # what was measured


def _holds(direction: Direction, z: float) -> bool:
    way = {Direction.UP: 1, Direction.DOWN: -1}.get(direction)
    return abs(z) < STILL_SD if way is None else way * z >= MOVE_SD


async def settle(follow_up: FollowUp, feed: Feed) -> Settled:
    """Measure each decisive test over its minutes, with the tools fixed at their end."""
    match_id, window = feed.meta.match_id, follow_up.window
    sink = MemorySink()
    server = build_server(FeedSource({match_id: feed}), sink, {match_id: window.end})
    tools = Tools(server, match_id, BUDGET)
    judged, readings = [], []
    for t in follow_up.tests:
        try:
            during = await tools.call(
                "metric", name=t.metric, subject=t.subject, window=str(window)
            )
            before = await tools.call(
                "baseline", name=t.metric, subject=t.subject, scope=BaselineScope.FIRST_HALF
            )
        except (ToolError, BudgetSpent) as exc:
            judged.append(t.model_copy(update={"holds": False, "measured": str(exc)[:200]}))
            continue
        if during.value is None or before.baseline is None:
            why = during.insufficient_data or before.insufficient_data
            judged.append(t.model_copy(update={"holds": False, "measured": f"no reading: {why}"}))
            continue
        if thin := too_few(t.metric, during, before):
            judged.append(t.model_copy(update={"holds": False, "measured": f"too thin: {thin}"}))
            continue
        read = natural.sigmas(
            feed.meta, t.metric, t.subject, window, during.value, before.baseline.value
        )
        if read is None:
            judged.append(t.model_copy(update={"holds": False, "measured": "no normal range"}))
            continue
        z = read[0]
        judged.append(
            DecisiveTest.model_validate(
                t.model_dump()
                | {
                    "sigmas": z,
                    "holds": _holds(t.direction, z),
                    "tool_call_id": during.tool_call_id,
                    "measured": f"{t.metric} of {t.subject}: {before.baseline.value:.3f} in the "
                    f"first half, {during.value:.3f} in {window}, so {z:+.2f} sd",
                }
            )
        )
        readings.append((judged[-1], during, before))
    primary = any(t.holds for t in judged if t.side == "primary")
    other = any(t.holds for t in judged if t.side == "rival")
    status = (
        "confirmed"
        if primary and not other
        else "overturned"
        if other and not primary
        else "unresolved"
    )
    settled = follow_up.model_copy(update={"tests": judged, "status": status})
    return Settled(FollowUp.model_validate(settled.model_dump()), tools, sink, readings)


def resolved(card: InsightCard, settled: Settled, finding: Finding, feed: Feed) -> InsightCard:
    """The card's next revision once its follow-up is settled, for the Verifier: the decisive
    readings added to its evidence and, if overturned, the rival named as primary on its own
    test's evidence and the old primary ruled out by its failed prediction."""
    f = settled.follow_up
    revision = card.revision + 1
    # (metric, subject, window) of each reading the revision adds: if overturned, the rival's
    # own test unless the card shows it already; then each decisive test that was measured.
    measured = []
    if f.status == "overturned":
        other = finding.tested_by_id(f.rival_hypothesis_id)
        p = other.hypothesis.prediction
        if all(e.tool_call_id != other.during.tool_call_id for e in card.evidence):
            measured.append((p.metric, p.subject, p.window, other.during, other.before))
    measured += [(t.metric, t.subject, f.window, d, b) for t, d, b in settled.readings]
    added = [
        Evidence(
            metric=metric,
            subject=subject,
            window=window,
            value=d.value,
            baseline=Baseline(window=BaselineScope.FIRST_HALF, value=b.baseline.value),
            n_events=d.n_events,
            tool_call_id=d.tool_call_id,
        )
        for metric, subject, window, d, b in measured
    ]
    sets = list(card.depends_on.evidence_sets) + [
        s for *_, d, b in measured for s in (d.evidence_set_id, b.evidence_set_id)
    ]
    data = card.model_dump(mode="json") | {
        "status": CardStatus.PROPOSED.value,
        "revision": revision,
        "revisions": [r.model_dump(mode="json") for r in card.revisions]
        + [
            Revision(
                revision=revision, at=f.window.end, reason=f"follow-up over {f.window}: {f.status}"
            ).model_dump(mode="json")
        ],
        "evidence": [e.model_dump(mode="json") for e in [*card.evidence, *added]],
        "depends_on": DependsOn(
            evidence_sets=list(dict.fromkeys(sets)), data_version=card.depends_on.data_version
        ).model_dump(mode="json"),
        "follow_up": f.model_dump(mode="json"),
        "verification": None,
        "variants": {},
        "timing": card.timing.model_dump(mode="json")
        | {"verified_at": str(f.window.end), "published_at": None},
    }
    if f.status == "overturned":
        was = card.primary_cause
        attributions = [
            AttributionProposition(
                id=was.id,
                cause=other.hypothesis.taxonomy,
                effect=was.effect,
                role="primary",
                hypothesis_id=other.hypothesis.hypothesis_id,
                agent=other.hypothesis.agent,
            )
            if a.id == was.id
            else a
            for a in card.attributions
            if a.hypothesis_id != f.rival_hypothesis_id
        ]
        failed = next((t for t in f.tests if t.side == "primary"), None)
        ruled_out = RejectedAlternative(
            hypothesis_id=was.hypothesis_id,
            taxonomy=was.cause,
            agent=was.agent,
            team=card.subject.team,
            reason=f"its prediction for {f.window} did not come true"
            + (f": {failed.measured}" if failed and failed.measured else ""),
            rejected_by="follow_up",
            tool_call_id=failed.tool_call_id if failed else None,
        )
        data |= {
            "propositions": [
                p.model_dump(mode="json") for p in card.propositions if p.type == "change"
            ]
            + [a.model_dump(mode="json") for a in attributions],
            "subject": Subject(team=f.rival_team, players=card.subject.players).model_dump(
                mode="json"
            ),
            "rejected_alternatives": [
                r.model_dump(mode="json") for r in [*card.rejected_alternatives, ruled_out]
            ],
        }
    candidate = InsightCard.model_validate(data)
    return candidate.model_copy(update={"claim": narrator.claim(candidate, feed.meta)})
