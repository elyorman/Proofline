"""What the feed first delivered, and which events each amendment corrects (spec §7.1).

The simulator produces the truth. An amendment's filter selects events by their true
position; the provider first showed them displaced by the opposite of the correcting
shift, and the batch at the amendment's `at` moves them back.
"""

from contracts.event import Event, Point
from engine.script import AmendmentSpec, MatchScript


def corrected_by(amendment: AmendmentSpec, team: str, events: list[Event]) -> list[str]:
    """Ids of the events `amendment` relocates: its types, team and window, with the
    true start and end both inside its y band."""
    f = amendment.batch.filter
    return [
        e.event_id
        for e in events
        if e.type in f.types
        and e.team == team
        and f.window.contains(e.clock)
        and f.y_min <= e.start.y <= f.y_max
        and f.y_min <= e.end.y <= f.y_max
    ]


def first_delivered(
    script: MatchScript, events: list[Event]
) -> tuple[list[Event], dict[str, list[str]]]:
    """The events as the feed first showed them, and the ids each amendment corrects."""
    corrected: dict[str, list[str]] = {}
    dy_of: dict[str, float] = {}
    for amendment in script.amendments:
        team = script.teams[amendment.batch.filter.team].name
        ids = corrected_by(amendment, team, events)
        overlap = dy_of.keys() & ids
        if overlap:
            raise ValueError(f"{amendment.id} corrects events already amended: {sorted(overlap)}")
        corrected[amendment.id] = ids
        dy_of |= dict.fromkeys(ids, amendment.batch.shift.dy_m)
    delivered = [
        e.model_copy(
            update={
                "start": Point(x=e.start.x, y=round(e.start.y - dy_of[e.event_id], 1)),
                "end": Point(x=e.end.x, y=round(e.end.y - dy_of[e.event_id], 1)),
            }
        )
        if e.event_id in dy_of
        else e
        for e in events
    ]
    return delivered, corrected
