import re
from typing import get_args

from engine.script import PLAYER_ID, TeamSpec
from engine.teams import FORMATIONS, build_lineup, position

NORTHVALE = TeamSpec(name="Northvale", code="NV", formation="4-2-3-1")


def _lineup(formation):
    return build_lineup(TeamSpec(name="Test", code="XX", formation=formation))


def test_script_formations_match_the_engine():
    assert set(get_args(TeamSpec.model_fields["formation"].annotation)) == set(FORMATIONS)


def test_every_formation_builds_eleven_valid_starters():
    for formation in FORMATIONS:
        lineup = _lineup(formation)
        assert [p.player_id for p in lineup] == [f"XX-{i:02d}" for i in range(1, 12)]
        assert all(re.match(PLAYER_ID, p.player_id) for p in lineup)
        assert [p.role for p in lineup].count("GK") == 1


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


def test_attacking_pushes_the_line_up_ten_metres():
    rcb = build_lineup(NORTHVALE)[2]
    x, _ = position(rcb, attacking=True, press_height=0.5, ball=(50, 34))
    assert x == rcb.base_x + 10


def test_players_shift_towards_the_ball():
    rb = build_lineup(NORTHVALE)[1]
    _, towards_right = position(rb, attacking=False, press_height=0.5, ball=(50, 68))
    _, towards_left = position(rb, attacking=False, press_height=0.5, ball=(50, 0))
    assert towards_left < rb.base_y < towards_right


def test_positions_stay_on_the_pitch():
    for formation in FORMATIONS:  # 4-3-3 wingers and 3-5-2 wing-backs need the clamp
        for p in _lineup(formation):
            for attacking in (True, False):
                for press in (0.0, 1.0):
                    for ball_y in (0.0, 68.0):
                        x, y = position(
                            p, attacking=attacking, press_height=press, ball=(50, ball_y)
                        )
                        assert 0 <= x <= 105 and 0 <= y <= 68
