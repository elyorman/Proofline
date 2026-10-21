"""Match event contract. Every event is versioned; amendments bump `version`.

Coordinates are the truth, in the acting team's attacking frame: x=0 is its own
goal line and x=105 the opponent's; y=0 is the left touchline and y=68 the right,
looking towards the opponent's goal. Tracking samples use the player's own team
frame. Pitch zones are derived from x/y by the State Builder; an amendment that
relocates events changes x/y.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from contracts.clock import MatchClock

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


class EventRef(BaseModel):
    """An event at a specific version, as read by a tool call."""

    event_id: str
    version: int = Field(ge=1)

    model_config = {"frozen": True}


class TrackingSample(BaseModel):
    """Not stored in Cosmos: kept in Blob or in memory per match and reduced
    to per-window aggregates by the State Builder."""

    match_id: str
    clock: MatchClock
    player_id: str
    team: str
    position: Point
    speed_kmh: float = Field(ge=0)
    cumulative_distance_m: float = Field(ge=0)


class CoordinateShift(BaseModel):
    """Relocate events by a delta in metres; the usual provider re-sync."""

    dx_m: float = 0.0
    dy_m: float = 0.0


class EventAmendment(BaseModel):
    """A batch amendment: re-attribute or re-locate a block of events.

    Exactly one of `shift` or `set` applies to every event in `event_ids`,
    and each affected event's `version` is incremented.
    """

    amendment_id: str
    match_id: str
    at: MatchClock
    event_ids: list[str] = Field(min_length=1)
    shift: CoordinateShift | None = None
    set: dict[str, str | float | int | bool] | None = None
    reason: str

    @model_validator(mode="after")
    def _one_change(self) -> "EventAmendment":
        if (self.shift is None) == (self.set is None):
            raise ValueError("amendment needs exactly one of shift or set")
        return self
