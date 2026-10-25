import pytest
from pydantic import ValidationError

from contracts.ambient import AmbientFeed, ControlPoint, MomentumPoint, TickerLine

RULES = dict(
    sprint_kmh=32,
    shot_kmh=110,
    badge_difficulty=80,
    shot_threat=3,
    entry_threat=1,
    momentum_half_life_min=2,
    control_window_min=5,
    control_min_actions=10,
    control_spell=10,
    chaos_spell=3,
)


def _feed(**overrides):
    base = dict(
        match_id="t01",
        home="St. Orrin",
        away="Northvale",
        rules=RULES,
        speed_tags=[
            dict(
                kind="sprint",
                event_id="e1",
                at="12:00",
                team="Northvale",
                player_id="NV-10",
                speed_kmh=33.4,
            )
        ],
        pass_badges=[],
        momentum=[],
        control=[],
        ticker=[
            dict(
                event_id="e2",
                at="12:30",
                kind="goal",
                team="St. Orrin",
                text=dict(en="Goal", es="Gol"),
            )
        ],
    )
    return base | overrides


def test_a_feed_round_trips_with_clocks_as_text_or_objects():
    feed = AmbientFeed.model_validate(_feed())
    again = AmbientFeed.model_validate_json(feed.model_dump_json())
    assert again == feed
    assert again.speed_tags[0].at.minute == 12


def test_the_gauge_runs_from_long_spells_to_short_ones():
    with pytest.raises(ValidationError, match="shorter"):
        AmbientFeed.model_validate(_feed(rules=RULES | dict(control_spell=3, chaos_spell=10)))


def test_every_ambient_item_names_a_team_in_the_match():
    with pytest.raises(ValidationError, match="teams"):
        AmbientFeed.model_validate(_feed(away="St. Orrin"))
    stranger = dict(_feed()["speed_tags"][0], team="Harbour City")
    with pytest.raises(ValidationError, match="one of the match's teams"):
        AmbientFeed.model_validate(_feed(speed_tags=[stranger]))


def test_ticker_text_is_in_every_viewer_language():
    line = dict(event_id="e", at="1:00", kind="foul", text=dict(en="Foul"))
    with pytest.raises(ValidationError):
        TickerLine.model_validate(line)
    with pytest.raises(ValidationError):
        TickerLine.model_validate(line | dict(kind="opinion", text=dict(en="x", es="y")))


def test_momentum_is_bounded_and_finite():
    point = dict(period=2, minute=63, at="64:00", home_threat=1.0, away_threat=0.0, value=1.0)
    assert MomentumPoint.model_validate(point).value == 1.0
    for bad in (1.2, -1.01, float("nan")):
        with pytest.raises(ValidationError):
            MomentumPoint.model_validate(point | dict(value=bad))


def test_a_gauge_reading_has_both_values_or_neither():
    point = dict(since="58:00", at="63:00", actions=60, turnovers=14, spell=4.0, chaos=0.86)
    assert ControlPoint.model_validate(point).chaos == 0.86
    assert ControlPoint.model_validate(point | dict(spell=None, chaos=None)).spell is None
    with pytest.raises(ValidationError, match="both"):
        ControlPoint.model_validate(point | dict(chaos=None))
    with pytest.raises(ValidationError, match="before"):
        ControlPoint.model_validate(point | dict(since="63:00"))
    with pytest.raises(ValidationError):
        ControlPoint.model_validate(point | dict(chaos=1.5))
