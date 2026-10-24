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
        _carry("starts-outside-the-band", y0=46.1, y1=40.0),
        _carry("window-start", clock="45:00"),  # windows include their start
        _carry("other-team", team="Harbour City"),
        _carry("first-half", clock="44:59"),
        _carry("window-end", clock="55:00"),  # windows are half-open
        _carry("not-a-listed-type", type_="dribble"),
    ]
    assert corrected_by(A1, "Northvale", events) == ["in", "window-start"]


def test_first_delivered_shows_corrected_events_displaced():
    events = [_carry("in", y0=30.14, y1=46.0), _carry("other-team", team="Harbour City")]
    delivered, corrected = first_delivered(SCRIPT, events)
    assert corrected == {"a1": ["in"]}
    assert (delivered[0].start.y, delivered[0].end.y) == (52.1, 68.0)  # 22 m to the right
    unchanged = {"start", "end"}
    assert delivered[0].model_dump(exclude=unchanged) == events[0].model_dump(exclude=unchanged)
    assert delivered[1] is events[1]


def test_overlapping_amendments_are_refused():
    twice = SCRIPT.model_copy(update={"amendments": [A1, A1.model_copy(update={"id": "a2"})]})
    with pytest.raises(ValueError, match="a2 corrects events already amended"):
        first_delivered(twice, [_carry("in")])


def test_a_written_match_carries_its_first_delivered_feed_and_the_batch_that_corrects_it(
    tmp_path,
):
    from pathlib import Path

    from contracts.clock import MatchClock, Window
    from contracts.taxonomy import Metric
    from engine.io import write_match
    from engine.script import load_script
    from engine.sim import MatchSim
    from state.tools import Call, metric
    from tools_server.server import DirectorySource

    script = load_script(Path(__file__).resolve().parents[1] / "engine/scripts/planted/m01.yaml")
    sim = MatchSim(script)
    truth = sim.run()
    write_match(sim, truth, tmp_path / "m01")
    source = DirectorySource(tmp_path)
    shown = source.feed("m01")
    (a1,) = source.amendments("m01")
    assert a1.amendment_id == "a1" and a1.at == MatchClock.parse("70:00") and a1.shift.dy_m == -22
    fixed = shown.amended(a1)
    true_by_id = {e.event_id: e for e in truth}
    for e in fixed.events:
        assert (e.start, e.end) == (true_by_id[e.event_id].start, true_by_id[e.event_id].end)
        assert e.version == (2 if e.event_id in a1.event_ids else 1)
    assert fixed.data_version == "feed-1+a1" and len(a1.event_ids) == 81

    def right_share(feed):
        call = Call(tool_call_id="tc-1", as_of=MatchClock.parse("70:00"), now_ms=0)
        window = Window.model_validate("45:00-65:00")
        result, _ = metric(feed, Metric.CHANNEL_SHARE_RIGHT, "Northvale", window, call)
        return round(result.value, 3)

    assert (right_share(shown), right_share(fixed)) == (0.715, 0.368)
