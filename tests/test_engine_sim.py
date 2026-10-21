from pathlib import Path

from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)


def _dump(events):
    return [e.model_dump_json() for e in events]


def test_same_script_and_seed_is_deterministic():
    assert _dump(MatchSim(M01, seed=3).run()) == _dump(MatchSim(M01, seed=3).run())


def test_seed_changes_the_match():
    assert _dump(MatchSim(M01, seed=3).run()) != _dump(MatchSim(M01, seed=4).run())


def test_events_are_ordered_with_sequential_ids():
    events = MatchSim(M01, seed=3).run()
    assert [e.event_id for e in events] == [f"m01-{i:05d}" for i in range(1, len(events) + 1)]
    keys = [e.clock.sort_key for e in events]
    assert keys == sorted(keys)


def test_two_periods_with_stoppage_time():
    events = MatchSim(M01, seed=3).run()
    markers = [e.type for e in events if e.type in ("period_start", "period_end")]
    assert markers == ["period_start", "period_end", "period_start", "period_end"]
    assert any(e.clock.period == 1 and e.clock.stoppage for e in events)


def test_every_player_is_on_a_roster():
    sim = MatchSim(M01, seed=3)
    events = sim.run()
    roster = {p.player_id for side in sim.lineups.values() for p in side}
    assert {e.player_id for e in events if e.player_id} <= roster
    assert {e.team for e in events} == {"Harbour City", "Northvale"}


def test_intervention_leaves_the_match_before_it_untouched():
    without_s1 = M01.model_copy(update={"scripts": [s for s in M01.scripts if s.id != "s1"]})

    def before_60(events):
        return _dump([e for e in events if e.clock.minute < 60])

    assert before_60(MatchSim(M01, seed=3).run()) == before_60(MatchSim(without_s1, seed=3).run())
