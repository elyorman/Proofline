"""Each planted story in the demo match is visible in a single match (spec §7.2).

Validation seeds 100-139 set the natural variation; none of them tuned the engine.
"""

import functools
import statistics
from pathlib import Path

import pytest

from contracts.clock import Window
from engine.amend import first_delivered
from engine.script import load_script
from engine.sim import MatchSim
from engine.visibility import (
    change,
    clears,
    long_ball_share,
    pressure_rate,
    right_channel_share,
    separation,
)

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)
WITHOUT_S1 = M01.model_copy(update={"scripts": [s for s in M01.scripts if s.id != "s1"]})
VALIDATION = range(100, 140)
CARD = Window.model_validate("58:00-63:00")  # the 63' press card's change window
FLANK = Window.model_validate("45:00-65:00")  # a1's window
PRESS = {
    "pressure_rate": pressure_rate("Harbour City", "Northvale"),
    "long_ball_share": long_ball_share("Northvale"),
}
RIGHT = right_channel_share("Northvale")


@functools.cache
def _match(seed):
    """Per observable: (change with the story, change without it), in one match.

    The press story's natural change comes from the same seed without s1; the flank
    story's from the truth, which a1 restores.
    """
    events = MatchSim(M01, seed=seed).run()
    without = MatchSim(WITHOUT_S1, seed=seed).run()
    delivered, corrected = first_delivered(M01, events)
    out = {name: (change(f, events, CARD), change(f, without, CARD)) for name, f in PRESS.items()}
    out["right_channel_share"] = change(RIGHT, delivered, FLANK), change(RIGHT, events, FLANK)
    out["corrected"] = len(corrected["a1"])
    return out


def _natural(name):
    return [_match(s)[name][1] for s in VALIDATION]


def _separation(name):
    return separation([_match(s)[name][0] for s in VALIDATION], _natural(name))


def test_raised_press_is_visible_in_one_match():
    assert _separation("pressure_rate") >= 2.5
    assert _separation("long_ball_share") >= 2.5


def test_flank_error_is_visible_as_first_delivered():
    # Play stays on one side for spells, so a 10-minute channel share is noisy and the
    # largest rise a lateral shift can cause is about a third: the bar is lower. 1.5 is
    # the requirement, not a fit: other 40-seed sets give 1.56-2.21, so a change that
    # reshuffles the random draws can land near it without any real regression.
    assert _separation("right_channel_share") >= 1.5
    assert min(_match(s)["corrected"] for s in VALIDATION) >= 12


def _typical_and_visible(name, story_change):
    """At least the validation-seed median, and clear of natural variation."""
    validation = [_match(s)[name][0] for s in VALIDATION]
    return story_change >= statistics.median(validation) and clears(story_change, _natural(name))


def _shows_every_story(seed):
    m = _match(seed)
    stories = ("pressure_rate", "long_ball_share", "right_channel_share")
    corrected_flank = m["right_channel_share"][1]
    return all(_typical_and_visible(name, m[name][0]) for name in stories) and not clears(
        corrected_flank, _natural("right_channel_share")
    )


def test_demo_seed_is_the_first_from_4417_that_shows_every_story():
    for seed in range(4417, 4617):  # about one seed in twelve meets the rule here
        if _shows_every_story(seed):
            break
    else:
        pytest.fail("no seed in 4417-4616 meets the demo-seed rule")
    assert M01.seed == seed, f"the demo-seed rule now picks seed {seed}"
