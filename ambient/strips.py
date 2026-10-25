"""The momentum strip and the control-vs-chaos gauge, minute by minute through each half.

Both restart at each kick-off and use only events already delivered when a value is
shown: a value is stamped with `at`, the clock at which its last counted event is past.

Momentum. Each event carries attacking threat for its team: a shot is worth 3 points, and
a pass, carry or dribble that takes the ball into the final third (from x < 70 to x >= 70
in the acting team's frame; a pass or dribble must be completed) is worth 1. Each team's
threat is summed minute by minute with a half-life of 2 minutes: a minute's threat counts
half as much two minutes later. The strip's value for a minute is

    (home - away) / max(home + away, 3)

from +1 (all the recent threat is the home side's) to -1 (all of it the away side's).
Dividing by at least 3 points, one shot's worth, keeps a quiet spell near zero instead of
letting a single entry swing the strip to an extreme. A minute's value is known at its
end, or at the final whistle of the half.

Control vs chaos. At every minute of each half, over the previous five minutes of that
half, a possession spell is the number of on-ball actions (passes, carries, dribbles) per
possession: actions / (possession changes + 1). Long spells are control; the ball changing
hands every few touches is chaos:

    chaos = clamp((10 - spell) / (10 - 3), 0, 1)

so ten or more actions per possession reads 0 (control) and three or fewer reads 1
(chaos). A window with fewer than 10 on-ball actions, such as the first minute of a half,
is too thin to read and carries no value.
"""

from collections import defaultdict

from contracts.ambient import ControlPoint, MomentumPoint
from contracts.clock import MatchClock
from contracts.event import Event, EventType, Outcome

ON_BALL = (EventType.PASS, EventType.CARRY, EventType.DRIBBLE)
FINAL_THIRD_X = 70.0
SHOT_THREAT = 3.0
ENTRY_THREAT = 1.0
HALF_LIFE_MIN = 2.0
QUIET_THREAT = 3.0
CONTROL_WINDOW_MIN = 5
CONTROL_MIN_ACTIONS = 10
CONTROL_SPELL = 10.0
CHAOS_SPELL = 3.0


def _first_minute(period: int) -> int:
    return 0 if period == 1 else 45


def _clock(period: int, seconds: int) -> MatchClock:
    """The clock `seconds` into a half."""
    minute, second = divmod(seconds, 60)
    return MatchClock(period=period, minute=_first_minute(period) + minute, second=second)


def _halves(events: list[Event]):
    """Each half's events and its final whistle, or None while it is still being played."""
    for period in (1, 2):
        own = [e for e in events if e.clock.period == period]
        if not own:
            continue
        ends = [e.clock for e in own if e.type == EventType.PERIOD_END]
        yield period, own, (ends[0] if ends else None)


def threat(event: Event) -> float:
    """The attacking threat one event carries for its own team."""
    if event.type == EventType.SHOT:
        return SHOT_THREAT
    if (
        event.type in ON_BALL
        and event.start is not None
        and event.end is not None
        and event.start.x < FINAL_THIRD_X <= event.end.x
        and event.outcome not in (Outcome.INCOMPLETE, Outcome.LOST)
    ):
        return ENTRY_THREAT
    return 0.0


def momentum(events: list[Event], home: str, away: str) -> list[MomentumPoint]:
    """The momentum strip: one point per minute of each half, home positive."""
    decay = 0.5 ** (1 / HALF_LIFE_MIN)
    points = []
    for period, own, end in _halves(events):
        per_minute: dict[tuple[int, str], float] = defaultdict(float)
        for e in own:
            per_minute[(e.clock.minute, e.team)] += threat(e)
        last = end or max(e.clock for e in own)
        # A half still being played has no value for its unfinished minute.
        final = last.minute if end is not None and last.second else last.minute - 1
        h = a = 0.0
        for minute in range(_first_minute(period), final + 1):
            h = h * decay + per_minute[(minute, home)]
            a = a * decay + per_minute[(minute, away)]
            at = MatchClock(period=period, minute=minute + 1, second=0)
            points.append(
                MomentumPoint(
                    period=period,
                    minute=minute,
                    at=min(at, end) if end is not None else at,
                    home_threat=round(h, 2),
                    away_threat=round(a, 2),
                    value=round((h - a) / max(h + a, QUIET_THREAT), 3),
                )
            )
    return points


def control(events: list[Event]) -> list[ControlPoint]:
    """The control-vs-chaos gauge at every minute of each half, and at its final whistle."""
    window = CONTROL_WINDOW_MIN * 60
    points = []
    for period, own, end in _halves(events):
        last = (end or max(e.clock for e in own)).seconds_in_period
        samples = list(range(60, last + 1, 60))
        if end is not None and last % 60:
            samples.append(last)
        for t in samples:
            since = max(0, t - window)
            inside = [e for e in own if since <= e.clock.seconds_in_period < t]
            actions = sum(e.type in ON_BALL for e in inside)
            turnovers = sum(e.type == EventType.POSSESSION_CHANGE for e in inside)
            spell = chaos = None
            if actions >= CONTROL_MIN_ACTIONS:
                raw = actions / (turnovers + 1)
                spell = round(raw, 1)
                share = (CONTROL_SPELL - raw) / (CONTROL_SPELL - CHAOS_SPELL)
                chaos = round(min(1.0, max(0.0, share)), 2)
            points.append(
                ControlPoint(
                    since=_clock(period, since),
                    at=_clock(period, t),
                    actions=actions,
                    turnovers=turnovers,
                    spell=spell,
                    chaos=chaos,
                )
            )
    return points
