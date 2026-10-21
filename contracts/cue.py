"""Broadcast cue: timed, machine-readable, one per insight revision."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from contracts.clock import MatchClock
from contracts.taxonomy import LanguageLevel, OverlayTemplate


class CueKind(StrEnum):
    INSIGHT = "insight"
    KEY_EVENT = "key_event"
    UPDATE = "update"
    WITHDRAWAL = "withdrawal"


class CueStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    HELD = "held"
    KILLED = "killed"
    AIRED = "aired"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ShowAt(BaseModel):
    mode: Literal["immediate", "next_dead_ball"]
    not_before: MatchClock
    not_after: MatchClock


class Cue(BaseModel):
    cue_id: str
    match_id: str
    insight_id: str | None = None
    insight_revision: int | None = None
    kind: CueKind
    template: OverlayTemplate
    priority: Literal["low", "normal", "high"] = "normal"
    show_at: ShowAt
    duration_s: int = Field(ge=1)
    fields: dict[str, str | float | int]
    locale: str = "en"
    language_level: LanguageLevel | None = None
    status: CueStatus = CueStatus.PENDING
    decided_by: Literal["auto", "producer"] | None = None
