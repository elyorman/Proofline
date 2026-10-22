"""Each planted story in the demo match is visible in a single match (spec §7.2).

Held-out seeds 100-139 set the natural variation; none of them tuned the engine.
"""

import functools
from pathlib import Path

from contracts.clock import Window
from engine.amend import first_delivered
from engine.script import load_script
from engine.sim import MatchSim
from engine.visibility import (
    change,
    long_ball_share,
    pressure_rate,
    right_channel_share,
    separation,
)

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)
WITHOUT_S1 = M01.model_copy(update={"scripts": [s for s in M01.scripts if s.id != "s1"]})
HELD_OUT = range(100, 140)
CARD = Window.model_validate("58:00-63:00")  # the 63' press card's change window
FLANK = Window.model_validate("45:00-55:00")  # a1's window, and the 55' flank card's
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
    return [_match(s)[name][1] for s in HELD_OUT]


def _separation(name):
    return separation([_match(s)[name][0] for s in HELD_OUT], _natural(name))


def test_raised_press_is_visible_in_one_match():
    assert _separation("pressure_rate") >= 2.5
    assert _separation("long_ball_share") >= 2.5


def test_flank_error_is_visible_until_corrected():
    # Play stays on one side for spells, so a 10-minute channel share is noisy and the
    # largest rise a lateral shift can cause is about a third: the bar is lower.
    assert _separation("right_channel_share") >= 1.5
    assert min(_match(s)["corrected"] for s in HELD_OUT) >= 12
