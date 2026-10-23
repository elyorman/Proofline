"""Broadcast cue: timed, machine-readable, one per insight revision."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def _ordered(self) -> "ShowAt":
        if self.not_after < self.not_before:
            raise ValueError(f"cue slot closes at {self.not_after} before it opens")
        return self


class Cue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    cue_id: str
    match_id: str
    insight_id: str | None = None
    insight_revision: int | None = Field(default=None, ge=1)
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

    @model_validator(mode="after")
    def _names_its_insight(self) -> "Cue":
        if self.kind != CueKind.KEY_EVENT and (
            self.insight_id is None or self.insight_revision is None
        ):
            raise ValueError(f"a {self.kind} cue names its insight_id and insight_revision")
        return self
