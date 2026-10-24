"""Normal variation (spec §8.1, `distribution`): how far a metric moves from the first half to a
second-half window in ordinary play, so a test can say how unusual a change is.

The spread comes from a synthetic season of matches with nothing planted, generated once by
the engine and committed as plain data (`state/season_baselines.json`); product code never
reaches into the engine. A change is read in standard deviations of that spread: the change
minus the season's mean change for the same metric, subject level, window length and minute
(sprints fall late in every match), over the season's standard deviation.
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from contracts.clock import Window
from contracts.meta import MatchMeta
from contracts.taxonomy import DEFAULT_THRESHOLD_KIND, Metric, ThresholdKind
from state.subjects import resolve

SEASON_FILE = Path(__file__).with_name("season_baselines.json")
LENGTHS = (5, 10, 15, 20)  # window minutes the season measures
ENDS = tuple(range(50, 95, 5))  # second-half minutes a window may end at


@dataclass(frozen=True)
class Spread:
    """The season's change for one metric, subject level, window length and end minute."""

    mean: float
    sd: float
    n: int


def level(meta: MatchMeta, subject: str) -> str:
    """'team', 'unit' or 'player': subjects at one level vary alike."""
    who = resolve(meta, subject)
    return "player" if who.player_id else "unit" if who.unit else "team"


def raw_change(metric: Metric, during: float, before: float) -> float | None:
    """The change in the metric's own threshold units: a fraction of the first-half value for
    a count, the difference otherwise; None from a zero count."""
    if DEFAULT_THRESHOLD_KIND[metric] == ThresholdKind.RELATIVE:
        return (during - before) / before if before > 0 else None
    return during - before


def bucket(window: Window) -> tuple[int, int] | None:
    """The season's (length, end minute) nearest a second-half window, or None for a window
    the season does not measure."""
    if window.start.period != 2 or window.end.period != 2:
        return None
    minutes = (window.end.seconds_in_period - window.start.seconds_in_period) / 60
    end = window.end.minute + window.end.second / 60
    length = min(LENGTHS, key=lambda n: abs(n - minutes))
    fits = [e for e in ENDS if e - length >= 45]
    return length, min(fits, key=lambda e: abs(e - end))


@cache
def _season(path: Path = SEASON_FILE) -> dict[tuple[str, str, int, int], Spread]:
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {
        (s["metric"], s["level"], s["minutes"], s["end"]): Spread(s["mean"], s["sd"], s["n"])
        for s in doc["spreads"]
    }


def spread(metric: Metric, subject_level: str, window: Window) -> Spread | None:
    if (at := bucket(window)) is None:
        return None
    return _season().get((metric.value, subject_level, *at))


def sigmas(
    meta: MatchMeta, metric: Metric, subject: str, window: Window, during: float, before: float
) -> tuple[float, Spread] | None:
    """The change from the first half to `window`, in standard deviations of normal variation,
    with the spread it was read against; None when either is undefined."""
    change = raw_change(metric, during, before)
    normal = spread(metric, level(meta, subject), window)
    if change is None or normal is None or normal.sd <= 0:
        return None
    return (change - normal.mean) / normal.sd, normal
