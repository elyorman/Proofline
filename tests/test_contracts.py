import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import (
    Case,
    CaseOutcome,
    Cause,
    Cue,
    DependencyEntry,
    EvalRun,
    Event,
    EventAmendment,
    Hypothesis,
    InsightCard,
    LanguageLevel,
    MatchClock,
    Prediction,
    Profile,
    SupportLevel,
    ThresholdKind,
    ToolResult,
    Window,
)
from contracts.card import (
    AttributionProposition,
    BroadcastCueSpec,
    ChangeProposition,
    CheckResult,
    DependsOn,
    Provenance,
    Subject,
    Timing,
    Verification,
)
from contracts.case import CaseStage, Checkpoint, TriggerMetric
from contracts.cue import ShowAt
from contracts.eval_run import MetricEstimate, Split, Suite, Variant, VariantComparison
from contracts.event import CoordinateShift, EventType, Outcome, PassQualifiers, Point
from contracts.prediction import Direction
from contracts.profile import Expertise
from contracts.taxonomy import AgentRole, BaselineScope, Metric, MomentType, OverlayTemplate

SPEC = Path(__file__).resolve().parents[1] / "docs" / "spec.md"

# --- clock and window -------------------------------------------------------


@pytest.mark.parametrize(
    "text,period,minute,second",
    [
        ("12:30", 1, 12, 30),
        ("45+2:10", 1, 47, 10),
        ("63:12", 2, 63, 12),
        ("90+3:05", 2, 93, 5),
    ],
)
def test_clock_parse_and_print_round_trip(text, period, minute, second):
    clock = MatchClock.parse(text)
    assert (clock.period, clock.minute, clock.second) == (period, minute, second)
    assert str(clock) == text


def test_first_half_stoppage_and_second_half_differ():
    first = MatchClock.parse("45+2:10")
    second = MatchClock.parse("47:10")
    assert first != second
    assert first < second
    assert str(first) != str(second)


def test_clock_accepts_text_in_models():
    assert MatchClock.model_validate("63:12").period == 2


def test_clock_rejects_bad_minutes():
    with pytest.raises(ValidationError):
        MatchClock(period=2, minute=30, second=0)
    with pytest.raises(ValueError):
        MatchClock.parse("58:99")


def test_window_orders_and_parses():
    w = Window.model_validate("58:00-63:00")
    assert str(w) == "58:00-63:00"
    assert w.contains(MatchClock.parse("60:00"))
    assert not w.contains(MatchClock.parse("63:00"))
    with pytest.raises(ValidationError):
        Window.model_validate("63:00-58:00")
    with pytest.raises(ValidationError):
        Window.model_validate("58:00-58:99")


# --- events -----------------------------------------------------------------


def test_pass_requires_qualifiers():
    with pytest.raises(ValidationError):
        Event(
            event_id="e1",
            match_id="m01",
            clock="10:00",
            wall_clock_ms=0,
            type=EventType.PASS,
            team="Harbour City",
        )


def test_pass_event_validates():
    event = Event(
        event_id="e1",
        match_id="m01",
        clock="10:00",
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


def test_amendment_needs_exactly_one_change():
    base = dict(amendment_id="a1", match_id="m01", at="68:00", event_ids=["e1"], reason="re-sync")
    assert EventAmendment(**base, shift=CoordinateShift(dy_m=-18)).shift is not None
    with pytest.raises(ValidationError):
        EventAmendment(**base)
    with pytest.raises(ValidationError):
        EventAmendment(**base, shift=CoordinateShift(dy_m=-18), set={"team": "Northvale"})


# --- predictions ------------------------------------------------------------


def test_prediction_defaults_threshold_kind_per_metric():
    momentum = Prediction(
        metric=Metric.MOMENTUM,
        subject="Northvale",
        window="58:00-63:00",
        compare_to=BaselineScope.FIRST_HALF,
        direction=Direction.DOWN,
        min_change=1.5,
    )
    assert momentum.threshold_kind == ThresholdKind.SIGMA
    ppda = Prediction(
        metric=Metric.PPDA,
        subject="Harbour City",
        window="58:00-63:00",
        compare_to=BaselineScope.FIRST_HALF,
        direction=Direction.DOWN,
        min_change=0.3,
    )
    assert ppda.threshold_kind == ThresholdKind.RELATIVE


def _prediction(**overrides):
    base = dict(
        metric=Metric.PPDA,
        subject="Harbour City",
        window="58:00-63:00",
        compare_to=BaselineScope.FIRST_HALF,
        direction=Direction.DOWN,
        min_change=0.3,
    )
    base.update(overrides)
    return Prediction(**base)


def test_relative_threshold_only_on_metrics_pinned_relative():
    with pytest.raises(ValidationError):
        _prediction(metric=Metric.MOMENTUM, threshold_kind=ThresholdKind.RELATIVE)
    assert _prediction(threshold_kind=ThresholdKind.SIGMA).threshold_kind == ThresholdKind.SIGMA


def test_prediction_is_judged_on_signed_change():
    ppda_down = _prediction()
    assert ppda_down.supported_by(-0.46)
    assert not ppda_down.supported_by(0.4)  # large change, wrong direction
    assert not ppda_down.supported_by(-0.1)  # right direction, too small


def _hypothesis(agent, cause):
    sprints = _prediction(metric=Metric.SPRINT_COUNT, subject="Northvale", min_change=0.15)
    return Hypothesis(
        hypothesis_id="hyp-1", case_id="case-063", agent=agent, taxonomy=cause, prediction=sprints
    )


def test_agents_register_only_causes_in_their_own_domain():
    assert _hypothesis(AgentRole.PHYSICAL, Cause.UNIT_FATIGUE).agent == AgentRole.PHYSICAL
    with pytest.raises(ValidationError):
        _hypothesis(AgentRole.TACTICS, Cause.UNIT_FATIGUE)


def test_synthesis_cannot_register_hypotheses():
    with pytest.raises(ValidationError):
        _hypothesis(AgentRole.SYNTHESIS, Cause.UNIT_FATIGUE)


def test_other_and_none_are_outcomes_not_hypotheses():
    with pytest.raises(ValidationError):
        _hypothesis(AgentRole.TACTICS, Cause.NONE)


def test_single_agent_baseline_registers_any_domain():
    assert _hypothesis(AgentRole.SINGLE, Cause.UNIT_FATIGUE).agent == AgentRole.SINGLE
    assert _hypothesis(AgentRole.SINGLE, Cause.PRESS_INTENSITY_UP).agent == AgentRole.SINGLE


# --- tool results -----------------------------------------------------------


def _tool_result(tool, **fields):
    return ToolResult(
        tool_call_id="tc-1",
        tool=tool,
        match_id="m01",
        n_events=41,
        evidence_set_id="es-tc-1",
        computed_at_ms=0,
        **fields,
    )


def test_compare_result_carries_both_windows_and_effect_size():
    result = _tool_result(
        "compare",
        metric=Metric.PPDA,
        subject="Harbour City",
        window="58:00-63:00",
        value=6.1,
        compared_with={"window": "50:00-55:00", "value": 10.8, "n_events": 37},
        effect_size=-1.4,
    )
    assert result.compared_with.window.start == MatchClock.parse("50:00")


def test_multi_valued_and_instant_tools_fit():
    load = _tool_result(
        "player_load",
        subject="NV-03",
        window="58:00-63:00",
        values={"sprints": 4, "high_intensity_runs": 9, "distance_m": 612.0},
    )
    state = _tool_result("game_state", at="63:12", values={"home_goals": 1, "away_goals": 0})
    assert load.values["sprints"] == 4
    assert state.subject is None


def test_tool_result_requires_the_fields_its_tool_returns():
    with pytest.raises(ValidationError):
        _tool_result(
            "compare", metric=Metric.PPDA, subject="Harbour City", window="58:00-63:00", value=6.1
        )


def test_tool_name_is_from_the_catalog():
    with pytest.raises(ValidationError):
        _tool_result(
            "metrc", metric=Metric.PPDA, subject="Harbour City", window="58:00-63:00", value=6.1
        )


def test_dependency_ids_are_unique_across_matches():
    first = DependencyEntry(event_id="e1", match_id="m01")
    second = DependencyEntry(event_id="e1", match_id="m02")
    assert first.id != second.id
    assert first.model_dump()["id"] == "m01:e1"


# --- verification -----------------------------------------------------------


def _verification(**overrides):
    base = dict(
        status="passed",
        recompute="match",
        baseline_check=CheckResult.PASSED,
        sample_size_check=CheckResult.PASSED,
        contradiction_check=CheckResult.PASSED,
        number_check=CheckResult.PASSED,
        semantic_check=CheckResult.PASSED,
        verifier_model_family="family-b",
        support_level=SupportLevel.MODERATE,
    )
    base.update(overrides)
    return Verification(**base)


def test_language_level_derives_from_support():
    assert _verification().language_level == LanguageLevel.MEASURED


def test_passed_requires_every_check_passed():
    with pytest.raises(ValidationError):
        _verification(recompute="mismatch")
    with pytest.raises(ValidationError):
        _verification(number_check=CheckResult.FAILED)


def test_rejected_requires_reason_and_no_support():
    with pytest.raises(ValidationError):
        _verification(status="rejected", support_level=None)
    v = _verification(
        status="rejected",
        support_level=None,
        number_check=CheckResult.FAILED,
        rejection_reason="48% in the Spanish variant does not match evidence 0.48",
    )
    assert v.language_level is None


def test_language_level_cannot_contradict_support():
    with pytest.raises(ValidationError):
        _verification(support_level=SupportLevel.WEAK, language_level=LanguageLevel.ASSERTIVE)


def test_corrected_cannot_skip_checks():
    skipped = {
        name: CheckResult.SKIPPED
        for name in (
            "baseline_check",
            "sample_size_check",
            "contradiction_check",
            "number_check",
            "semantic_check",
        )
    }
    with pytest.raises(ValidationError):
        _verification(status="corrected", **skipped)
    with pytest.raises(ValidationError):
        _verification(
            status="corrected",
            number_check=CheckResult.SKIPPED,
            semantic_check=CheckResult.CORRECTED,
        )


def test_corrected_needs_a_corrected_check():
    with pytest.raises(ValidationError):
        _verification(status="corrected")
    fixed = _verification(status="corrected", number_check=CheckResult.CORRECTED)
    assert fixed.status == "corrected"


# --- cards ------------------------------------------------------------------

CHANGE = ChangeProposition(
    id="p1",
    metric=Metric.PPDA,
    subject="Harbour City",
    direction=Direction.DOWN,
    window="58:00-63:00",
    baseline=BaselineScope.FIRST_HALF,
)


def _attr(cause, effect="p1", role="primary"):
    return AttributionProposition(
        id="p3",
        cause=cause,
        effect=effect,
        role=role,
        hypothesis_id="hyp-1",
        agent=AgentRole.TACTICS,
    )


def _card(propositions, outcome=CaseOutcome.EXPLAINED):
    return InsightCard(
        id="ins-m01-063-01",
        match_id="m01",
        case_id="case-063-pressure",
        case_outcome=outcome,
        moment_type=MomentType.PRESSURE_SHIFT,
        subject=Subject(team="Harbour City"),
        timing=Timing(change_window="58:00-63:00", detected_at="63:12"),
        propositions=propositions,
        claim="Harbour City have raised their press since around the hour.",
        depends_on=DependsOn(evidence_sets=["es-tc-8841"], data_version="feed-1"),
        provenance=Provenance(trace_id="otel-5f2c"),
    )


def test_primary_cause_lives_in_propositions():
    card = _card([CHANGE, _attr(Cause.PRESS_INTENSITY_UP)])
    assert card.primary_cause.cause == Cause.PRESS_INTENSITY_UP


def test_attribution_must_reference_a_change_proposition():
    with pytest.raises(ValidationError):
        _card([CHANGE, _attr(Cause.PRESS_INTENSITY_UP, effect="p9")])


def test_outcome_none_carries_no_attribution():
    none_card = _card([CHANGE], outcome=CaseOutcome.NONE)
    assert none_card.primary_cause is None
    with pytest.raises(ValidationError):
        _card([CHANGE, _attr(Cause.PRESS_INTENSITY_UP)], outcome=CaseOutcome.NONE)


def test_outcome_explained_needs_taxonomy_cause():
    with pytest.raises(ValidationError):
        _card([CHANGE], outcome=CaseOutcome.EXPLAINED)
    with pytest.raises(ValidationError):
        _card([CHANGE, _attr(Cause.OTHER)], outcome=CaseOutcome.EXPLAINED)
    assert _card([CHANGE, _attr(Cause.OTHER)], outcome=CaseOutcome.OTHER).case_outcome == "other"


def test_cue_template_is_an_enum_everywhere():
    spec = BroadcastCueSpec(template=OverlayTemplate.PRESSURE_SHIFT_BAR, fields={"team": "x"})
    assert spec.template == "pressure_shift_bar"
    with pytest.raises(ValidationError):
        BroadcastCueSpec(template="presure_shift_bar", fields={})


def test_cue_slot_cannot_close_before_it_opens():
    assert ShowAt(mode="immediate", not_before="63:40", not_after="63:40").mode == "immediate"
    with pytest.raises(ValidationError):
        ShowAt(mode="next_dead_ball", not_before="64:25", not_after="63:40")


def _spec_example(heading):
    text = SPEC.read_text(encoding="utf-8")
    return re.search(re.escape(heading) + r".*?```json\n(.*?)```", text, re.S).group(1)


@pytest.mark.parametrize(
    "heading,model",
    [
        ("## 5. Insight Card", InsightCard),
        ("### 12.3 Broadcast Cue Feed", Cue),
        ("## 13. Personalization model", Profile),
    ],
)
def test_spec_examples_validate(heading, model):
    model.model_validate_json(_spec_example(heading))


# --- case, eval run, profile ------------------------------------------------


def test_case_checkpoints_in_order_and_budget():
    trigger = TriggerMetric(
        metric=Metric.PPDA, subject="Harbour City", value=6.1, baseline_value=11.4, n_events=41
    )
    case = Case(
        case_id="case-063",
        match_id="m01",
        moment_type=MomentType.PRESSURE_SHIFT,
        window="58:00-63:00",
        triggers=[trigger],
        checkpoints=[
            Checkpoint(stage=CaseStage.OPEN, wall_clock_ms=1),
            Checkpoint(stage=CaseStage.PREREGISTERED, wall_clock_ms=2),
        ],
        tool_calls_used=11,
    )
    assert case.stage == CaseStage.OPEN
    with pytest.raises(ValidationError):
        Case(
            case_id="c",
            match_id="m01",
            moment_type=MomentType.PRESSURE_SHIFT,
            window="58:00-63:00",
            triggers=[trigger],
            checkpoints=[
                Checkpoint(stage=CaseStage.TESTED, wall_clock_ms=1),
                Checkpoint(stage=CaseStage.OPEN, wall_clock_ms=2),
            ],
        )
    with pytest.raises(ValidationError):
        Case(
            case_id="c",
            match_id="m01",
            moment_type=MomentType.PRESSURE_SHIFT,
            window="58:00-63:00",
            triggers=[trigger],
            tool_calls_used=17,
        )


def _estimate(**overrides):
    base = dict(
        name="planted_recall", suite=Suite.PLANTED, value=0.8, ci_low=0.7, ci_high=0.9, n=40
    )
    base.update(overrides)
    return MetricEstimate(**base)


def _eval_run(metrics):
    return EvalRun(
        run_id="r1",
        variant=Variant.A_PROOFLINE,
        suites=[Suite.PLANTED],
        split=Split.HELDOUT,
        model_tier="final",
        match_ids=["m01"],
        metrics=metrics,
        started_at_ms=0,
        finished_at_ms=10,
    )


def test_eval_run_ci_contains_estimate():
    assert _eval_run([_estimate()]).metrics[0].n == 40
    with pytest.raises(ValidationError):
        _estimate(value=0.95)


def test_eval_metric_belongs_to_a_suite_the_run_covered():
    with pytest.raises(ValidationError):
        _eval_run([_estimate(name="decoy_restraint", suite=Suite.DECOYS)])


def _comparison(variant_b):
    return VariantComparison(
        comparison_id="cmp-1",
        run_a="r-a",
        run_b="r-b",
        variant_a=Variant.A_PROOFLINE,
        variant_b=variant_b,
        split=Split.HELDOUT,
        difference=_estimate(value=0.12, ci_low=0.03, ci_high=0.21),
    )


def test_variant_comparison_is_a_paired_difference_of_two_variants():
    assert _comparison(Variant.B_SINGLE_AGENT).difference.value == 0.12
    with pytest.raises(ValidationError):
        _comparison(Variant.A_PROOFLINE)


def test_profile_budget_defaults_by_expertise():
    assert Profile(profile_id="a", expertise=Expertise.CASUAL).budget == 3
    assert Profile(profile_id="b", expertise=Expertise.CORE).budget == 6
    assert Profile(profile_id="c", attention_budget_per_half=1).budget == 1


def test_cause_domains():
    assert Cause.PRESS_INTENSITY_UP.domain == "tactical"
    assert Cause.OTHER.domain == "fallback"
