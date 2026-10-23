"""Would a detector see a planted story in one match? (spec §7.2)

The detector watches a single match, so a paired-run effect whose confidence interval
clears zero is not enough. A story is visible when its observable's in-match change
(the detection window against the same match's first half) stands out from the change
that observable shows without the story. Separation is that gap in standard deviations
of the natural change, over many seeds. Separation is signed like the change: positive
when the observable rose. A story clears when its change goes far enough in its own
direction. Counts compared across windows of different lengths are rates per minute of play.
"""

import re
import statistics
from collections.abc import Callable
from typing import get_args

from contracts.clock import Window
from contracts.eval_run import VISIBILITY_SDS
from contracts.event import Event
from contracts.prediction import Direction
from contracts.taxonomy import Metric
from engine.script import PLAYER_ID, Unit
from engine.teams import UNIT_OF_ROLE

ON_BALL = ("pass", "carry", "dribble")
RIGHT_CHANNEL_Y = 68 * 2 / 3  # right third of the width, in the acting team's frame

Keep = Callable[[Event], bool]
Observable = Callable[[list[Event], Keep], float]


class PerMinute:
    """A count, compared per minute of play so that windows of different lengths compare."""

    def __init__(self, count: Callable[[list[Event], Keep], int]) -> None:
        self.count = count


def first_half(e: Event) -> bool:
    return e.clock.period == 1


def first_half_minutes(events: list[Event]) -> float:
    """The first half's played length, stoppage included, from its period_end event."""
    end = next((e for e in events if e.type == "period_end" and e.clock.period == 1), None)
    if end is None:
        raise ValueError("no first-half period_end: the first half's length is unknown")
    return end.clock.seconds_in_period / 60


def window_minutes(window: Window) -> float:
    if window.start.period != window.end.period:
        raise ValueError(f"{window} spans half-time")
    return (window.end.seconds_in_period - window.start.seconds_in_period) / 60


def change(observable: Observable | PerMinute, events: list[Event], window: Window) -> float:
    """The observable over `window` minus its first-half value, in one match."""

    def in_window(e: Event) -> bool:
        return window.contains(e.clock)

    if isinstance(observable, PerMinute):
        during = observable.count(events, in_window) / window_minutes(window)
        return during - observable.count(events, first_half) / first_half_minutes(events)
    return observable(events, in_window) - observable(events, first_half)


def separation(story: list[float], natural: list[float]) -> float:
    """Mean story change minus mean natural change, in natural standard deviations."""
    return (statistics.mean(story) - statistics.mean(natural)) / statistics.stdev(natural)


def clears(
    story_change: float,
    natural: list[float],
    sds: float = VISIBILITY_SDS,
    direction: Direction = Direction.UP,
) -> bool:
    """One match's change sits at least `sds` natural standard deviations past normal,
    in the story's direction."""
    way = 1 if direction == Direction.UP else -1
    return way * (story_change - statistics.mean(natural)) >= sds * statistics.stdev(natural)


def pressure_rate(presser: str, opponent: str) -> Observable:
    """Pressures by `presser` per `opponent` on-ball action in the opponent's first 60%.

    A rate, not a count: a heavier press also shortens the opponent's time on the ball.
    That zone is x < 63 in the opponent's frame and x > 42 in the presser's.
    """

    def rate(events: list[Event], keep: Keep) -> float:
        pressures = sum(
            e.type == "pressure" and e.team == presser and e.start.x > 42 and keep(e)
            for e in events
        )
        actions = sum(
            e.type in ON_BALL and e.team == opponent and e.start.x < 63 and keep(e) for e in events
        )
        return pressures / actions

    return rate


def long_ball_share(team: str) -> Observable:
    """Share of `team`'s passes longer than 30 m."""

    def share(events: list[Event], keep: Keep) -> float:
        passes = [e for e in events if e.type == "pass" and e.team == team and keep(e)]
        return sum(p.pass_q.distance_m > 30 for p in passes) / len(passes)

    return share


def right_channel_share(team: str) -> Observable:
    """Share of `team`'s on-ball actions that start in the right third of the width."""

    def share(events: list[Event], keep: Keep) -> float:
        ys = [e.start.y for e in events if e.type in ON_BALL and e.team == team and keep(e)]
        return sum(y > RIGHT_CHANNEL_Y for y in ys) / len(ys)

    return share


def _sprints_of(subject: str) -> Callable[[Event], bool]:
    """Sprints by a team ("Harbour City"), one of its units ("Harbour City.defence") or a
    player ("HC-10")."""
    if re.fullmatch(PLAYER_ID, subject):
        return lambda e: e.type == "sprint" and e.player_id == subject
    team, _, unit = subject.rpartition(".")
    if unit not in get_args(Unit):
        team, unit = subject, ""
    return lambda e: (
        e.type == "sprint" and e.team == team and (not unit or UNIT_OF_ROLE[e.position] == unit)
    )


def sprint_count(subject: str) -> PerMinute:
    """Sprints by a team, unit or player, per minute of play."""
    mine = _sprints_of(subject)
    return PerMinute(lambda events, keep: sum(mine(e) and keep(e) for e in events))


def sprint_speed(subject: str) -> Observable:
    """Mean speed of a team's, unit's or player's sprints, in km/h; NaN with none."""
    mine = _sprints_of(subject)

    def speed(events: list[Event], keep: Keep) -> float:
        speeds = [e.qualifiers["speed_kmh"] for e in events if mine(e) and keep(e)]
        return statistics.mean(speeds) if speeds else float("nan")

    return speed


def observable(metric: Metric, subject: str, opponent: str) -> Observable | PerMinute:
    """The engine's measure of a contracts metric for `subject` (whose opponent is named)."""
    if metric == Metric.PRESSURE_RATE:
        return pressure_rate(subject, opponent)
    if metric == Metric.LONG_BALL_SHARE:
        return long_ball_share(subject)
    if metric == Metric.SPRINT_COUNT:
        return sprint_count(subject)
    if metric == Metric.SPRINT_SPEED:
        return sprint_speed(subject)
    raise ValueError(f"the engine does not measure {metric}")
