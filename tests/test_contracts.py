import json
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
from contracts.prediction import (
    CrossExamination,
    Direction,
    HypothesisTest,
    check_counter_test,
)
from contracts.profile import Expertise
from contracts.taxonomy import (
    DEFAULT_THRESHOLD_KIND,
    AgentRole,
    BaselineScope,
    Metric,
    MomentType,
    OverlayTemplate,
)

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


def test_every_metric_has_a_pinned_threshold_kind():
    assert set(DEFAULT_THRESHOLD_KIND) == set(Metric)
    assert DEFAULT_THRESHOLD_KIND[Metric.PRESSURE_RATE] == ThresholdKind.ABSOLUTE
    assert DEFAULT_THRESHOLD_KIND[Metric.CHANNEL_SHARE_RIGHT] == ThresholdKind.ABSOLUTE


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


def test_a_flat_prediction_holds_within_its_tolerance():
    flat = _prediction(metric=Metric.SPRINT_COUNT, direction=Direction.FLAT, min_change=0.1)
    assert flat.supported_by(0.08) and flat.supported_by(-0.1)
    assert not flat.supported_by(0.15)
    with pytest.raises(ValueError, match="share must be"):
        flat.supported_by(0.0, share=0)


def _cross_examination(observed_change):
    sprints_flat = _prediction(
        metric=Metric.SPRINT_COUNT, subject="Northvale", direction=Direction.FLAT, min_change=0.1
    )
    return CrossExamination(
        hypothesis_id="hyp-physical-01",
        challenger=AgentRole.TACTICS,
        counter_prediction=sprints_flat,
        tool_call_id="tc-8850",
        observed_change=observed_change,
        reason="sprints compared with the season average for the same minutes",
    )


def test_cross_examination_is_scored_by_its_counter_test():
    assert _cross_examination(-0.05).result == "refuted"  # the counter-prediction holds
    assert _cross_examination(-0.15).result == "weakened"  # within twice the tolerance
    assert _cross_examination(-0.30).result == "holds"
    assert _cross_examination(-0.05).model_dump()["result"] == "refuted"


def test_an_up_or_down_counter_test_is_scored_against_its_threshold():
    fell_too = _prediction(metric=Metric.SPRINT_COUNT, subject="Harbour City", min_change=0.15)

    def result(observed):
        return CrossExamination(
            hypothesis_id="hyp-physical-01",
            challenger=AgentRole.TACTICS,
            counter_prediction=fell_too,
            tool_call_id="tc-8850",
            observed_change=observed,
            reason="Harbour City's sprints fell too",
        ).result

    scored = {x: result(x) for x in (-0.25, -0.15, -0.10, -0.075, -0.05, 0.30)}
    assert scored == {
        -0.25: "refuted",
        -0.15: "refuted",  # exactly the threshold
        -0.10: "weakened",
        -0.075: "weakened",  # exactly half of it
        -0.05: "holds",
        0.30: "holds",
    }


def test_a_stored_cross_examination_round_trips_and_cannot_be_rewritten():
    exam = _cross_examination(-0.05)
    assert CrossExamination.model_validate_json(exam.model_dump_json()) == exam
    with pytest.raises(ValidationError, match="disagrees with the counter-test"):
        CrossExamination.model_validate(dict(exam.model_dump(), result="holds"))


def test_counter_tests_need_a_domain_challenger_and_a_finite_change():
    stored = _cross_examination(-0.05).model_dump(exclude={"result"})
    with pytest.raises(ValidationError, match="does not cross-examine"):
        CrossExamination.model_validate(dict(stored, challenger="synthesis"))
    for broken in (float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            CrossExamination.model_validate(dict(stored, observed_change=broken))
        with pytest.raises(ValidationError):
            HypothesisTest(
                hypothesis_id="hyp-1",
                tool_call_id="tc-1",
                observed_change=broken,
                outcome="supported",
                reason="r",
            )


def test_a_hypothesis_predicts_a_change():
    flat = _prediction(
        metric=Metric.SPRINT_COUNT, subject="Northvale", direction=Direction.FLAT, min_change=0.15
    )
    with pytest.raises(ValidationError, match="flat is for counter-tests"):
        Hypothesis(
            hypothesis_id="hyp-1",
            case_id="case-063",
            agent=AgentRole.PHYSICAL,
            taxonomy=Cause.UNIT_FATIGUE,
            prediction=flat,
        )


def _hypothesis(agent, cause):
    sprints = _prediction(metric=Metric.SPRINT_COUNT, subject="Northvale", min_change=0.15)
    return Hypothesis(
        hypothesis_id="hyp-1", case_id="case-063", agent=agent, taxonomy=cause, prediction=sprints
    )


@pytest.mark.parametrize(
    "counter,fair",
    [
        # The demo's counter: Harbour City's sprints fell too (a control).
        (dict(subject="Harbour City"), True),
        # Northvale's sprints are normal for these minutes (flat against another baseline).
        (dict(compare_to=BaselineScope.SEASON_AVERAGE, direction="flat", min_change=0.1), True),
        (dict(compare_to=BaselineScope.SEASON_AVERAGE, direction="up"), True),
        # Restatements of the hypothesis's own signal.
        (dict(), False),
        (dict(compare_to=BaselineScope.MATCH_SO_FAR, min_change=0.001), False),
        (dict(window="57:00-63:00", min_change=0.001), False),
        (dict(subject="Northvale.defence"), False),
        # Controls that are trivially easy, or flat tolerances that swallow the claim.
        (dict(subject="Harbour City", min_change=0.001), False),
        (dict(subject="Harbour City", direction="flat", min_change=0.149), False),
        (dict(window="00:00-05:00", direction="flat", min_change=0.149), False),
        (dict(direction="flat", min_change=0.149), False),
        (dict(compare_to=BaselineScope.SEASON_AVERAGE, direction="flat", min_change=0.2), False),
        (
            dict(threshold_kind=ThresholdKind.ABSOLUTE, subject="Harbour City", min_change=0.5),
            False,
        ),
    ],
)
def test_a_counter_test_must_be_able_to_contradict_its_hypothesis(counter, fair):
    fatigue = _hypothesis(AgentRole.PHYSICAL, Cause.UNIT_FATIGUE)  # Northvale sprints down 15%
    sprints = dict(metric=Metric.SPRINT_COUNT, subject="Northvale", min_change=0.15) | counter
    exam = CrossExamination(
        hypothesis_id="hyp-1",
        challenger=AgentRole.TACTICS,
        counter_prediction=_prediction(**sprints),
        tool_call_id="tc-1",
        observed_change=0.0,
        reason="r",
    )
    if fair:
        check_counter_test(fatigue, exam)
    else:
        with pytest.raises(ValueError):
            check_counter_test(fatigue, exam)


def test_a_challenger_never_examines_its_own_hypothesis():
    fatigue = _hypothesis(AgentRole.PHYSICAL, Cause.UNIT_FATIGUE)
    own = CrossExamination(
        hypothesis_id="hyp-1",
        challenger=AgentRole.PHYSICAL,
        counter_prediction=_prediction(metric=Metric.SPRINT_COUNT, subject="Harbour City"),
        tool_call_id="tc-1",
        observed_change=0.0,
        reason="r",
    )
    with pytest.raises(ValueError, match="its own hypothesis"):
        check_counter_test(fatigue, own)


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


def _card_example():
    return json.loads(_spec_example("## 5. Insight Card"))


def test_a_card_reaches_a_surface_only_once_verified():
    card = _card_example()
    assert InsightCard.model_validate(dict(card, status="shown")).status == "shown"
    rejected = dict(
        card["verification"],
        status="rejected",
        rejection_reason="number mismatch",
        number_check="failed",
        support_level=None,
        language_level=None,
    )
    corrected = dict(card["verification"], status="corrected", number_check="corrected")
    assert InsightCard.model_validate(dict(card, status="shown", verification=corrected))
    for status in ("verified", "scheduled", "shown", "expired", "killed"):
        for verification in (None, rejected):
            with pytest.raises(ValidationError, match="needs a passed or corrected verification"):
                InsightCard.model_validate(dict(card, status=status, verification=verification))
    # A card that fails re-verification is withdrawn and keeps the rejected verdict.
    assert InsightCard.model_validate(dict(card, status="withdrawn", verification=rejected))
    for status in ("rejected", "withdrawn"):
        with pytest.raises(ValidationError, match="carries the rejected verification"):
            InsightCard.model_validate(dict(card, status=status))


def test_only_key_events_take_the_fast_lane():
    card = _card_example()
    changes = [p for p in card["propositions"] if p["type"] == "change"]
    goal = dict(
        card,
        lane="fast",
        status="shown",
        verification=None,
        moment_type="key_event",
        case_outcome="none",
        propositions=changes,
    )
    assert InsightCard.model_validate(goal).lane == "fast"
    for unfit in (
        dict(goal, moment_type="pressure_shift"),
        dict(goal, case_outcome="explained", propositions=card["propositions"]),
        dict(goal, verification=card["verification"]),
    ):
        with pytest.raises(ValidationError, match="fast-lane card is a key event"):
            InsightCard.model_validate(unfit)


def test_revisions_are_numbered_from_two_up_to_the_card_revision():
    card = _card_example()
    second = {"revision": 2, "at": "70:05", "reason": "events amended", "amendment_ids": ["a1"]}
    assert InsightCard.model_validate(dict(card, revision=2, revisions=[second])).revision == 2
    third = dict(second, revision=3)
    for revision, revisions in ((2, []), (1, [second]), (3, [second]), (3, [third, second])):
        with pytest.raises(ValidationError, match="revisions must number"):
            InsightCard.model_validate(dict(card, revision=revision, revisions=revisions))
    with pytest.raises(ValidationError, match="revision 2 or later"):
        InsightCard.model_validate(dict(card, status="revised"))


def test_change_propositions_move():
    with pytest.raises(ValidationError, match="moves up or down"):
        ChangeProposition(
            id="p1",
            metric=Metric.PRESSURE_RATE,
            subject="Harbour City",
            direction=Direction.FLAT,
            window="58:00-63:00",
            baseline=BaselineScope.FIRST_HALF,
        )


def test_cue_template_is_an_enum_everywhere():
    spec = BroadcastCueSpec(template=OverlayTemplate.PRESSURE_SHIFT_BAR, fields={"team": "x"})
    assert spec.template == "pressure_shift_bar"
    with pytest.raises(ValidationError):
        BroadcastCueSpec(template="presure_shift_bar", fields={})


def test_cue_slot_cannot_close_before_it_opens():
    assert ShowAt(mode="immediate", not_before="63:40", not_after="63:40").mode == "immediate"
    with pytest.raises(ValidationError):
        ShowAt(mode="next_dead_ball", not_before="64:25", not_after="63:40")


def test_cues_tied_to_an_insight_name_it():
    cue = json.loads(_spec_example("### 12.3 Broadcast Cue Feed"))
    for kind in ("insight", "update", "withdrawal"):
        for missing in ("insight_id", "insight_revision"):
            with pytest.raises(ValidationError, match="names its insight_id"):
                Cue.model_validate(dict(cue, kind=kind, **{missing: None}))
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Cue.model_validate(dict(cue, insight_revision=0))
    # A key-event cue may name the fast-lane card it comes from, or nothing.
    for named in (True, False):
        key_event = dict(cue, kind="key_event")
        if not named:
            key_event |= {"insight_id": None, "insight_revision": None}
        assert Cue.model_validate(key_event).kind == "key_event"


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


def _check(**overrides):
    base = dict(
        metric=Metric.SPRINT_COUNT,
        subject="NV-03",
        direction=Direction.DOWN,
        separation=-0.9,
        ci_low=-1.2,
        ci_high=-0.6,
    )
    return base | overrides


def _exclusion(rule, *checks, **check):
    observables = list(checks) or [_check(**check)]
    return dict(script_id="p07-s1", cause=Cause.PLAYER_FATIGUE, rule=rule, observables=observables)


def _with_exclusions(exclusions, suite=Suite.PLANTED):
    run = _eval_run([_estimate()]).model_dump()
    metrics = [_estimate(suite=suite).model_dump()]
    return EvalRun.model_validate(
        dict(run, suites=[suite], metrics=metrics, not_observable=exclusions)
    )


UP = dict(metric=Metric.PRESSURE_RATE, subject="Harbour City", direction=Direction.UP)


@pytest.mark.parametrize(
    "exclusion",
    [
        # Its paired CI clears zero downwards, but one match cannot show it.
        _exclusion("no_separation"),
        _exclusion("no_separation", **UP, separation=1.9, ci_low=0.1, ci_high=0.4),
        # A CI that includes or only touches zero is excluded by the paired-effect rule first.
        _exclusion("no_paired_effect", ci_high=0.1),
        _exclusion("no_paired_effect", ci_high=0.0),
        _exclusion("no_paired_effect", **UP, separation=0.3, ci_low=-0.1, ci_high=0.4),
    ],
)
def test_excluded_scripts_carry_the_numbers_that_excluded_them(exclusion):
    assert _with_exclusions([exclusion]).not_observable[0].rule == exclusion["rule"]


@pytest.mark.parametrize(
    "exclusion,message",
    [
        (_exclusion("no_paired_effect"), "clears zero its way"),
        (_exclusion("no_separation", ci_high=0.1), "paired-effect rule applies first"),
        (_exclusion("no_separation", separation=-2.4), "separates enough to count"),
        (_exclusion("no_separation", separation=-2.0), "separates enough to count"),
        (_exclusion("no_separation", **UP, separation=2.1, ci_low=0.1, ci_high=0.4), "enough"),
        (_exclusion("no_separation", _check(), _check(subject="NV-04", separation=-2.2)), "enough"),
        (_exclusion("no_separation", separation=0.9), "points against the paired-effect"),
        (_exclusion("no_separation", direction=Direction.FLAT), "moves up or down"),
        (_exclusion("no_separation", ci_low=-0.5, ci_high=-0.6), "ci_low is above ci_high"),
        (_exclusion("no_separation", subject=""), "at least 1 character"),
        (_exclusion("no_separation", separation=float("nan")), "finite number"),
        (_exclusion("no_paired_effect", ci_low=float("-inf"), ci_high=0.1), "finite number"),
        (dict(_exclusion("no_separation"), cause=Cause.NONE), "never planted causes"),
    ],
)
def test_an_exclusion_must_fit_its_rule(exclusion, message):
    with pytest.raises(ValidationError, match=message):
        _with_exclusions([exclusion])


def test_exclusions_belong_to_planted_runs_and_are_listed_once():
    with pytest.raises(ValidationError, match="listed once"):
        _with_exclusions([_exclusion("no_separation")] * 2)
    with pytest.raises(ValidationError, match="planted suite"):
        _with_exclusions([_exclusion("no_separation")], suite=Suite.DECOYS)


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
