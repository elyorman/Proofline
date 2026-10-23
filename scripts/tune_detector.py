#!/usr/bin/env python3
"""Tune each detector watch's allowance k and decision limit h on the dev split only.

Natural matches are 40 dev decoy-style matches (nothing planted, the planted classes'
starting styles); planted matches are the dev planted suite. For each watch, the grid
point that catches the most planted changes of its classes, while opening at most
`MAX_NATURAL` cases per natural match, wins; ties go to fewer natural cases. A planted
change is caught when its watch fires on one of its class's observables between the
change's start and five minutes after its window. Held-out seeds are never touched.

    uv run python scripts/tune_detector.py
"""

import itertools
import statistics
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import yaml

from contracts.clock import MatchClock, Window
from contracts.eval_run import Split
from contracts.planted import GroundTruth
from detector.cusum import UNITS, WATCHES, SeriesState, step, subjects
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from engine.suite_builder import decoys
from state.tools import first_half_minutes, read, window_minutes

DEV = Path(__file__).resolve().parents[1] / "engine" / "suites" / "planted" / "dev"
MAX_NATURAL = 0.5
GRID = {"k": (0.5, 0.75, 1.0), "h": (1.0, 1.5, 2.0, 3.0)}  # in natural p90s of |change|


def _changes(script):
    """{(watch, subject): [(minute, change)]} for one match."""
    sim = MatchSim(script)
    events = sim.run()
    meta = match_meta(sim)
    half = first_half_minutes(events)
    first = [e for e in events if e.clock.period == 1]
    out = {}
    for i, w in enumerate(WATCHES):
        for subject in subjects(meta, w):
            base = read(meta, w.metric, subject, first, half).value
            seq = []
            for m in range(45 + w.window, 91):
                win = Window(start=_clock(m - w.window), end=_clock(m))
                now = read(
                    meta,
                    w.metric,
                    subject,
                    [e for e in events if win.contains(e.clock)],
                    window_minutes(win),
                )
                if base is not None and now.value is not None and now.n >= w.min_n:
                    seq.append((m, now.value - base))
            out[i, subject] = seq
    return out


def _clock(minute):
    return MatchClock(period=2, minute=minute, second=0)


def _fires(watch, seq):
    """Minutes at which one series fires under `watch`'s k and h."""
    state = SeriesState()
    return [m for m, change in seq if step(state, watch, change)]


def _caught(truth, watch, fires_by_series):
    """Whether the watch fired on one of the change's observables in time. The detector
    watches units, so a tired player counts as caught when one of his team's units fires."""
    watched = set()
    for o in truth.observables:
        if o.metric == watch.metric:
            is_player = o.subject != truth.team and "." not in o.subject and o.subject[2:3] == "-"
            watched |= {f"{truth.team}.{u}" for u in UNITS} if is_player else {o.subject}
    late = truth.window.end.minute + 5
    return any(
        truth.started.minute <= m <= late for s in watched for m in fires_by_series.get(s, [])
    )


def main() -> None:
    truth = GroundTruth.model_validate(yaml.safe_load((DEV / "ground_truth.yaml").read_text()))
    planted = [load_script(DEV / "scripts" / f"{e.match_id}.yaml") for e in truth.entries]
    natural = decoys(Split.DEV, count=40).scripts
    with Pool(4) as pool:
        planted_changes = pool.map(_changes, planted)
        natural_changes = pool.map(_changes, natural)
    for i, w in enumerate(WATCHES):
        p90 = statistics.quantiles(
            [
                abs(c)
                for nc in natural_changes
                for (j, _), seq in nc.items()
                if j == i
                for _, c in seq
            ],
            n=10,
        )[8]
        relevant = [
            (t, pc)
            for t, pc in zip(truth.entries, planted_changes, strict=True)
            if any(o.metric == w.metric for o in t.observables)
        ]
        best = None
        for k, h in itertools.product(GRID["k"], GRID["h"]):
            trial = replace(w, k=round(k * p90, 3), h=round(h * p90, 3))
            natural_cases = statistics.mean(
                sum(len(_fires(trial, seq)) for (j, _), seq in nc.items() if j == i)
                for nc in natural_changes
            )
            caught = sum(
                _caught(t, w, {s: _fires(trial, seq) for (j, s), seq in pc.items() if j == i})
                for t, pc in relevant
            )
            score = (natural_cases <= MAX_NATURAL, caught, -natural_cases)
            if best is None or score > best[0]:
                best = (score, trial, natural_cases, caught)
        _, trial, natural_cases, caught = best
        print(
            f"{w.moment} {w.metric}: k={trial.k} h={trial.h} min_n={w.min_n} "
            f"(natural p90 {p90:.3f}); {natural_cases:.2f} natural cases a match; "
            f"caught {caught} of {len(relevant)} dev planted changes"
        )


if __name__ == "__main__":
    main()
