"""Final published revisions and planted-card matching conditions."""

from collections.abc import Iterable

from contracts.card import NEEDS_PASSING, InsightCard
from contracts.eval_run import CardOutcome, MatchOutcome, Suite
from contracts.planted import PlantedTruth
from contracts.taxonomy import CardStatus, CaseOutcome, Cause

# Outcomes that claim a real effect; a card closing a decoy's case as `none` is restraint.
CLAIMS = (CaseOutcome.EXPLAINED, CaseOutcome.OTHER)


def final_cards(
    cards: Iterable[InsightCard], *, batch_published: bool = False
) -> list[InsightCard]:
    latest: dict[tuple[str, str], InsightCard] = {}
    seen: dict[tuple[str, str, int], str] = {}
    for card in cards:
        card = InsightCard.model_validate(card.model_dump(mode="json"))
        if batch_published and (
            card.status not in NEEDS_PASSING
            or card.verification is None
            or card.verification.status not in ("passed", "corrected")
        ):
            raise ValueError("a batch-published card must be verified")
        identity = (card.match_id, card.id)
        revision = (*identity, card.revision)
        serialized = card.model_dump_json()
        if revision in seen and seen[revision] != serialized:
            raise ValueError(f"conflicting records for {card.id} revision {card.revision}")
        seen[revision] = serialized
        # An unfinished replacement cannot hide the revision that passed the Verifier.
        if (
            not batch_published
            and card.status not in NEEDS_PASSING
            and card.status != CardStatus.WITHDRAWN
        ):
            continue
        if identity not in latest or card.revision > latest[identity].revision:
            latest[identity] = card
    return sorted(latest.values(), key=lambda c: (c.match_id, c.id))


def match_card(card: InsightCard, truth: PlantedTruth) -> CardOutcome:
    """Recall needs the card in time: its window overlaps the truth's observable window. A
    planted change runs to full time once it starts, so for precision a card is true when it
    names that change's cause anywhere after it began (`holds`)."""
    reason = "matched"
    running = False
    primary = card.primary_cause
    if card.match_id != truth.match_id:
        reason = "match mismatch"
    elif primary is None or primary.cause != truth.cause:
        reason = "class mismatch"
    elif card.subject.team != truth.team:
        reason = "team mismatch"
    else:
        effect = next(p for p in card.propositions if p.id == primary.effect)
        observable = next(
            (
                o
                for o in truth.observables
                if (o.metric, o.subject) == (effect.metric, effect.subject)
            ),
            None,
        )
        if observable is None:
            reason = "observable mismatch"
        elif effect.direction != observable.direction:
            reason = "direction mismatch"
        else:
            running = truth.started < effect.window.end
            if not (
                effect.window.start < truth.window.end and truth.window.start < effect.window.end
            ):
                reason = "window does not overlap"
    return CardOutcome(
        card_id=card.id,
        revision=card.revision,
        outcome=card.case_outcome,
        correct=reason == "matched",
        holds=running,
        reason=reason,
    )


def score_match(
    truth: PlantedTruth,
    cards: Iterable[InsightCard],
    suite: Suite | str,
    *,
    excluded: bool = False,
    batch_published: bool = False,
) -> MatchOutcome:
    suite = Suite(suite)
    if suite not in (Suite.PLANTED, Suite.DECOYS):
        raise ValueError("only planted and decoy matching is implemented")
    if (suite == Suite.DECOYS) != (truth.cause == Cause.NONE):
        raise ValueError("truth does not belong to the requested suite")
    if excluded and suite != Suite.PLANTED:
        raise ValueError("only planted matches can be excluded")
    published = [
        c
        for c in final_cards(cards, batch_published=batch_published)
        if c.match_id == truth.match_id
        and (batch_published or (c.lane == "full" and c.status in NEEDS_PASSING))
    ]
    results = [match_card(c, truth) for c in published]
    if suite == Suite.DECOYS:
        claims = [c for c in published if c.case_outcome in CLAIMS]
        correct = not claims
        reason = "no cause published" if correct else "cause published on decoy"
    elif suite == Suite.PLANTED:
        correct = any(r.correct for r in results)
        reason = (
            "matched"
            if correct
            else "; ".join(f"{r.card_id}: {r.reason}" for r in results) or "no published card"
        )
    else:
        raise ValueError("only planted and decoy matching is implemented")
    return MatchOutcome(
        match_id=truth.match_id,
        suite=suite,
        correct=correct,
        reason=reason,
        excluded=excluded,
        cards=results,
    )
