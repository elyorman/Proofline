import pytest

from engine.rng import Streams


def test_same_seed_gives_same_draws():
    a, b = Streams(7), Streams(7)
    draws = [a.uniform("pass_length", 61) for _ in range(5)]
    assert draws == [b.uniform("pass_length", 61) for _ in range(5)]
    assert len(set(draws)) == 5  # each draw advances the stream


def test_extra_draws_do_not_shift_other_minutes_or_decisions():
    plain, busy = Streams(7), Streams(7)
    for _ in range(50):  # e.g. an intervention adds passes in minute 61
        busy.uniform("pass_length", 61)
    assert busy.uniform("pass_length", 61) != plain.uniform("pass_length", 61)
    assert plain.uniform("pass_length", 62) == busy.uniform("pass_length", 62)
    assert plain.uniform("shot_outcome", 61) == busy.uniform("shot_outcome", 61)


def test_different_seeds_differ():
    assert Streams(1).uniform("pass_length", 10) != Streams(2).uniform("pass_length", 10)


def test_draws_are_pinned_across_processes():
    # Changing this value changes every generated match, suite and released dataset.
    assert Streams(4417).uniform("pass_dist", 61, 6, 24) == pytest.approx(14.308525307278389)


def test_minutes_must_be_integers():
    with pytest.raises(TypeError):
        Streams(1).uniform("pass_length", 61.0)
