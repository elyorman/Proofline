import pytest

from contracts.event import Event, Point
from engine.amend import corrected_by, first_delivered
from engine.script import MatchScript

SCRIPT = MatchScript.model_validate(
    {
        "match_id": "t01",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC"},
            "away": {"name": "Northvale", "code": "NV"},
        },
        "amendments": [
            {
                "id": "a1",
                "at": "68:00",
                "batch": {
                    "filter": {
                        "types": ["pass", "carry"],
                        "team": "away",
                        "window": "45:00-55:00",
                        "y_min": 0,
                        "y_max": 46,
                    },
                    "shift": {"dy_m": -22},
                },
                "reason": "provider coordinate recalibration",
            }
        ],
    }
)
A1 = SCRIPT.amendments[0]


def _carry(event_id, clock="50:00", team="Northvale", y0=30.0, y1=40.0, type_="carry"):
    return Event(
        event_id=event_id,
        match_id="t01",
        clock=clock,
        wall_clock_ms=0,
        type=type_,
        team=team,
        start=Point(x=50, y=y0),
        end=Point(x=55, y=y1),
    )


def test_selects_by_type_team_window_and_true_position():
    events = [
        _carry("in"),
        _carry("ends-outside-the-band", y1=46.1),
        _carry("other-team", team="Harbour City"),
        _carry("first-half", clock="44:59"),
        _carry("window-end", clock="55:00"),  # windows are half-open
        _carry("not-a-listed-type", type_="dribble"),
    ]
    assert corrected_by(A1, "Northvale", events) == ["in"]


def test_first_delivered_shows_corrected_events_displaced():
    events = [_carry("in", y0=30.0, y1=46.0), _carry("other-team", team="Harbour City")]
    delivered, corrected = first_delivered(SCRIPT, events)
    assert corrected == {"a1": ["in"]}
    assert (delivered[0].start.y, delivered[0].end.y) == (52.0, 68.0)  # 22 m to the right
    unchanged = {"start", "end"}
    assert delivered[0].model_dump(exclude=unchanged) == events[0].model_dump(exclude=unchanged)
    assert delivered[1] is events[1]


def test_overlapping_amendments_are_refused():
    twice = SCRIPT.model_copy(update={"amendments": [A1, A1.model_copy(update={"id": "a2"})]})
    with pytest.raises(ValueError, match="a2 corrects events already amended"):
        first_delivered(twice, [_carry("in")])
