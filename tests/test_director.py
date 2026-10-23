"""The Director on the demo match: who sees which revision when, and the broadcast cues.
Deterministic; cards are built by the scripted pipeline in tests/test_corrections.py."""

import asyncio

from test_corrections import PRESS, Scripted, _flank, _published, m01  # noqa: F401

from agents.director import direct, goals
from contracts.profile import Profile
from contracts.taxonomy import CardStatus
from corrections.watcher import correct

FAN = Profile(profile_id="demo", expertise="core", language="es", favorite_club="Northvale")


def test_goals_take_the_fast_lane_with_the_running_score(m01):  # noqa: F811
    shown, _ = m01
    cards = goals(shown.meta, shown.events)
    assert [str(c.timing.published_at) for c in cards] == [
        "00:55",
        "12:30",
        "26:51",
        "52:54",
        "77:09",
    ]
    assert (
        cards[-1].variants["casual"]["es"] == "¡Gol del Harbour City! Harbour City 2-3 Northvale."
    )
    assert all(c.lane == "fast" and not c.attributions for c in cards)


def test_a_withdrawal_reaches_the_fan_who_saw_the_card_and_waits_for_the_producer(m01):  # noqa: F811
    shown, a1 = m01
    flank, press = _published(shown, 58, _flank(0.2)), _published(shown, 63, PRESS)
    withdrawn = asyncio.run(correct(Scripted(), flank, shown.amended(a1), a1)).card
    schedule = direct([flank.card, press.card, withdrawn], shown.events, shown.meta, FAN)
    insight = [c for c in schedule.cards if c.lane == "full"]
    assert [(c.case_id, c.revision, c.status, str(c.timing.published_at)) for c in insight] == [
        ("case-m01-058-shape_change", 1, CardStatus.SHOWN, "58:00"),
        ("case-m01-063-pressure_shift", 1, CardStatus.SHOWN, "63:00"),
        ("case-m01-058-shape_change", 2, CardStatus.WITHDRAWN, "68:00"),
    ]
    by_kind = {c.kind: c for c in schedule.cues}
    assert by_kind["insight"].status in ("approved", "expired")
    withdrawal = by_kind["withdrawal"]
    assert withdrawal.template == "withdrawal_banner" and withdrawal.status == "pending"
    assert withdrawal.fields["headline"] == "WITHDRAWN"
    press_cue = next(c for c in schedule.cues if c.insight_id == press.card.id)
    assert press_cue.fields["headline"] == "PRESS RAISED" and press_cue.fields["after"] > 0.8


def test_a_card_beyond_the_budget_or_below_the_viewers_language_waits_for_the_recap(m01):  # noqa: F811
    shown, _ = m01
    press = _published(shown, 63, PRESS)
    none_left = FAN.model_copy(update={"attention_budget_per_half": 0})
    (late,) = [
        c
        for c in direct([press.card], shown.events, shown.meta, none_left).cards
        if c.lane == "full"
    ]
    assert late.status == CardStatus.EXPIRED and late.timing.published_at is None
    sure_only = FAN.model_copy(update={"min_language_level": "assertive"})
    level = press.card.verification.language_level
    (seen,) = [
        c
        for c in direct([press.card], shown.events, shown.meta, sure_only).cards
        if c.lane == "full"
    ]
    assert seen.status == (CardStatus.SHOWN if level == "assertive" else CardStatus.EXPIRED)
