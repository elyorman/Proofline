import pytest
from pydantic import ValidationError

from contracts import (
    Cause,
    Event,
    InsightCard,
    LanguageLevel,
    Profile,
    SupportLevel,
)
from contracts.card import (
    AttributionProposition,
    ChangeProposition,
    DependsOn,
    Provenance,
    Subject,
    Timing,
    Verification,
)
from contracts.event import EventType, MatchClock, Outcome, PassQualifiers, Point
from contracts.prediction import Direction, Window
from contracts.profile import Expertise
from contracts.taxonomy import BaselineScope, Metric, MomentType


def test_match_clock_round_trips_second_half():
    clock = MatchClock.parse("63:12")
    assert clock.period == 2
    assert clock.minute == 63
    assert str(clock) == "63:12"


def test_pass_requires_qualifiers():
    with pytest.raises(ValidationError):
        Event(
            event_id="e1",
            match_id="m01",
            clock=MatchClock.parse("10:00"),
            wall_clock_ms=0,
            type=EventType.PASS,
            team="Harbour City",
        )


def test_pass_event_validates():
    event = Event(
        event_id="e1",
        match_id="m01",
        clock=MatchClock.parse("10:00"),
        wall_clock_ms=0,
        type=EventType.PASS,
        team="Harbour City",
        player_id="HC-08",
        start=Point(x=30, y=34),
        end=Point(x=62, y=20),
        outcome=Outcome.COMPLETE,
        pass_q=PassQualifiers(
            distance_m=35.0, ball_speed_kmh=58.0, pressure_on_passer=0.3, receiver_id="HC-11"
        ),
    )
    assert event.version == 1


def test_language_level_derives_from_support():
    v = Verification(
        status="passed",
        recompute="match",
        baseline_check="passed",
        sample_size_check="passed",
        contradiction_check="passed",
        semantic_check="passed",
        verifier_model_family="family-b",
        support_level=SupportLevel.MODERATE,
    )
    assert v.language_level == LanguageLevel.MEASURED


def test_language_level_cannot_contradict_support():
    with pytest.raises(ValidationError):
        Verification(
            status="passed",
            recompute="match",
            baseline_check="passed",
            sample_size_check="passed",
            contradiction_check="passed",
            semantic_check="passed",
            verifier_model_family="family-b",
            support_level=SupportLevel.WEAK,
            language_level=LanguageLevel.ASSERTIVE,
        )


def _card(propositions):
    return InsightCard(
        id="ins-m01-063-01",
        match_id="m01",
        case_id="case-063-pressure",
        moment_type=MomentType.PRESSURE_SHIFT,
        subject=Subject(team="Harbour City"),
        timing=Timing(change_window=Window(start="58:00", end="63:00"), detected_at="63:12"),
        propositions=propositions,
        claim="Harbour City have raised their press since around the hour.",
        depends_on=DependsOn(evidence_sets=["es-tc-8841"], data_version="feed-1"),
        provenance=Provenance(trace_id="otel-5f2c"),
    )


def test_attribution_must_reference_a_change_proposition():
    change = ChangeProposition(
        id="p1",
        metric=Metric.PPDA,
        subject="Harbour City",
        direction=Direction.DOWN,
        window=Window(start="58:00", end="63:00"),
        baseline=BaselineScope.FIRST_HALF,
    )
    ok = AttributionProposition(
        id="p3", cause=Cause.PRESS_INTENSITY_UP, effect="p1", role="primary"
    )
    assert _card([change, ok]).revision == 1

    bad = AttributionProposition(
        id="p3", cause=Cause.PRESS_INTENSITY_UP, effect="p9", role="primary"
    )
    with pytest.raises(ValidationError):
        _card([change, bad])


def test_profile_budget_defaults_by_expertise():
    assert Profile(profile_id="a", expertise=Expertise.CASUAL).budget == 3
    assert Profile(profile_id="b", expertise=Expertise.CORE).budget == 6
    assert Profile(profile_id="c", attention_budget_per_half=1).budget == 1


def test_cause_domains():
    assert Cause.PRESS_INTENSITY_UP.domain == "tactical"
    assert Cause.OTHER.domain == "fallback"
