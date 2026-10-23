from pathlib import Path

from contracts.clock import Window
from contracts.taxonomy import Metric, MomentType
from detector.cusum import SeriesState, Watch, detect, step
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
RISE = Watch(MomentType.PRESSURE_SHIFT, Metric.PRESSURE_RATE, 5, k=0.25, h=0.5, min_n=8)


def _run(watch, changes):
    state = SeriesState()
    return [step(state, watch, c) for c in changes]


def test_a_series_fires_once_its_change_beyond_the_allowance_adds_up():
    assert _run(RISE, [0.25, 0.5, 0.5]) == [False, False, True]  # 0 + 0.25 + 0.25
    assert _run(RISE, [0.75]) == [True]  # one large step
    assert not any(_run(RISE, [0.24] * 30))  # within the allowance, never


def test_it_watches_both_ways_unless_told_and_re_arms_only_after_settling():
    assert _run(RISE, [-1.0]) == [True]
    falls = Watch(MomentType.FATIGUE_SIGNAL, Metric.SPRINT_COUNT, 10, 0.25, 0.5, 0, ways=(-1,))
    assert _run(falls, [1.0, -1.0]) == [False, True]
    # After firing it stays quiet while the change persists, and fires again only after it
    # has fallen back within the allowance.
    assert _run(RISE, [1.0, 1.0, 1.0, 0.0, 1.0]) == [True, False, False, False, True]


def test_the_demo_press_opens_a_case_at_63_minutes():
    sim = MatchSim(load_script(M01))
    cases = detect(match_meta(sim), sim.run())
    press = [c for c in cases if c.window == Window.model_validate("58:00-63:00")]
    assert len(press) == 1 and press[0].moment_type == MomentType.PRESSURE_SHIFT
    (trigger,) = press[0].triggers
    assert (trigger.metric, trigger.subject, trigger.n_events) == (
        Metric.PRESSURE_RATE,
        "Harbour City",
        18,
    )
    assert round(trigger.baseline_value, 2) == 0.32 and round(trigger.value, 2) == 0.83
    assert all(c.window.start.period == 2 for c in cases)  # the first half is the baseline


def test_a_flank_shown_wrongly_opens_a_case_that_its_correction_takes_away(tmp_path):
    from engine.io import write_match
    from tools_server.server import DirectorySource

    sim = MatchSim(load_script(M01))
    write_match(sim, sim.run(), tmp_path / "m01")
    source = DirectorySource(tmp_path)
    shown = source.feed("m01")
    fixed = shown.amended(source.amendments("m01")[0])
    (flank,) = [c for c in detect(shown.meta, shown.events) if c.moment_type == "shape_change"]
    assert flank.case_id == "case-m01-058-shape_change" and str(flank.window) == "48:00-58:00"
    (trigger,) = flank.triggers
    assert (trigger.metric, trigger.subject, round(trigger.value, 3)) == (
        "channel_share_right",
        "Northvale",
        0.636,
    )
    assert not [c for c in detect(fixed.meta, fixed.events) if c.moment_type == "shape_change"]
