"""The Director (spec §9.4): which card revisions a viewer sees and when, and the broadcast
cues for them, from verified cards and the match's own events. It schedules; it never
changes a card's words or numbers.

A new card reaches the viewer when it is ready, if its language level is one the profile
accepts and the half's attention budget has room; otherwise it waits for the recap. A
correction passes the budget and goes wherever the card it corrects went. A broadcast cue
airs at the first dead ball within its maximum delay, or expires. Goals take the fast lane.
"""

from dataclasses import dataclass

from agents import narrator
from contracts.card import InsightCard
from contracts.clock import MatchClock
from contracts.cue import Cue, CueKind, CueStatus, ShowAt
from contracts.event import Event, EventType
from contracts.meta import MatchMeta
from contracts.profile import Profile
from contracts.taxonomy import CardStatus, LanguageLevel, MomentType, OverlayTemplate

DEAD_BALL = {
    EventType.SET_PIECE,
    EventType.GOAL,
    EventType.FOUL,
    EventType.SUBSTITUTION,
    EventType.CARD,
}
MAX_DELAY_S = 45
CUE_S = 8
TEMPLATE = {
    MomentType.PRESSURE_SHIFT: OverlayTemplate.PRESSURE_SHIFT_BAR,
    MomentType.SHAPE_CHANGE: OverlayTemplate.SHAPE_CHANGE,
    MomentType.FATIGUE_SIGNAL: OverlayTemplate.FATIGUE_WARNING,
}
CORRECTION = {
    CardStatus.REVISED: (CueKind.UPDATE, OverlayTemplate.UPDATE_BANNER),
    CardStatus.WITHDRAWN: (CueKind.WITHDRAWAL, OverlayTemplate.WITHDRAWAL_BANNER),
}
RANK = {LanguageLevel.TENTATIVE: 0, LanguageLevel.MEASURED: 1, LanguageLevel.ASSERTIVE: 2}


@dataclass
class Schedule:
    cards: list[InsightCard]  # every revision, with the status and time the viewer sees
    cues: list[Cue]


def later(clock: MatchClock, seconds: int) -> MatchClock:
    total = clock.minute * 60 + clock.second + seconds
    return MatchClock(period=clock.period, minute=total // 60, second=total % 60)


def _ready(card: InsightCard) -> MatchClock:
    return card.timing.verified_at or card.timing.detected_at


def _dead_ball(events: list[Event], after: MatchClock) -> MatchClock | None:
    """The first stoppage after `after` within the cue's maximum delay."""
    latest = later(after, MAX_DELAY_S)
    return next(
        (
            e.clock
            for e in events
            if e.type in DEAD_BALL and after < e.clock and not latest < e.clock
        ),
        None,
    )


def _as(card: InsightCard, status: CardStatus, at: MatchClock | None) -> InsightCard:
    data = card.model_dump(mode="json")
    data["status"] = status
    data["timing"]["published_at"] = str(at) if at else None
    return InsightCard.model_validate(data)


def _cue(card: InsightCard, kind: CueKind, template, events, meta, aired: MatchClock | None):
    at = aired or _ready(card)
    return Cue(
        cue_id=f"cue-{card.id}-r{card.revision}",
        match_id=card.match_id,
        insight_id=card.id,
        insight_revision=card.revision,
        kind=kind,
        template=template,
        priority="high" if kind != CueKind.INSIGHT else "normal",
        show_at=ShowAt(mode="immediate", not_before=at, not_after=later(at, MAX_DELAY_S)),
        duration_s=CUE_S,
        fields=narrator.broadcast(card, meta, 0),
        language_level=card.verification.language_level if card.verification else None,
        status=(
            CueStatus.PENDING
            if kind != CueKind.INSIGHT  # a correction cue waits for the producer
            else CueStatus.APPROVED
            if aired
            else CueStatus.EXPIRED
        ),
        decided_by=None if kind != CueKind.INSIGHT else "auto",
    )


def goals(meta: MatchMeta, events: list[Event]) -> list[InsightCard]:
    """Fast-lane cards for goals, from the events alone (rule 6's only exception)."""
    home, away = meta.teams["home"].name, meta.teams["away"].name
    score = {home: 0, away: 0}
    out = []
    for e in (e for e in events if e.type == EventType.GOAL):
        score[e.team] += 1
        line = narrator.goal(e.team, f"{home} {score[home]}-{score[away]} {away}")
        window = f"{e.clock}-{later(e.clock, 1)}"
        out.append(
            InsightCard.model_validate(
                {
                    "id": f"ins-{meta.match_id}-goal-{e.event_id}",
                    "match_id": meta.match_id,
                    "case_id": f"key-{e.event_id}",
                    "lane": "fast",
                    "status": "shown",
                    "case_outcome": "none",
                    "moment_type": "key_event",
                    "subject": {"team": e.team},
                    "timing": {
                        "change_window": window,
                        "detected_at": str(e.clock),
                        "published_at": str(e.clock),
                    },
                    "propositions": [  # a goal raises the scorers' xG; the card states no cause
                        {
                            "id": "p1",
                            "type": "change",
                            "metric": "xg",
                            "subject": e.team,
                            "direction": "up",
                            "window": window,
                            "baseline": "match_so_far",
                        }
                    ],
                    "claim": line["en"],
                    "depends_on": {"evidence_sets": [], "data_version": "feed"},
                    "variants": {"casual": line, "analyst": line},
                    "provenance": {"trace_id": f"key-{e.event_id}"},
                }
            )
        )
    return out


def direct(
    revisions: list[InsightCard], events: list[Event], meta: MatchMeta, profile: Profile
) -> Schedule:
    """Schedule every revision of every card for one viewer and the broadcast."""
    cards: list[InsightCard] = []
    cues: list[Cue] = []
    shown: set[str] = set()
    used = {1: 0, 2: 0}
    for card in sorted(revisions, key=lambda c: (_ready(c).sort_key, c.revision)):
        at = _ready(card)
        if card.revision == 1:
            if card.status != CardStatus.VERIFIED:
                continue  # nothing the Verifier rejected reaches a surface
            level = card.verification.language_level
            if RANK[level] < RANK[profile.min_language_level] or used[at.period] >= profile.budget:
                cards.append(_as(card, CardStatus.EXPIRED, None))  # to the recap
                continue
            used[at.period] += 1
            shown.add(card.id)
            out = _as(card, CardStatus.SHOWN, at)
            cards.append(out)
            if template := TEMPLATE.get(card.moment_type):
                aired = _dead_ball(events, at)
                cues.append(_cue(out, CueKind.INSIGHT, template, events, meta, aired))
        elif card.id in shown:  # corrections pass the budget, to wherever the card went
            out = _as(card, card.status, at)
            cards.append(out)
            kind, template = CORRECTION[card.status]
            cues.append(_cue(out, kind, template, events, meta, _dead_ball(events, at)))
        else:
            cards.append(_as(card, card.status, None))  # the console still shows it
    return Schedule(goals(meta, events) + cards, cues)
