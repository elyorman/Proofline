"""The Verifier's semantic check (spec §9.2): a model from a different family from the
agents' reads only the card's propositions, evidence and text, and says whether each
sentence follows at the card's language level, flagging any overstatement."""

import json

from pydantic import BaseModel

from agents import narrator
from agents.llm import Model, Usage
from contracts.card import InsightCard
from contracts.meta import MatchMeta
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
published when its window ends, so 'since <start>' with the window's start is entailed. \
Each subject is written as 'names' gives it. A sentence that names no cause cannot \
overstate one; a sentence that names one is held to the language level. Plain words for a \
change ('pressing harder', 'going long more often', 'sprinting less') narrate its metric \
and are entailed when the metric moved that way. A rejected alternative is a cause the \
investigation ruled out; naming it as ruled out is entailed. A 'follow_up' is a check on \
the minutes after the card: while it is pending, saying it will be checked against its \
'against' causes by the end of its minutes is entailed; once settled, 'not <cause>' is \
entailed for each cause it ruled out, and when it is unresolved, saying it could be any of \
the causes is entailed. Keep each reason under 20 words."""


class SentenceCheck(BaseModel):
    sentence: str
    entailed: bool
    overstated: bool
    reason: str


class SemanticReport(BaseModel):
    sentences: list[SentenceCheck]


def facts(card: InsightCard, support: SupportLevel, meta: MatchMeta) -> dict:
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
            narrator.cause_phrase(r.taxonomy, r.team or card.subject.team, 0)
            for r in card.rejected_alternatives
        ],
        "names": {
            s: narrator.who(meta, s)[0]
            for s in dict.fromkeys(
                [p.subject for p in card.propositions if p.type == "change"]
                + [ev.subject for ev in card.evidence]
            )
        },
        "team_the_cause_is_about": card.subject.team,
        "support_level": support.value,
        "language_level": LANGUAGE_FOR_SUPPORT[support].value,
        "published_at": str(card.timing.verified_at or card.timing.detected_at),
    } | ({"follow_up": _follow_up(card)} if card.follow_up else {})


def _follow_up(card: InsightCard) -> dict:
    f = card.follow_up
    out = {
        "status": f.status,
        "against": [narrator.cause_phrase(r.cause, r.team, 0) for r in f.rivals],
        "minutes": str(f.window),
    }
    if f.status == "confirmed":
        out["ruled_out"] = out["against"]
    elif f.status == "overturned":
        was = next(r for r in card.rejected_alternatives if r.rejected_by == "follow_up")
        out["ruled_out"] = [narrator.cause_phrase(was.taxonomy, was.team, 0)]
    return out


async def check(
    model: Model, card: InsightCard, sentences: list[str], support: SupportLevel, meta: MatchMeta
) -> tuple[SemanticReport, Usage]:
    prompt = json.dumps({"facts": facts(card, support, meta), "sentences": sentences}, indent=1)
    report, usage = await model.ask("verifier", INSTRUCTIONS, prompt, SemanticReport)
    # A sentence left unjudged is not verified. Judgements are counted, not matched by text:
    # the model echoes a sentence loosely ("->" for "→").
    if len(report.sentences) != len(sentences):
        raise ValueError(f"it judged {len(report.sentences)} of {len(sentences)} sentences")
    return report, usage
