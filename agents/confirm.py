"""Whether a change is real (spec §9.1): code measures it against normal variation before any
agent looks for its cause. No model is asked.

A detected change is confirmed. The detector picks the most unusual window among many, so
many changes it opens a case on are swings that fade. Five match minutes after it fires, code
re-measures each change it saw over those five minutes alone, events the detector never
read. If one held, the case is investigated over its window run on to that minute; if all
faded, it closes as `none`.

A viewer's question has its premise tested. The viewer, not the detector, chose the stretch of
play, so the change over it is read as it stands.
"""

from mcp.server.mcpserver.exceptions import ToolError

from agents.investigation import BudgetSpent, Tools, change_of, normally, too_few
from contracts.case import Case, Reading
from contracts.case_file import Persistence
from contracts.clock import MatchClock, Window
from contracts.meta import MatchMeta
from contracts.prediction import Direction, Prediction
from contracts.taxonomy import BaselineScope, Metric, ThresholdKind
from contracts.tool_result import ToolResult
from state import natural
from state.tools import Feed, first_half_minutes, read, window_minutes

CONFIRM_MINUTES = 5
# Tuned on the dev split: no swing in a decoy or before a planted change held this far, and
# most changes in a planted window did.
PERSIST_SD = 1.5
# The change itself can thin five minutes of play (a heavier press shortens the opponent's
# time on the ball), so confirming asks half the sample a card needs; a card's own evidence
# still needs all of it.
CONFIRM_SAMPLE = 0.5
PREMISE_SD = 2.0  # a viewer's window is not picked for being unusual: the usual two sd


def extended(case: Case) -> Case:
    """The case as it is investigated: its window run on to the confirming minute."""
    end = case.window.end
    at = MatchClock(period=end.period, minute=end.minute + CONFIRM_MINUTES, second=end.second)
    return case.model_copy(
        update={"window": Window(start=case.window.start, end=at), "detected_at": end}
    )


async def measure(
    tools: Tools,
    meta: MatchMeta,
    metric: Metric,
    subject: str,
    way: Direction,
    window: Window,
    bar: float,
    sample: float = 1.0,
) -> Persistence:
    """`metric` of `subject` over `window` against the first half, in sd of normal variation:
    it holds when it moved `way` by at least `bar`, on at least `sample` of a card's events."""
    p = Prediction(
        metric=metric,
        subject=subject,
        window=window,
        compare_to=BaselineScope.FIRST_HALF,
        direction=way,
        threshold_kind=ThresholdKind.SIGMA,
        min_change=bar,
    )
    row = {"metric": metric, "subject": subject, "direction": way, "window": window}
    try:
        during = await tools.call("metric", name=metric, subject=subject, window=str(window))
        before = await tools.call("baseline", name=metric, subject=subject, scope=p.compare_to)
    except (ToolError, BudgetSpent) as exc:
        return Persistence(**row, holds=False, reason=str(exc))
    row |= {"tool_call_id": during.tool_call_id, "n_events": during.n_events}
    if during.value is None or before.baseline is None:
        why = during.insufficient_data or before.insufficient_data
        return Persistence(**row, holds=False, reason=f"insufficient data: {why}")
    row |= {"value": during.value, "baseline": before.baseline.value}
    if thin := too_few(metric, during, before, sample):
        return Persistence(**row, holds=False, reason=f"too little data: {thin}")
    sigmas = change_of(p, during.value, before.baseline.value, meta)
    holds = sigmas is not None and p.supported_by(sigmas)
    measured = "no normal range" if sigmas is None else f"{normally(p, meta)}, so {sigmas:+.2f} sd"
    verdict = "it held" if holds else f"short of {bar:g} sd {way}"
    reason = (
        f"{metric} of {subject} in {window}: {during.value:.3f} against "
        f"{before.baseline.value:.3f} in the first half; {measured}; {verdict}"
    )
    return Persistence(**row, sigmas=sigmas, holds=holds, reason=reason)


async def confirm(tools: Tools, case: Case, meta: MatchMeta) -> list[Persistence]:
    """Each trigger of an extended case, re-measured over the minutes after detection."""
    after = Window(start=case.detected_at, end=case.window.end)
    return [
        await measure(
            tools,
            meta,
            t.metric,
            t.subject,
            Direction.UP if t.value > t.baseline_value else Direction.DOWN,
            after,
            PERSIST_SD,
            CONFIRM_SAMPLE,
        )
        for t in case.triggers
    ]


async def explained(
    tools: Tools, metric: Metric, subject: str, way: Direction, window: Window
) -> tuple[Prediction, ToolResult, ToolResult] | None:
    """The change a card explains, measured over the case's window: the card's headline and
    its primary cause's effect. Every hypothesis is about this change; its own prediction is
    the evidence that tells its cause from the others."""
    p = Prediction(
        metric=metric,
        subject=subject,
        window=window,
        compare_to=BaselineScope.FIRST_HALF,
        direction=way,
        threshold_kind=ThresholdKind.SIGMA,
        min_change=PERSIST_SD,
    )
    try:
        during = await tools.call("metric", name=metric, subject=subject, window=str(window))
        before = await tools.call("baseline", name=metric, subject=subject, scope=p.compare_to)
    except (ToolError, BudgetSpent):
        return None
    if during.value is None or before.baseline is None:
        return None
    return p, during, before


OVERVIEW = (Metric.PRESSURE_RATE, Metric.LONG_BALL_SHARE, Metric.SPRINT_COUNT)


def both_teams(feed: Feed, window: Window) -> list[Reading]:
    """Each team's pressing, long balls and sprints over `window` against its first half, in
    sd of normal variation: what an analyst glances at before asking why. Measurement only;
    it names no cause."""
    delivered = feed.delivered(window.end)
    first = [e for e in delivered if e.clock.period == 1]
    during = [e for e in delivered if window.contains(e.clock)]
    half, minutes = first_half_minutes(delivered), window_minutes(window)
    out = []
    for team in (t.name for t in feed.meta.teams.values()):
        for metric in OVERVIEW:
            now = read(feed.meta, metric, team, during, minutes)
            then = read(feed.meta, metric, team, first, half)
            if now.value is None or then.value is None:
                continue
            z = natural.sigmas(feed.meta, metric, team, window, now.value, then.value)
            out.append(
                Reading(
                    metric=metric,
                    subject=team,
                    value=now.value,
                    baseline_value=then.value,
                    sigmas=round(z[0], 2) if z else None,
                )
            )
    return out
