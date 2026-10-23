"""The metrics the planted stories move, as pure functions over events already chosen by
window or baseline. Coordinates are in the acting team's attacking frame.

Each returns a Reading: the value and the sample it rests on. A share or a mean over an
empty sample has no value (None), never NaN; a rate of zero sprints is a real zero.
"""

import statistics
from dataclasses import dataclass

from contracts.event import Event, EventType

ON_BALL = (EventType.PASS, EventType.CARRY, EventType.DRIBBLE)
LONG_PASS_M = 30.0
# The opponent's first 60% of the pitch: x > 42 in the presser's frame, x < 63 in theirs.
PRESS_ZONE_X = 42.0
OPPONENT_ZONE_X = 63.0
THIRD_Y = 68.0 / 3
CHANNELS = ("left", "centre", "right")


@dataclass(frozen=True)
class Reading:
    value: float | None
    n: int


def _x(e: Event) -> float:
    return e.start.x if e.start is not None else float("nan")  # no position: in no zone


def pressure_rate(events: list[Event], team: str, opponent: str) -> Reading:
    """`team`'s pressures in the zone per `opponent` on-ball action starting there."""
    pressures = sum(
        e.type == EventType.PRESSURE and e.team == team and _x(e) > PRESS_ZONE_X for e in events
    )
    actions = sum(
        e.type in ON_BALL and e.team == opponent and _x(e) < OPPONENT_ZONE_X for e in events
    )
    return Reading(pressures / actions if actions else None, actions)


def long_ball_share(events: list[Event], team: str) -> Reading:
    """Share of `team`'s passes longer than 30 m."""
    passes = [e for e in events if e.type == EventType.PASS and e.team == team]
    long = sum(p.pass_q.distance_m > LONG_PASS_M for p in passes)
    return Reading(long / len(passes) if passes else None, len(passes))


def channel_share(events: list[Event], team: str, channel: str) -> Reading:
    """Share of `team`'s on-ball actions starting in one third of the width."""
    ys = [e.start.y for e in events if e.type in ON_BALL and e.team == team and e.start]
    inside = {
        "left": lambda y: y < THIRD_Y,
        "centre": lambda y: THIRD_Y <= y <= 2 * THIRD_Y,
        "right": lambda y: y > 2 * THIRD_Y,
    }[channel]
    return Reading(sum(map(inside, ys)) / len(ys) if ys else None, len(ys))


def _sprints(events: list[Event], players: set[str]) -> list[Event]:
    return [e for e in events if e.type == EventType.SPRINT and e.player_id in players]


def sprint_count(events: list[Event], players: set[str], minutes: float) -> Reading:
    """Sprints per minute of play by the given players."""
    n = len(_sprints(events, players))
    return Reading(n / minutes, n)


def sprint_speed(events: list[Event], players: set[str]) -> Reading:
    """Mean speed of the given players' sprints, in km/h."""
    speeds = [float(e.qualifiers["speed_kmh"]) for e in _sprints(events, players)]
    return Reading(statistics.mean(speeds) if speeds else None, len(speeds))
