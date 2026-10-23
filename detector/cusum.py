"""CUSUM over each watched series' change from the first half (spec §8.3).

Each minute of the second half, a series is measured over the trailing window and
compared with its first-half value. The change, less an allowance `k`, accumulates in
the series' direction; when the sum reaches the decision limit `h` the series fires and
re-arms only once its change falls back within the allowance (hysteresis). A window
with fewer than `min_n` events adds nothing. Fires of one moment type within
`MERGE_MINUTES` of an open case join it. The first half is the baseline, so nothing
fires before half-time.
"""

from dataclasses import dataclass, field

from contracts.case import Case, TriggerMetric
from contracts.clock import MatchClock, Window
from contracts.event import Event
from contracts.meta import MatchMeta
from contracts.taxonomy import Metric, MomentType
from state.tools import first_half_minutes, read, window_minutes

MERGE_MINUTES = 3


@dataclass(frozen=True)
class Watch:
    """One kind of series and how it is judged: allowance, limit and sample, in the
    metric's own units, tuned on the dev split (scripts/tune_detector.py)."""

    moment: MomentType
    metric: Metric
    window: int  # minutes
    k: float
    h: float
    min_n: int
    ways: tuple[int, ...] = (1, -1)  # +1 watches rises, -1 falls


# Tuned on the dev split by scripts/tune_detector.py: allowance and limit are its chosen
# multiples of each series' natural p90 change, at most 0.5 natural cases a match each.
WATCHES = (
    Watch(MomentType.PRESSURE_SHIFT, Metric.PRESSURE_RATE, 5, k=0.212, h=0.424, min_n=8),
    Watch(MomentType.PRESSURE_SHIFT, Metric.LONG_BALL_SHARE, 5, k=0.154, h=0.231, min_n=8),
    Watch(MomentType.FATIGUE_SIGNAL, Metric.SPRINT_COUNT, 10, 0.755, 2.265, min_n=0, ways=(-1,)),
    # No class plants a flank change, so a flank watch is as sensitive as 0.2 natural cases
    # a match allows: play shifting onto one wing.
    Watch(MomentType.SHAPE_CHANGE, Metric.CHANNEL_SHARE_LEFT, 10, 0.26, 0.52, min_n=8, ways=(1,)),
    Watch(
        MomentType.SHAPE_CHANGE, Metric.CHANNEL_SHARE_RIGHT, 10, 0.261, 0.522, min_n=8, ways=(1,)
    ),
)
UNITS = ("defence", "midfield", "attack")


@dataclass
class SeriesState:
    sums: dict[int, float] = field(default_factory=dict)
    armed: dict[int, bool] = field(default_factory=dict)


def step(state: SeriesState, watch: Watch, change: float) -> bool:
    """One minute of one series: accumulate, and say whether it fires."""
    fired = False
    for way in watch.ways:
        signed = way * change
        if not state.armed.get(way, True):
            state.armed[way] = signed < watch.k  # re-arm once back within the allowance
            continue
        total = max(0.0, state.sums.get(way, 0.0) + signed - watch.k)
        if total >= watch.h:
            state.sums[way], state.armed[way], fired = 0.0, False, True
        else:
            state.sums[way] = total
    return fired


def subjects(meta: MatchMeta, watch: Watch) -> list[str]:
    teams = [t.name for t in meta.teams.values()]
    if watch.metric == Metric.SPRINT_COUNT:
        return [f"{t}.{u}" for t in teams for u in UNITS]
    return teams


@dataclass
class Detector:
    """Feed it the events delivered so far once a minute; it returns the cases it opened or
    added a trigger to."""

    meta: MatchMeta
    watches: tuple[Watch, ...] = WATCHES
    cases: list[Case] = field(default_factory=list)
    _series: dict[tuple[int, str], SeriesState] = field(default_factory=dict)
    _baselines: dict[tuple[int, str], float | None] = field(default_factory=dict)

    def tick(self, delivered: list[Event], minute: int) -> list[Case]:
        """Judge every series at `minute`:00 of the second half."""
        half = first_half_minutes(delivered)
        if half is None:
            return []
        touched: list[Case] = []
        first = [e for e in delivered if e.clock.period == 1]
        for i, watch in enumerate(self.watches):
            if minute - watch.window < 45:
                continue
            window = Window(start=_clock(minute - watch.window), end=_clock(minute))
            during = [e for e in delivered if window.contains(e.clock)]
            for subject in subjects(self.meta, watch):
                key = (i, subject)
                if key not in self._baselines:
                    self._baselines[key] = read(self.meta, watch.metric, subject, first, half).value
                base = self._baselines[key]
                now = read(self.meta, watch.metric, subject, during, window_minutes(window))
                if base is None or now.value is None or now.n < watch.min_n:
                    continue
                if step(self._series.setdefault(key, SeriesState()), watch, now.value - base):
                    trigger = TriggerMetric(
                        metric=watch.metric,
                        subject=subject,
                        value=now.value,
                        baseline_value=base,
                        n_events=now.n,
                    )
                    case = self._open(watch.moment, window, trigger, minute)
                    if all(case is not c for c in touched):
                        touched.append(case)
        return touched

    def _open(
        self, moment: MomentType, window: Window, trigger: TriggerMetric, minute: int
    ) -> Case:
        for case in self.cases:
            if case.moment_type == moment and minute - case.window.end.minute <= MERGE_MINUTES:
                case.triggers.append(trigger)
                return case
        case = Case(
            case_id=f"case-{self.meta.match_id}-{minute:03d}-{moment}",
            match_id=self.meta.match_id,
            moment_type=moment,
            window=window,
            triggers=[trigger],
        )
        self.cases.append(case)
        return case


def _clock(minute: int) -> MatchClock:
    return MatchClock(period=2, minute=minute, second=0)


def detect(meta: MatchMeta, events: list[Event], last_minute: int = 90) -> list[Case]:
    """Replay a whole match through the detector, a minute at a time (batch mode)."""
    detector = Detector(meta)
    for minute in range(46, last_minute + 1):
        cutoff = _clock(minute)
        detector.tick([e for e in events if e.clock < cutoff], minute)
    return detector.cases
