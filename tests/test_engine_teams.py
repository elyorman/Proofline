from engine.script import TeamSpec
from engine.teams import FORMATIONS, build_lineup, position

NORTHVALE = TeamSpec(name="Northvale", code="NV", formation="4-2-3-1")


def test_every_formation_fields_eleven_with_one_keeper():
    for roles in FORMATIONS.values():
        assert len(roles) == 11
        assert [r for r, _, _ in roles].count("GK") == 1


def test_lineup_ids_names_and_units():
    lineup = build_lineup(NORTHVALE)
    assert [p.player_id for p in lineup][:3] == ["NV-01", "NV-02", "NV-03"]
    assert lineup[2].role == "RCB" and lineup[2].unit == "defence"
    assert all(p.name for p in lineup)


def test_a_higher_press_pushes_the_defensive_block_up():
    rcb = build_lineup(NORTHVALE)[2]
    low, _ = position(rcb, attacking=False, press_height=0.3, ball=(50, 34))
    high, _ = position(rcb, attacking=False, press_height=0.8, ball=(50, 34))
    assert high > low


def test_positions_stay_on_the_pitch():
    for p in build_lineup(NORTHVALE):
        for attacking in (True, False):
            x, y = position(p, attacking=attacking, press_height=1.0, ball=(100, 68))
            assert 0 <= x <= 105 and 0 <= y <= 68
