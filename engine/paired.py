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
from contracts.eval_run import Exclusion, ExclusionRule, ObservableCheck
from contracts.planted import CAUSE_OBSERVABLES, TruthObservable
from contracts.taxonomy import Cause
from engine.script import Intervention, MatchScript
from engine.sim import MatchSim
from engine.visibility import change, observable

Z95 = 1.96
LATEST_START = MatchClock.parse("75:00")  # later starts leave too little match to measure


def window_after(start: MatchClock, offsets: tuple[int, int]) -> Window:
    """Minutes `offsets[0]` to `offsets[1]` after `start`, in the same half."""
    base = start.minute * 60 + start.second

    def at(minutes: int) -> MatchClock:
        total = base + minutes * 60
        return MatchClock(period=start.period, minute=total // 60, second=total % 60)

    return Window(start=at(offsets[0]), end=at(offsets[1]))


def resolve(cause: Cause, script: MatchScript, intervention: Intervention) -> list[TruthObservable]:
    """The class's observables, with their subjects named for this script."""
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
    """Each observable's paired-effect interval and separation over `pairs` seeds.

    Seeds on which the intervention never starts, or starts after LATEST_START, are
    skipped; a seed with no value for one observable (no sprints in the window, say) is
    left out of that observable only.
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
        if len(used) == pairs:
            break
    if len(used) < pairs:
        raise ValueError(f"{script.match_id}: {iv.id} starts in time on only {len(used)} seeds")
    checks = []
    for o, s, n in zip(observables, story, natural, strict=True):
        diffs = [a - b for a, b in zip(s, n, strict=True)]
        half = Z95 * statistics.stdev(diffs) / math.sqrt(len(diffs))
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


def judge(script_id: str, cause: Cause, checks: list[ObservableCheck]) -> Exclusion | None:
    """Spec §7.2: excluded under the first rule the numbers meet, or None if it counts."""
    if not any(c.clears_zero for c in checks):
        rule = ExclusionRule.NO_PAIRED_EFFECT
    elif not any(c.separates for c in checks):
        rule = ExclusionRule.NO_SEPARATION
    else:
        return None
    return Exclusion(script_id=script_id, cause=cause, rule=rule, observables=checks)
