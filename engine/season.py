"""A synthetic season: matches with nothing planted, measured with the State Builder's own
metrics, so `state/natural.py` knows how far each metric moves in ordinary play.

Each match sets one team up in the starting style of one class's template, the classes taken
in turn, as the decoys do, so the season covers the styles the suites play in. Its seeds are
a range of their own that nothing else draws from (spec §11.1). A measurement on fewer events
than a claim needs (the Verifier's minimum samples) is left out, as a test would leave it.
"""

import random
import statistics
from collections import defaultdict
from multiprocessing import Pool

from agents.verifier.rules import MIN_SAMPLE
from contracts.clock import Window
from contracts.planted import CAUSE_OBSERVABLES
from contracts.taxonomy import Metric
from engine.io import match_meta
from engine.script import MatchScript
from engine.sim import MatchSim
from engine.suite_builder import _styled
from state.natural import ENDS, LENGTHS, raw_change
from state.subjects import resolve
from state.tools import MEASURED, SUBJECT_METRICS, first_half_minutes, read

SEASON_SEEDS = range(3000, 3200)
UNITS = ("defence", "midfield", "attack")


def _windows() -> dict[tuple[int, int], Window]:
    return {
        (n, end): Window.model_validate(f"{end - n}:00-{end}:00")
        for n in LENGTHS
        for end in ENDS
        if end - n >= 45
    }


def _changes(k: int) -> list[tuple[str, str, int, int, float]]:
    """(metric, level, minutes, end, change) for every subject and window of season match k."""
    styles = list(CAUSE_OBSERVABLES)
    teams, _, _ = _styled(styles[k % len(styles)], random.Random(f"season:{k}"))
    sim = MatchSim(MatchScript(match_id=f"s{k:03d}", seed=SEASON_SEEDS[k], teams=teams))
    events = sim.run()
    meta = match_meta(sim)
    first, half = [e for e in events if e.clock.period == 1], first_half_minutes(events)
    subjects = [
        s
        for t in meta.teams.values()
        for s in [t.name, *(f"{t.name}.{u}" for u in UNITS), *(p.player_id for p in t.players)]
    ]
    windows = {key: [e for e in events if w.contains(e.clock)] for key, w in _windows().items()}
    out = []
    for subject in subjects:
        who = resolve(meta, subject)
        level = "player" if who.player_id else "unit" if who.unit else "team"
        for metric in MEASURED if who.is_team else SUBJECT_METRICS:
            before = read(meta, metric, subject, first, half)
            if before.value is None:
                continue
            for (n, end), during_events in windows.items():
                during = read(meta, metric, subject, during_events, n)
                sample = before.n if metric == Metric.SPRINT_COUNT else during.n
                if during.value is None or sample < MIN_SAMPLE[metric]:
                    continue
                change = raw_change(metric, during.value, before.value)
                if change is not None:
                    out.append((metric.value, level, n, end, change))
    return out


def season(matches: int = len(SEASON_SEEDS), workers: int | None = None) -> dict:
    """The season's spread of every metric's change, by subject level, window length and end."""
    if not 1 < matches <= len(SEASON_SEEDS):
        raise ValueError(f"a season holds 2 to {len(SEASON_SEEDS)} matches")
    with Pool(workers) as pool:
        measured = pool.map(_changes, range(matches))
    grouped: dict[tuple, list[float]] = defaultdict(list)
    for rows in measured:
        for metric, level, n, end, change in rows:
            grouped[metric, level, n, end].append(change)
    spreads = [
        {
            "metric": metric,
            "level": level,
            "minutes": n,
            "end": end,
            "n": len(changes),
            "mean": round(statistics.mean(changes), 5),
            "sd": round(statistics.stdev(changes), 5),
        }
        for (metric, level, n, end), changes in sorted(grouped.items())
        if len(changes) >= 2
    ]
    return {
        "about": "change from the first half to a second-half window over matches with nothing "
        "planted, in each metric's threshold units (spec §8.1, state/natural.py)",
        "seeds": [SEASON_SEEDS.start, SEASON_SEEDS.start + matches - 1],
        "matches": matches,
        "spreads": spreads,
    }
