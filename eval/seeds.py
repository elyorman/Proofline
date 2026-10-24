"""Single-field false claims; factual references and all other card fields stay intact."""

import math
from dataclasses import dataclass
from decimal import Decimal

from agents import narrator
from agents.verifier.checks import numbers_match
from contracts.card import InsightCard
from contracts.eval_run import SeedType
from contracts.prediction import Direction
from contracts.taxonomy import LANGUAGE_FOR_SUPPORT, Cause, SupportLevel
from state.subjects import opponent, resolve
from state.tools import Feed


@dataclass(frozen=True)
class Mutation:
    kind: SeedType
    card: InsightCard | None
    field: str | None = None
    before: str | float | None = None
    after: str | float | None = None
    skip_reason: str | None = None


def next_display(value: float) -> float:
    """The first larger binary float whose fixed two-decimal display differs."""
    old = f"{value:.2f}"
    boundary = 0.0 if old == "-0.00" else float(Decimal(old) + Decimal("0.005"))
    while f"{boundary:.2f}" == old:
        boundary = math.nextafter(boundary, math.inf)
    previous = math.nextafter(boundary, -math.inf)
    while previous > value and f"{previous:.2f}" != old:
        boundary, previous = previous, math.nextafter(previous, -math.inf)
    return boundary


def mutations(card: InsightCard, feed: Feed) -> list[Mutation]:
    result = []
    for kind in SeedType:
        clone = card.model_copy(deep=True)
        primary = clone.primary_cause
        change = next((p for p in clone.propositions if primary and p.id == primary.effect), None)
        field, before, after, reason = "claim", card.claim, None, None
        if kind in (SeedType.EVIDENCE_VALUE, SeedType.BASELINE_VALUE):
            if not clone.evidence:
                reason = "card has no evidence"
            else:
                target = (
                    clone.evidence[0]
                    if kind == SeedType.EVIDENCE_VALUE
                    else clone.evidence[0].baseline
                )
                field = (
                    "evidence[0].value"
                    if kind == SeedType.EVIDENCE_VALUE
                    else "evidence[0].baseline.value"
                )
                before = target.value
                after = target.value = next_display(before)
        elif kind == SeedType.UNSUPPORTED_NUMBER:
            number = 1000000
            while numbers_match(card, [str(number)]):
                number += 1
            change_name = narrator.LABEL.get(
                change.metric, (change.metric.value.replace("_", " "),)
            )[0]
            who = narrator.who(feed.meta, change.subject)[0]
            after = (
                f"Since {change.window.start.minute}', the {change_name.lower()} "
                f"for {who} has changed by {number}."
            )
        elif kind == SeedType.CLAIM_DIRECTION:
            if change is None or (change.metric, change.direction) not in narrator.CHANGE:
                reason = "primary change has no direction template"
            else:
                change.direction = (
                    Direction.DOWN if change.direction == Direction.UP else Direction.UP
                )
                clone.propositions = [change, *[p for p in clone.propositions if p.id != change.id]]
                after = narrator.claim(clone, feed.meta)
                clone = card.model_copy(deep=True)
        elif kind == SeedType.WRONG_TEAM:
            if change is None:
                reason = "card has no primary change proposition"
            else:
                other = opponent(feed.meta, resolve(feed.meta, change.subject).team)
                change.subject = other
                clone.propositions = [change, *[p for p in clone.propositions if p.id != change.id]]
                after = narrator.claim(clone, feed.meta)
                clone = card.model_copy(deep=True)
        elif kind == SeedType.OVERCERTAINTY:
            if card.verification.support_level == SupportLevel.STRONG:
                reason = "strong support already permits assertive language"
            elif primary is None:
                reason = "card has no primary cause"
            else:
                phrase = narrator.cause_phrase(primary.cause, card.subject.team, 0)
                after = f"The change is definitely caused by {phrase}."
        elif kind == SeedType.UNNAMED_CAUSE:
            named = {a.cause for a in card.attributions} | {
                r.taxonomy for r in card.rejected_alternatives
            }
            cause = next((c for c in narrator.CAUSE if c not in named and c != Cause.OTHER), None)
            if cause is None:
                reason = "all available causes are already named"
            else:
                phrase = narrator.cause_phrase(cause, card.subject.team, 0)
                level = LANGUAGE_FOR_SUPPORT[card.verification.support_level]
                after = narrator.LEVEL[level][0].format(cause=phrase)
        else:
            if change is None:
                reason = "card has no primary change proposition"
            else:
                field = f"propositions[{clone.propositions.index(change)}].direction"
                before = change.direction.value
                change.direction = (
                    Direction.DOWN if change.direction == Direction.UP else Direction.UP
                )
                after = change.direction.value
        if reason:
            result.append(Mutation(kind, None, skip_reason=reason))
        else:
            if field == "claim":
                clone.claim = after
            result.append(Mutation(kind, clone, field, before, after))
    return result
