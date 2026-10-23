"""The tool catalog's results (spec §8.1). Each call reads only events delivered by its
`as_of` clock, stores the refs it read as an EvidenceSet, and returns a ToolResult that
points at it, so the Verifier can recompute it and a correction can find it.

Half lengths come from period_end events, never from metadata: a live feed does not know
how long a half runs until it ends.
"""

from dataclasses import dataclass

from contracts.clock import MatchClock, Window
from contracts.event import Event, EventRef, EventType
from contracts.meta import MatchMeta
from contracts.taxonomy import BaselineScope, Metric
from contracts.tool_result import BaselineValue, EvidenceSet, ToolName, ToolResult
from state import metrics
from state.subjects import opponent, players_of, resolve

TEAM_METRICS = {
    Metric.PRESSURE_RATE: "no opponent on-ball actions in the zone",
    Metric.LONG_BALL_SHARE: "no passes",
    Metric.CHANNEL_SHARE_LEFT: "no on-ball actions",
    Metric.CHANNEL_SHARE_CENTRE: "no on-ball actions",
    Metric.CHANNEL_SHARE_RIGHT: "no on-ball actions",
}
SUBJECT_METRICS = {Metric.SPRINT_COUNT: "no sprints", Metric.SPRINT_SPEED: "no sprints"}
MEASURED = TEAM_METRICS | SUBJECT_METRICS


@dataclass(frozen=True)
class Feed:
    """What the State Builder reads: a match's metadata and its events in delivery order."""

    meta: MatchMeta
    events: list[Event]
    data_version: str

    def delivered(self, as_of: MatchClock) -> list[Event]:
        return [e for e in self.events if not as_of < e.clock]


@dataclass(frozen=True)
class Call:
    """Who is asking and when: the ids and clocks a result records."""

    tool_call_id: str
    as_of: MatchClock
    now_ms: int


def first_half_minutes(events: list[Event]) -> float | None:
    """The first half's played length, stoppage included, once its period_end arrives."""
    end = next((e for e in events if e.type == EventType.PERIOD_END and e.clock.period == 1), None)
    return end.clock.seconds_in_period / 60 if end else None


def window_minutes(window: Window) -> float:
    if window.start.period != window.end.period:
        raise ValueError(f"{window} spans half-time")
    return (window.end.seconds_in_period - window.start.seconds_in_period) / 60


def read(
    meta: MatchMeta, name: Metric, subject: str, events: list[Event], minutes: float
) -> metrics.Reading:
    """One metric over events already chosen by window or baseline."""
    if name not in MEASURED:
        raise ValueError(f"the State Builder does not measure {name} yet")
    who = resolve(meta, subject)
    if name in TEAM_METRICS and not who.is_team:
        raise ValueError(f"{name} is measured for a team, not {subject}")
    if name == Metric.PRESSURE_RATE:
        return metrics.pressure_rate(events, who.team, opponent(meta, who.team))
    if name == Metric.LONG_BALL_SHARE:
        return metrics.long_ball_share(events, who.team)
    if name in TEAM_METRICS:
        return metrics.channel_share(events, who.team, name.removeprefix("channel_share_"))
    if name == Metric.SPRINT_COUNT:
        return metrics.sprint_count(events, players_of(meta, who), minutes)
    return metrics.sprint_speed(events, players_of(meta, who))


def _evidence(feed: Feed, call: Call, events: list[Event]) -> EvidenceSet:
    return EvidenceSet(
        evidence_set_id=f"es-{call.tool_call_id}",
        match_id=feed.meta.match_id,
        data_version=feed.data_version,
        events=[EventRef(event_id=e.event_id, version=e.version) for e in events],
    )


def _scoped(
    feed: Feed, scope: BaselineScope, as_of: MatchClock
) -> tuple[list[Event], float | None, str | None]:
    """(events, minutes of play, why not) for a baseline scope."""
    delivered = feed.delivered(as_of)
    half = first_half_minutes(delivered)
    if scope == BaselineScope.FIRST_HALF:
        if half is None:
            return [], None, "the first half has not ended"
        return [e for e in delivered if e.clock.period == 1], half, None
    if scope == BaselineScope.MATCH_SO_FAR:
        played = as_of.seconds_in_period / 60 + ((half or 0.0) if as_of.period == 2 else 0.0)
        return delivered, played, None if played > 0 else "no minutes played yet"
    return [], None, "no season baselines yet (state/season_baselines.json)"


def metric(
    feed: Feed, name: Metric, subject: str, window: Window, call: Call
) -> tuple[ToolResult, EvidenceSet]:
    """`metric(name, subject, window)`: one metric over a window that has finished."""
    if call.as_of < window.end:
        raise ValueError(f"{window} has not finished at {call.as_of}")
    events = [e for e in feed.delivered(call.as_of) if window.contains(e.clock)]
    reading = read(feed.meta, name, subject, events, window_minutes(window))
    evidence = _evidence(feed, call, events)
    result = ToolResult(
        tool_call_id=call.tool_call_id,
        tool=ToolName.METRIC,
        match_id=feed.meta.match_id,
        metric=name,
        subject=subject,
        window=window,
        value=reading.value,
        n_events=reading.n,
        insufficient_data=None if reading.value is not None else MEASURED[name],
        evidence_set_id=evidence.evidence_set_id,
        computed_at_ms=call.now_ms,
    )
    return result, evidence


def baseline(
    feed: Feed, name: Metric, subject: str, scope: BaselineScope, call: Call
) -> tuple[ToolResult, EvidenceSet]:
    """`baseline(name, subject, scope)`: the metric over the first half or the match so far."""
    events, minutes, why_not = _scoped(feed, scope, call.as_of)
    reading = None if why_not else read(feed.meta, name, subject, events, minutes)
    if reading is not None and reading.value is None:
        why_not = MEASURED[name]
    evidence = _evidence(feed, call, events)
    value = None
    if why_not is None:
        value = BaselineValue(
            scope=scope,
            value=reading.value,
            n_events=reading.n,
            evidence_set_id=evidence.evidence_set_id,
        )
    result = ToolResult(
        tool_call_id=call.tool_call_id,
        tool=ToolName.BASELINE,
        match_id=feed.meta.match_id,
        metric=name,
        subject=subject,
        baseline=value,
        n_events=reading.n if reading else 0,
        insufficient_data=why_not,
        evidence_set_id=evidence.evidence_set_id,
        computed_at_ms=call.now_ms,
    )
    return result, evidence


def game_state(feed: Feed, call: Call) -> tuple[ToolResult, EvidenceSet]:
    """`game_state(at)`: the score from the goals delivered by `as_of`."""
    goals = [e for e in feed.delivered(call.as_of) if e.type == EventType.GOAL]
    values = {
        f"{side}_goals": float(sum(g.team == team.name for g in goals))
        for side, team in feed.meta.teams.items()
    }
    evidence = _evidence(feed, call, goals)
    result = ToolResult(
        tool_call_id=call.tool_call_id,
        tool=ToolName.GAME_STATE,
        match_id=feed.meta.match_id,
        at=call.as_of,
        values=values,
        n_events=len(goals),
        evidence_set_id=evidence.evidence_set_id,
        computed_at_ms=call.now_ms,
    )
    return result, evidence
