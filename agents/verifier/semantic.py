"""The Verifier's semantic check (spec §9.2): a model from a different family from the
agents' reads only the card's propositions, evidence and text, and says whether each
sentence follows at the card's language level, flagging any overstatement."""

import json

from pydantic import BaseModel

from agents import narrator
from agents.llm import Model, Usage
from contracts.card import InsightCard
from contracts.taxonomy import LANGUAGE_FOR_SUPPORT, SupportLevel

INSTRUCTIONS = """\
You are an independent verifier for football match insights. You see a card's facts and \
its sentences, never how they were produced. For each sentence, decide whether the facts \
entail it, and whether it overstates them.
A sentence overstates when it claims more than the facts: a number, time or team not in \
them, a change in the wrong direction, or more certainty about the cause than the language \
level allows. The support level the Verifier assigned is a fact. 'assertive' may \
state the cause as fact; 'measured' may say it looks like or \
is consistent with the cause; 'tentative' may only say it may be the cause. The card is \
published when its window ends, so 'since <start>' means from the window's start until now. \
A rejected alternative is a cause the investigation ruled out; naming it as ruled out is \
entailed. Keep each reason under 20 words."""


class SentenceCheck(BaseModel):
    sentence: str
    entailed: bool
    overstated: bool
    reason: str


class SemanticReport(BaseModel):
    sentences: list[SentenceCheck]


def facts(card: InsightCard, support: SupportLevel) -> dict:
    change = next(p for p in card.propositions if p.type == "change")
    return {
        "change": {
            "metric": change.metric.value,
            "subject": change.subject,
            "direction": change.direction.value,
            "window": str(change.window),
            "compared_with": change.baseline.value,
        },
        "causes": [
            {
                "cause": a.cause.value,
                "role": a.role,
                "plain": narrator.cause_phrase(a.cause, card.subject.team, 0),
            }
            for a in card.attributions
        ],
        "evidence": [
            {
                "metric": ev.metric.value,
                "subject": ev.subject,
                "first_half": narrator.number(ev.metric, ev.baseline.value),
                "window": narrator.number(ev.metric, ev.value),
            }
            for ev in card.evidence
        ],
        "ruled_out": [
            narrator.cause_phrase(r.taxonomy, card.subject.team, 0)
            for r in card.rejected_alternatives
        ],
        "team_the_cause_is_about": card.subject.team,
        "support_level": support.value,
        "language_level": LANGUAGE_FOR_SUPPORT[support].value,
        "published_at": str(card.timing.detected_at),
    }


async def check(
    model: Model, card: InsightCard, sentences: list[str], support: SupportLevel
) -> tuple[SemanticReport, Usage]:
    prompt = json.dumps({"facts": facts(card, support), "sentences": sentences}, indent=1)
    return await model.ask("verifier", INSTRUCTIONS, prompt, SemanticReport)
