"""Speed tags and pass difficulty badges, read from each event's own qualifiers.

Speed tags (spec 8.2). A sprint faster than 32 km/h (`qualifiers.speed_kmh`) or a shot
faster than 110 km/h (`shot_q.shot_speed_kmh`) gets a tag with the player, the clock and
the speed. Both thresholds are strict: 32.0 km/h is not tagged.

Pass difficulty, 0-100, from the pass's own `pass_q`:

    difficulty = 50 * min(distance_m / 40, 1) + 50 * pressure_on_passer

rounded to the nearest whole number, halves to even. Half the scale is length, full marks
from 40 m; half is the pressure on the passer as the feed reports it (0 none, 1 the most).
A completed pass of difficulty 80 or more gets a badge: a long pass under real pressure,
such as 40 m with pressure 0.6 or 32 m with pressure 0.8. Ball speed is left out on
purpose: it says how the pass was struck, not how hard it was to complete. Incomplete
passes never get a badge, however hard they were.
"""

from contracts.ambient import PassBadge, SpeedTag
from contracts.event import Event, EventType, Outcome

SPRINT_TAG_KMH = 32.0
SHOT_TAG_KMH = 110.0
FULL_LENGTH_M = 40.0
BADGE_DIFFICULTY = 80


def speed_tags(events: list[Event]) -> list[SpeedTag]:
    """A tag for every sprint over 32 km/h and every shot over 110 km/h, in feed order."""
    tags = []
    for e in events:
        if e.player_id is None:
            continue
        if e.type == EventType.SPRINT and float(e.qualifiers["speed_kmh"]) > SPRINT_TAG_KMH:
            kind, speed = "sprint", float(e.qualifiers["speed_kmh"])
        elif e.type == EventType.SHOT and e.shot_q.shot_speed_kmh > SHOT_TAG_KMH:
            kind, speed = "shot", e.shot_q.shot_speed_kmh
        else:
            continue
        tags.append(
            SpeedTag(
                kind=kind,
                event_id=e.event_id,
                at=e.clock,
                team=e.team,
                player_id=e.player_id,
                speed_kmh=speed,
            )
        )
    return tags


def pass_difficulty(event: Event) -> int:
    """The 0-100 difficulty of one pass; see the module docstring."""
    if event.type != EventType.PASS:
        raise ValueError("only a pass has a pass difficulty")
    q = event.pass_q
    length = min(q.distance_m / FULL_LENGTH_M, 1.0)
    return round(50 * length + 50 * q.pressure_on_passer)


def pass_badges(events: list[Event]) -> list[PassBadge]:
    """Completed passes of difficulty 80 or more, in feed order."""
    badges = []
    for e in events:
        if e.type != EventType.PASS or e.outcome != Outcome.COMPLETE or e.player_id is None:
            continue
        difficulty = pass_difficulty(e)
        if difficulty < BADGE_DIFFICULTY:
            continue
        badges.append(
            PassBadge(
                event_id=e.event_id,
                at=e.clock,
                team=e.team,
                player_id=e.player_id,
                receiver_id=e.pass_q.receiver_id,
                difficulty=difficulty,
                distance_m=e.pass_q.distance_m,
                pressure_on_passer=e.pass_q.pressure_on_passer,
            )
        )
    return badges
