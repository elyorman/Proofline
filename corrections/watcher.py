"""The Correction Watcher (spec §10): a published claim stays accountable as the feed is
corrected. When an amendment arrives, every published card whose evidence read an amended
event is re-verified at the new versions. The same numbers need nothing; a claim that still
holds becomes a new revision; one that no longer holds is withdrawn. Earlier revisions never
change: a correction is always a new revision of the card.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from agents import narrator
from agents.confirm import PERSIST_SD
from agents.investigation import change_of
from agents.llm import Model
from agents.single import case_tools
from agents.verifier.checks import Record
from agents.verifier.verify import MODEL_FAMILY, verify
from contracts.card import (
    Baseline,
    CheckResult,
    DependsOn,
    Evidence,
    InsightCard,
    Revision,
    Verification,
)
from contracts.case import Case
from contracts.event import EventAmendment
from contracts.prediction import Hypothesis
from contracts.taxonomy import CardStatus
from contracts.tool_result import DependencyEntry, EvidenceSet
from state import natural
from state.tools import Feed


@dataclass
class Published:
    """A published card and what re-verifying it needs: its case (for the cutoff), the
    primary cause's pre-registered hypothesis and the evidence sets the card depends on."""

    card: InsightCard
    case: Case
    hypothesis: Hypothesis
    evidence: dict[str, EvidenceSet]


@dataclass
class Correction:
    decision: Literal["revise", "withdraw"]
    card: InsightCard  # the new revision
    was: InsightCard


class DependencyIndex:
    """Which published cards read each event, through their evidence sets (spec §10.1)."""

    def __init__(self) -> None:
        self._cards: dict[str, set[str]] = defaultdict(set)
        self._sets: dict[str, set[str]] = defaultdict(set)
        self._match: dict[str, str] = {}

    def add(self, published: Published) -> None:
        card = published.card
        for set_id in card.depends_on.evidence_sets:
            for ref in published.evidence[set_id].events:
                self._cards[ref.event_id].add(card.id)
                self._sets[ref.event_id].add(set_id)
                self._match[ref.event_id] = card.match_id

    def dependents(self, amendment: EventAmendment) -> set[str]:
        return {c for event_id in amendment.event_ids for c in self._cards.get(event_id, ())}

    def entries(self) -> list[DependencyEntry]:
        return [
            DependencyEntry(
                event_id=event_id,
                match_id=self._match[event_id],
                evidence_set_ids=sorted(self._sets[event_id]),
                card_ids=sorted(cards),
            )
            for event_id, cards in sorted(self._cards.items())
        ]


def _withdrawn(candidate: InsightCard, was: InsightCard, feed: Feed, reason: str) -> InsightCard:
    claim, variants = narrator.withdrawal(candidate, was, feed.meta)
    verification = Verification(
        status="rejected",
        recompute="match",
        baseline_check=CheckResult.SKIPPED,
        sample_size_check=CheckResult.SKIPPED,
        contradiction_check=CheckResult.SKIPPED,
        number_check=CheckResult.SKIPPED,
        semantic_check=CheckResult.SKIPPED,
        verifier_model_family=MODEL_FAMILY,
        rejection_reason=reason,
    )
    data = candidate.model_dump(mode="json") | {
        "status": CardStatus.WITHDRAWN,
        "claim": claim,
        "variants": variants,
        "verification": verification.model_dump(mode="json"),
    }
    return InsightCard.model_validate(data)


async def correct(
    verifier: Model, published: Published, feed: Feed, amendment: EventAmendment
) -> Correction | None:
    """Re-verify one dependent card on the amended `feed`; None when its numbers are the same.

    Each evidence call is run again through the MCP tools over the amended feed, at the
    card's own cutoff. If the change the card explains is no longer beyond ordinary play, or
    the primary cause's pre-registered prediction no longer holds, the card is withdrawn;
    otherwise the new revision goes through the whole Verifier again.
    """
    was = published.card
    tools, sink = case_tools(published.case, feed)
    remeasured = []
    for ev in was.evidence:
        during = await tools.call(
            "metric", name=ev.metric, subject=ev.subject, window=str(ev.window)
        )
        before = await tools.call(
            "baseline", name=ev.metric, subject=ev.subject, scope=ev.baseline.window
        )
        remeasured.append((ev, during, before))
    if all(
        d.value == ev.value and b.baseline and b.baseline.value == ev.baseline.value
        for ev, d, b in remeasured
    ):
        return None
    revision = was.revision + 1
    because = f"amendment {amendment.amendment_id}: {amendment.reason}"
    evidence = [
        Evidence(
            metric=ev.metric,
            subject=ev.subject,
            window=ev.window,
            value=d.value,
            baseline=Baseline(window=ev.baseline.window, value=b.baseline.value),
            n_events=d.n_events,
            tool_call_id=d.tool_call_id,
        )
        for ev, d, b in remeasured
        if d.value is not None and b.baseline is not None
    ]
    candidate = InsightCard.model_validate(
        was.model_dump(mode="json")
        | {
            "status": CardStatus.PROPOSED,
            "revision": revision,
            "revisions": [r.model_dump(mode="json") for r in was.revisions]
            + [
                Revision(
                    revision=revision,
                    at=amendment.at,
                    reason=because,
                    amendment_ids=[amendment.amendment_id],
                ).model_dump(mode="json")
            ],
            "evidence": [e.model_dump(mode="json") for e in evidence],
            "depends_on": DependsOn(
                evidence_sets=[
                    s for _, d, b in remeasured for s in (d.evidence_set_id, b.evidence_set_id)
                ],
                data_version=feed.data_version,
            ).model_dump(mode="json"),
            "verification": None,
            "variants": {},
            "timing": was.timing.model_dump(mode="json")
            | {"verified_at": str(amendment.at), "published_at": None},
        }
    )
    # First, the change the card explains: if the amended data no longer show it beyond
    # ordinary play, there is nothing to explain.
    effect = next(x for x in was.propositions if x.id == was.primary_cause.effect)
    shown = next(
        (
            (d, b)
            for ev, d, b in remeasured
            if (ev.metric, ev.subject) == (effect.metric, effect.subject)
        ),
        None,
    )
    still = (
        natural.sigmas(
            feed.meta,
            effect.metric,
            effect.subject,
            effect.window,
            shown[0].value,
            shown[1].baseline.value,
        )
        if shown and shown[0].value is not None and shown[1].baseline is not None
        else None
    )
    way = 1 if effect.direction == "up" else -1
    if still is None or way * still[0] < PERSIST_SD:
        size = "no longer measurable" if still is None else f"now {still[0]:+.2f} sd"
        reason = (
            f"after {because}, {effect.metric} of {effect.subject} is {size}, within ordinary "
            f"play (a change needs {PERSIST_SD:g} sd)"
        )
        return Correction("withdraw", _withdrawn(candidate, was, feed, reason), was)
    p = published.hypothesis.prediction
    lead = next(
        ((d, b) for ev, d, b in remeasured if (ev.metric, ev.subject) == (p.metric, p.subject)),
        None,
    )
    moved = (
        change_of(p, lead[0].value, lead[1].baseline.value, feed.meta)
        if lead and lead[0].value is not None and lead[1].baseline is not None
        else None
    )
    if moved is None or not p.supported_by(moved):
        unit = " sd" if p.threshold_kind == "sigma" else ""
        size = "no longer measurable" if moved is None else f"now {moved:+.3f}{unit}"
        reason = (
            f"after {because}, {p.metric} of {p.subject} is {size}, short of the claim of "
            f"{p.direction} by {p.min_change:g}{unit}"
        )
        return Correction("withdraw", _withdrawn(candidate, was, feed, reason), was)
    record = Record.of(tools.log, sink.evidence)
    verdict = await verify(verifier, candidate, record, feed, [])
    if verdict.card.status != CardStatus.VERIFIED:
        rejected = verdict.card.verification.rejection_reason
        reason = f"after {because}, the Verifier rejected it: {rejected}"
        return Correction("withdraw", _withdrawn(candidate, was, feed, reason), was)
    revised = verdict.card.model_dump(mode="json")
    revised["status"] = CardStatus.REVISED
    revised["variants"] = narrator.updated(verdict.card.variants)
    return Correction("revise", InsightCard.model_validate(revised), was)
