"""Broadcast cue: timed, machine-readable, one per insight revision."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from contracts.taxonomy import LanguageLevel


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
    not_before: str
    not_after: str


class OverlayTemplate(StrEnum):
    PLAYER_NAME_TAG = "player_name_tag"
    SPEED_DISTANCE_TAG = "speed_distance_tag"
    SHOT_SPEED = "shot_speed"
    PASS_DIFFICULTY = "pass_difficulty"
    PRESSURE_SHIFT_BAR = "pressure_shift_bar"
    MOMENTUM_STRIP = "momentum_strip"
    CONTROL_CHAOS_GAUGE = "control_chaos_gauge"
    SHAPE_CHANGE = "shape_change"
    FATIGUE_WARNING = "fatigue_warning"
    MILESTONE_BADGE = "milestone_badge"
    UPDATE_BANNER = "update_banner"
    WITHDRAWAL_BANNER = "withdrawal_banner"


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
