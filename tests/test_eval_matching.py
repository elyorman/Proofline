import json
import re
from pathlib import Path

import pytest

from contracts.card import CheckResult, InsightCard
from contracts.taxonomy import Cause
from eval.matching import match_card, score_match
from eval.runner import evaluate
from eval.suites import load_suite

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bundle():
    return load_suite(ROOT / "engine/suites", "planted", "dev")


@pytest.fixture
def make_card():
    text = (ROOT / "docs/spec.md").read_text()
    example = json.loads(re.search(r"## 5\. Insight Card.*?```json\n(.*?)```", text, re.S)[1])

    def make(truth, **overrides):
        raw = json.loads(json.dumps(example))
        observable = truth.observables[0]
        raw.update(id=f"card-{truth.match_id}", match_id=truth.match_id, status="shown")
        raw["subject"]["team"] = truth.team
        raw["propositions"] = [
            dict(
                id="change",
                type="change",
                metric=observable.metric,
                subject=observable.subject,
                direction=observable.direction,
                window=str(truth.window),
                baseline="first_half",
            ),
            dict(
                id="cause",
                type="attribution",
                cause=truth.cause,
                effect="change",
                role="primary",
                hypothesis_id="h1",
                agent="single",
            ),
        ]
        raw.update(overrides)
        return InsightCard.model_validate(raw)

    return make


def test_matches_the_primary_effect(bundle, make_card):
    truth = bundle.truth.entries[0]
    assert match_card(make_card(truth), truth).correct
    assert score_match(truth, [make_card(truth)], bundle.truth.suite).correct


@pytest.mark.parametrize("condition", ["class", "team", "observable", "direction", "window"])
def test_records_why_a_card_fails(bundle, make_card, condition):
    truth = bundle.truth.entries[0]
    raw = make_card(truth).model_dump(mode="json")
    if condition == "class":
        raw["propositions"][1]["cause"] = Cause.BLOCK_DEEPER
    elif condition == "team":
        raw["subject"]["team"] = "Northvale" if truth.team != "Northvale" else "Harbour City"
    elif condition == "observable":
        raw["propositions"][0]["subject"] = "unrelated"
    elif condition == "direction":
        raw["propositions"][0]["direction"] = (
            "up" if truth.observables[0].direction == "down" else "down"
        )
    else:
        raw["propositions"][0]["window"] = "10:00-20:00"
    result = match_card(InsightCard.model_validate(raw), truth)
    assert not result.correct and condition in result.reason


def test_half_open_windows_do_not_overlap_at_the_boundary(bundle, make_card):
    truth = bundle.truth.entries[0]
    raw = make_card(truth).model_dump(mode="json")
    raw["propositions"][0]["window"] = {"start": "45:00", "end": truth.window.start}
    assert not match_card(InsightCard.model_validate(raw), truth).correct


def test_withdrawal_supersedes_an_earlier_published_card(bundle, make_card):
    truth = bundle.truth.entries[0]
    first = make_card(truth)
    raw = first.model_dump(mode="json")
    raw.update(
        status="withdrawn", revision=2, revisions=[dict(revision=2, at="80:00", reason="amended")]
    )
    raw["verification"].update(
        status="rejected",
        rejection_reason="amended evidence",
        support_level=None,
        language_level=None,
    )
    withdrawn = InsightCard.model_validate(raw)
    assert not score_match(truth, [withdrawn, first], "planted").correct


def test_drafts_do_not_count_and_conflicting_revisions_are_refused(bundle, make_card):
    truth = bundle.truth.entries[0]
    assert not score_match(truth, [make_card(truth, status="proposed")], "planted").correct
    first = make_card(truth)
    changed = make_card(truth, claim="Different text at the same revision")
    with pytest.raises(ValueError, match="conflicting"):
        score_match(truth, [first, changed], "planted")


def test_decoy_restraint_counts_explained_and_other_cards(bundle, make_card):
    decoy = load_suite(ROOT / "engine/suites", "decoys", "dev").truth.entries[0]
    card = make_card(bundle.truth.entries[0], match_id=decoy.match_id)
    assert score_match(decoy, [], "decoys").correct
    assert not score_match(decoy, [card], "decoys").correct
    raw = card.model_dump(mode="json")
    raw["case_outcome"] = "other"
    raw["propositions"][1]["cause"] = "other"
    assert not score_match(decoy, [InsightCard.model_validate(raw)], "decoys").correct


def test_revalidation_catches_mutated_verification(bundle, make_card):
    card = make_card(bundle.truth.entries[0])
    card.verification.number_check = CheckResult.FAILED
    with pytest.raises(ValueError):
        score_match(bundle.truth.entries[0], [card], "planted")


@pytest.mark.parametrize("status", ["verified", "scheduled", "killed"])
def test_a_card_that_passed_the_verifier_counts_whether_or_not_it_aired(bundle, make_card, status):
    truth = bundle.truth.entries[0]
    raw = make_card(truth, status=status).model_dump(mode="json")
    raw["timing"]["published_at"] = None
    assert score_match(truth, [InsightCard.model_validate(raw)], "planted").correct


@pytest.mark.parametrize("status", ["proposed", "cross_examined"])
def test_unpublished_cards_do_not_count(bundle, make_card, status):
    truth = bundle.truth.entries[0]
    raw = make_card(truth, status=status).model_dump(mode="json")
    raw["timing"]["published_at"] = None
    card = InsightCard.model_validate(raw)
    result = score_match(truth, [card], "planted")
    assert not result.correct and result.cards == []


def test_an_expired_card_that_reached_the_recap_still_counts(bundle, make_card):
    truth = bundle.truth.entries[0]
    assert score_match(truth, [make_card(truth, status="expired")], "planted").correct


def test_a_card_from_another_match_cannot_match_directly(bundle, make_card):
    truth = bundle.truth.entries[0]
    result = match_card(make_card(truth, match_id="different"), truth)
    assert not result.correct and result.reason == "match mismatch"


def test_decoy_exclusions_and_mislabeled_truth_are_refused(bundle):
    decoy = load_suite(ROOT / "engine/suites", "decoys", "dev").truth.entries[0]
    with pytest.raises(ValueError, match="excluded"):
        score_match(decoy, [], "decoys", excluded=True)
    with pytest.raises(ValueError, match="truth"):
        score_match(bundle.truth.entries[0], [], "decoys")


def test_a_secondary_cause_cannot_earn_recall(bundle, make_card):
    truth = bundle.truth.entries[0]
    raw = make_card(truth).model_dump(mode="json")
    raw["propositions"][1]["role"] = "secondary"
    raw["propositions"].append(
        dict(raw["propositions"][1], id="primary", role="primary", cause=Cause.BLOCK_DEEPER)
    )
    assert not score_match(truth, [InsightCard.model_validate(raw)], "planted").correct


def test_evaluate_rejects_duplicate_suites_and_cards_outside_the_cohort(bundle, make_card):
    options = dict(run_id="fixture", variant="A", model_id="fixture", resamples=50)
    with pytest.raises(ValueError, match="distinct suites"):
        evaluate([bundle, bundle], [], **options)
    with pytest.raises(ValueError, match="outside the cohort"):
        evaluate([bundle], [make_card(bundle.truth.entries[0], match_id="unknown")], **options)


def test_evaluate_retains_wrong_extra_cards_for_precision(bundle, make_card):
    truth = bundle.truth.entries[0]
    correct = make_card(truth)
    raw = correct.model_dump(mode="json")
    raw["id"] = "extra"
    raw["propositions"][1]["cause"] = Cause.BLOCK_DEEPER
    run = evaluate(
        [bundle],
        [correct, InsightCard.model_validate(raw)],
        run_id="fixture",
        variant="A",
        model_id="fixture",
        resamples=50,
    )
    outcome = next(o for o in run.outcomes if o.match_id == truth.match_id)
    assert outcome.correct and len(outcome.cards) == 2
    precision = next(m for m in run.metrics if m.name == "cause_precision")
    assert precision.value == 0.5 and precision.n == 2


def test_an_unpublished_new_revision_does_not_hide_the_shown_revision(bundle, make_card):
    truth = bundle.truth.entries[0]
    shown = make_card(truth)
    raw = shown.model_dump(mode="json")
    raw.update(
        status="proposed", revision=2, revisions=[dict(revision=2, at="80:00", reason="draft")]
    )
    draft = InsightCard.model_validate(raw)
    result = score_match(truth, [shown, draft], "planted")
    assert result.correct and result.cards[0].revision == 1
    run = evaluate(
        [bundle], [shown, draft], run_id="fixture", variant="A", model_id="fixture", resamples=50
    )
    assert next(o for o in run.outcomes if o.match_id == truth.match_id) == result
