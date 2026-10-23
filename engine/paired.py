"""Paired runs: a script with and without one intervention, over many seeds (spec §7.2).

For every seed on which the intervention starts in time, the engine runs the match twice
and measures each observable's in-match change over a window anchored where the change
began. The paired difference gives the effect's confidence interval; the spread of the
change without the intervention gives the natural variation that separation is measured
in. From those numbers a script either counts toward recall or is excluded, and why.
"""

import math
import statistics
from collections.abc import Iterable

from contracts.clock import MatchClock, Window
from contracts.eval_run import MIN_SEED_PAIRS, Exclusion, ExclusionRule, ObservableCheck
from contracts.planted import CAUSE_OBSERVABLES, TruthObservable
from contracts.taxonomy import Cause
from engine.script import Intervention, MatchScript
from engine.sim import MatchSim
from engine.visibility import change, observable

Z95 = 1.959964
LATEST_START = MatchClock.parse("75:00")  # later starts leave too little match to measure
LAST_WINDOW_END = MatchClock.parse("90:00")  # every match plays at least this far


def t95(df: int) -> float:
    """The two-sided 95% Student t quantile, by Cornish-Fisher expansion: within 0.001 of
    the table from 19 degrees of freedom, the fewest that MIN_SEED_PAIRS allows."""
    z = Z95
    return z + (z**3 + z) / (4 * df) + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * df**2)


def window_after(start: MatchClock, offsets: tuple[int, int]) -> Window:
    """Minutes `offsets[0]` to `offsets[1]` after a second-half `start`.

    A change is compared with the first half (engine/visibility.py), so one that starts
    before half-time is refused; spec §7.2 compares it with the minutes before it, which
    nothing here does yet. The window must end by 90:00, so that every minute is played.
    """
    if start.period == 1:
        raise ValueError(f"{start}: a first-half change cannot be compared with the first half")
    base = start.minute * 60 + start.second

    def at(minutes: int) -> MatchClock:
        total = base + minutes * 60
        return MatchClock(period=start.period, minute=total // 60, second=total % 60)

    window = Window(start=at(offsets[0]), end=at(offsets[1]))
    if LAST_WINDOW_END < window.end:
        raise ValueError(f"{window} ends after {LAST_WINDOW_END}, which not every match plays")
    return window


def resolve(cause: Cause, script: MatchScript, intervention: Intervention) -> list[TruthObservable]:
    """The class's observables, with their subjects named for this script."""
    for role in ("unit", "player"):
        needed = any(o.subject == role for o in CAUSE_OBSERVABLES[cause])
        if needed and getattr(intervention, role) is None:
            raise ValueError(f"{cause} is measured on a {role}; {intervention.id} names none")
    team = script.teams[intervention.team].name
    opponent = script.teams["away" if intervention.team == "home" else "home"].name
    subjects = {
        "team": team,
        "opponent": opponent,
        "unit": f"{team}.{intervention.unit}",
        "player": intervention.player,
    }
    return [
        TruthObservable(metric=o.metric, subject=subjects[o.subject], direction=o.direction)
        for o in CAUSE_OBSERVABLES[cause]
    ]


def _opponent(script: MatchScript, subject: str) -> str:
    names = [t.name for t in script.teams.values()]
    team = subject.partition(".")[0]
    return next((n for n in names if n != team), names[0])


def measure(
    script: MatchScript,
    script_id: str,
    observables: list[TruthObservable],
    offsets: tuple[int, int],
    seeds: Iterable[int],
    pairs: int,
) -> tuple[list[ObservableCheck], list[int]]:
    """Each observable's paired-effect interval and separation over at least `pairs` seeds.

    Seeds on which the intervention never starts, or starts after LATEST_START, are
    skipped. A seed with no value for one observable (no sprints in the window, say) is
    left out of that observable only, and seeds are run until every observable has
    `pairs` of them; the seeds returned are all those run.
    """
    iv = next(s for s in script.scripts if s.id == script_id)
    without = script.model_copy(update={"scripts": [s for s in script.scripts if s.id != iv.id]})
    measures = [observable(o.metric, o.subject, _opponent(script, o.subject)) for o in observables]
    story: list[list[float]] = [[] for _ in observables]
    natural: list[list[float]] = [[] for _ in observables]
    used: list[int] = []
    for seed in seeds:
        sim = MatchSim(script, seed=seed)
        events = sim.run()
        start = sim.params.started[iv.id]
        if start is None or LATEST_START < start:
            continue
        window = window_after(start, offsets)
        plain = MatchSim(without, seed=seed).run()
        for i, f in enumerate(measures):
            pair = change(f, events, window), change(f, plain, window)
            if not any(math.isnan(x) for x in pair):
                story[i].append(pair[0])
                natural[i].append(pair[1])
        used.append(seed)
        if min(len(s) for s in story) >= pairs:
            break
    measured = min(len(s) for s in story)
    if measured < max(pairs, MIN_SEED_PAIRS):
        raise ValueError(
            f"{script.match_id}: {iv.id} starts in time on {len(used)} seeds, "
            f"and every observable has a value on {measured}"
        )
    checks = []
    for o, s, n in zip(observables, story, natural, strict=True):
        if statistics.stdev(n) == 0:
            raise ValueError(f"{script.match_id}: {o.metric} of {o.subject} never varies")
        diffs = [a - b for a, b in zip(s, n, strict=True)]
        half = t95(len(diffs) - 1) * statistics.stdev(diffs) / math.sqrt(len(diffs))
        mean = statistics.mean(diffs)
        checks.append(
            ObservableCheck(
                metric=o.metric,
                subject=o.subject,
                direction=o.direction,
                separation=(statistics.mean(s) - statistics.mean(n)) / statistics.stdev(n),
                ci_low=mean - half,
                ci_high=mean + half,
            )
        )
    return checks, used


def judge(match_id: str, cause: Cause, checks: list[ObservableCheck]) -> Exclusion | None:
    """Spec §7.2: excluded under the first rule the numbers meet, or None if it counts."""
    if not any(c.clears_zero for c in checks):
        rule = ExclusionRule.NO_PAIRED_EFFECT
    elif not any(c.separates for c in checks):
        rule = ExclusionRule.NO_SEPARATION
    else:
        return None
    return Exclusion(match_id=match_id, cause=cause, rule=rule, observables=checks)
