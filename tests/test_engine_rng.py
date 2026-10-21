from engine.rng import Streams


def test_same_seed_gives_same_draws():
    a, b = Streams(7), Streams(7)
    assert [a.uniform("pass_length", 61) for _ in range(5)] == [
        b.uniform("pass_length", 61) for _ in range(5)
    ]


def test_extra_draws_do_not_shift_other_minutes_or_decisions():
    plain, busy = Streams(7), Streams(7)
    for _ in range(50):  # e.g. an intervention adds passes in minute 61
        busy.uniform("pass_length", 61)
    assert plain.uniform("pass_length", 62) == busy.uniform("pass_length", 62)
    assert plain.uniform("shot_outcome", 61) == busy.uniform("shot_outcome", 61)


def test_different_seeds_differ():
    assert Streams(1).uniform("pass_length", 10) != Streams(2).uniform("pass_length", 10)
