"""Verify a proposed card (spec §9.2): deterministic checks and the support level first;
if the card can be published, narration at that level, then the number check and the
semantic check on the text. The verified or rejected card is rebuilt by full validation,
so the contracts' publishing gate applies to it."""

from dataclasses import dataclass

from agents import narrator
from agents.llm import Model, Usage
from agents.verifier import semantic
from agents.verifier.checks import (
    Record,
    baseline_fair,
    change,
    contradicted,
    level_of,
    numbers_match,
    recompute,
    sample,
    sample_size,
)
from agents.verifier.rules import support
from contracts.card import CheckResult, InsightCard, Verification
from contracts.prediction import CrossExamination
from contracts.taxonomy import CardStatus
from state.tools import Feed, window_minutes

MODEL_FAMILY = "openai"  # gpt-5-mini, as the agents (spec §15)


@dataclass
class Verdict:
    card: InsightCard
    report: semantic.SemanticReport | None
    usage: Usage


def _done(card: InsightCard, verification: Verification, **update) -> InsightCard:
    status = CardStatus.VERIFIED if verification.status == "passed" else CardStatus.REJECTED
    data = card.model_dump(mode="json") | update
    return InsightCard.model_validate(
        data | {"status": status, "verification": verification.model_dump(mode="json")}
    )


async def verify(
    model: Model, card: InsightCard, record: Record, feed: Feed, exams: list[CrossExamination]
) -> Verdict:
    matched = recompute(card, record, feed)
    checks = {
        "baseline_check": baseline_fair(card),
        "sample_size_check": sample_size(card, record),
        "contradiction_check": CheckResult.FAILED
        if contradicted(card, feed)
        else CheckResult.PASSED,
    }
    lead = card.evidence[0]
    primary = card.primary_cause.hypothesis_id
    weakened = any(e.hypothesis_id == primary and e.result == "weakened" for e in exams)
    level = support(
        change(lead.metric, lead.value, lead.baseline.value),
        lead.metric,
        level_of(feed, lead.subject),
        window_minutes(lead.window),
        sample(lead, record),
        weakened,
        checks["contradiction_check"] == CheckResult.FAILED,
    )
    common = dict(recompute="match" if matched else "mismatch", verifier_model_family=MODEL_FAMILY)
    failed = [name for name, result in checks.items() if result != CheckResult.PASSED]
    if not matched or failed or level is None:
        reason = "recompute mismatch" if not matched else ", ".join(failed) or "below support rules"
        verification = Verification(
            status="rejected",
            **common,
            **checks,
            number_check=CheckResult.SKIPPED,
            semantic_check=CheckResult.SKIPPED,
            rejection_reason=reason,
        )
        return Verdict(_done(card, verification), None, Usage())

    texts = narrator.variants(card, feed.meta, level)
    every = [card.claim] + [t for by_locale in texts.values() for t in by_locale.values()]
    numbers = CheckResult.PASSED if numbers_match(card, every) else CheckResult.FAILED
    english = [card.claim] + [by_locale["en"] for by_locale in texts.values()]
    try:
        report, usage = await semantic.check(model, card, english, level, feed.meta)
    except ValueError as exc:  # no answer is no verification: the card is not published
        report, usage = None, Usage()
        unanswered = f"the semantic check gave no answer ({str(exc)[:80]})"
    sound = report is not None and all(s.entailed and not s.overstated for s in report.sentences)
    semantic_result = CheckResult.PASSED if sound else CheckResult.FAILED
    if numbers == CheckResult.PASSED and sound:
        verification = Verification(
            status="passed",
            **common,
            **checks,
            number_check=numbers,
            semantic_check=semantic_result,
            support_level=level,
        )
        return Verdict(_done(card, verification, variants=texts), report, usage)
    flagged = (
        [s.reason for s in report.sentences if not s.entailed or s.overstated]
        if report
        else [unanswered]
    )
    verification = Verification(
        status="rejected",
        **common,
        **checks,
        number_check=numbers,
        semantic_check=semantic_result,
        rejection_reason="; ".join(
            ["number check failed"] * (numbers != CheckResult.PASSED) + flagged
        )[:500],
    )
    return Verdict(_done(card, verification), report, usage)
