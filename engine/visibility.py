"""Would a detector see a planted story in one match? (spec §7.2)

The detector watches a single match, so a paired-run effect whose confidence interval
clears zero is not enough. A story is visible when its observable's in-match change
(the detection window against the same match's first half) stands out from the change
that observable shows without the story. Separation is that gap in standard deviations
of the natural change, over many seeds. Every observable here rises with its story.
"""

import statistics
from collections.abc import Callable

from contracts.clock import Window
from contracts.event import Event

ON_BALL = ("pass", "carry", "dribble")
RIGHT_CHANNEL_Y = 68 * 2 / 3  # right third of the width, in the acting team's frame

Keep = Callable[[Event], bool]
Observable = Callable[[list[Event], Keep], float]


def first_half(e: Event) -> bool:
    return e.clock.period == 1


def change(observable: Observable, events: list[Event], window: Window) -> float:
    """The observable over `window` minus its first-half value, in one match."""
    return observable(events, lambda e: window.contains(e.clock)) - observable(events, first_half)


def separation(story: list[float], natural: list[float]) -> float:
    """Mean story change above mean natural change, in natural standard deviations."""
    return (statistics.mean(story) - statistics.mean(natural)) / statistics.stdev(natural)


def clears(story_change: float, natural: list[float], sds: float = 2.0) -> bool:
    """One match's change sits at least `sds` natural standard deviations above normal."""
    return story_change >= statistics.mean(natural) + sds * statistics.stdev(natural)


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
