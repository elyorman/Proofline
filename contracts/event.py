"""Match event contract. Every event is versioned; amendments bump `version`."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0


class EventType(StrEnum):
    PASS = "pass"
    CARRY = "carry"
    DRIBBLE = "dribble"
    SHOT = "shot"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    CLEARANCE = "clearance"
    PRESSURE = "pressure"
    DUEL = "duel"
    FOUL = "foul"
    CARD = "card"
    SUBSTITUTION = "substitution"
    POSSESSION_CHANGE = "possession_change"
    SET_PIECE = "set_piece"
    GOAL = "goal"
    SPRINT = "sprint"
    PERIOD_START = "period_start"
    PERIOD_END = "period_end"


class Outcome(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    WON = "won"
    LOST = "lost"
    ON_TARGET = "on_target"
    OFF_TARGET = "off_target"
    BLOCKED = "blocked"
    GOAL = "goal"
    NA = "na"


class Point(BaseModel):
    x: float = Field(ge=0, le=PITCH_LENGTH_M)
    y: float = Field(ge=0, le=PITCH_WIDTH_M)


class MatchClock(BaseModel):
    """Match time as period + seconds since period start, e.g. 2nd half 18:12."""

    period: Literal[1, 2] = 1
    seconds: float = Field(ge=0)

    @property
    def minute(self) -> int:
        base = 0 if self.period == 1 else 45 * 60
        return int((base + self.seconds) // 60)

    def __str__(self) -> str:
        base = 0 if self.period == 1 else 45 * 60
        total = int(base + self.seconds)
        return f"{total // 60:02d}:{total % 60:02d}"

    @classmethod
    def parse(cls, text: str) -> "MatchClock":
        mm, ss = text.split(":")
        total = int(mm) * 60 + int(ss)
        if total >= 45 * 60:
            return cls(period=2, seconds=total - 45 * 60)
        return cls(period=1, seconds=total)


class PassQualifiers(BaseModel):
    distance_m: float = Field(ge=0)
    ball_speed_kmh: float = Field(ge=0)
    pressure_on_passer: float = Field(ge=0, le=1)
    receiver_id: str | None = None


class ShotQualifiers(BaseModel):
    shot_speed_kmh: float = Field(ge=0)
    distance_m: float = Field(ge=0)
    angle_deg: float = Field(ge=0, le=180)
    defenders_in_cone: int = Field(ge=0)


class Event(BaseModel):
    event_id: str
    version: int = Field(default=1, ge=1)
    match_id: str
    clock: MatchClock
    wall_clock_ms: int = Field(ge=0)
    type: EventType
    team: str
    player_id: str | None = None
    position: str | None = None
    start: Point | None = None
    end: Point | None = None
    outcome: Outcome = Outcome.NA
    body_part: str | None = None
    zone: str | None = None
    pass_q: PassQualifiers | None = None
    shot_q: ShotQualifiers | None = None
    qualifiers: dict[str, str | float | int | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _qualifiers_match_type(self) -> "Event":
        if self.type == EventType.PASS and self.pass_q is None:
            raise ValueError("pass events require pass_q")
        if self.type == EventType.SHOT and self.shot_q is None:
            raise ValueError("shot events require shot_q")
        return self


class TrackingSample(BaseModel):
    match_id: str
    clock: MatchClock
    player_id: str
    team: str
    position: Point
    speed_kmh: float = Field(ge=0)
    cumulative_distance_m: float = Field(ge=0)


class EventAmendment(BaseModel):
    """A batch amendment: re-attribute or re-locate a block of events."""

    amendment_id: str
    match_id: str
    at: MatchClock
    event_ids: list[str] = Field(min_length=1)
    change: dict[str, str | float | int | bool]
    reason: str
