"""The ambient layer as exported to surfaces: speed tags, pass badges, the momentum strip,
the control-vs-chaos gauge and the event ticker.

`ambient/` computes every value deterministically from a match's delivered events; no
model writes any of it, and a surface only formats it. Each item carries the match clock
from which it is known (`at`), so a replay shows it no earlier than it could have been
computed live.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.clock import MatchClock


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class LocalizedText(_Strict):
    """A rendered template in every viewer language."""

    en: str = Field(min_length=1)
    es: str = Field(min_length=1)


class SpeedTag(_Strict):
    """A sprint or a shot whose speed clears its threshold in `AmbientRules`."""

    kind: Literal["sprint", "shot"]
    event_id: str
    at: MatchClock
    team: str
    player_id: str
    speed_kmh: float = Field(ge=0)


class PassBadge(_Strict):
    """A completed pass whose difficulty clears `AmbientRules.badge_difficulty`."""

    event_id: str
    at: MatchClock
    team: str
    player_id: str
    receiver_id: str | None = None
    difficulty: int = Field(ge=0, le=100)
    distance_m: float = Field(ge=0)
    pressure_on_passer: float = Field(ge=0, le=1)


class MomentumPoint(_Strict):
    """One minute of the momentum strip: +1 is all home threat, -1 all away."""

    period: Literal[1, 2]
    minute: int = Field(ge=0, le=130, description="on-screen minute the bucket covers")
    at: MatchClock = Field(description="the end of the minute, when its value is known")
    home_threat: float = Field(ge=0)
    away_threat: float = Field(ge=0)
    value: float = Field(ge=-1, le=1)


class ControlPoint(_Strict):
    """The control-vs-chaos gauge over the window [since, at)."""

    since: MatchClock
    at: MatchClock
    actions: int = Field(ge=0, description="passes, carries and dribbles in the window")
    turnovers: int = Field(ge=0, description="possession changes in the window")
    spell: float | None = Field(default=None, ge=0, description="on-ball actions per possession")
    chaos: float | None = Field(default=None, ge=0, le=1, description="0 control, 1 chaos")

    @model_validator(mode="after")
    def _both_or_neither(self) -> "ControlPoint":
        if (self.spell is None) != (self.chaos is None):
            raise ValueError("a gauge reading has both spell and chaos, or neither")
        if not self.since < self.at:
            raise ValueError("the window starts before it ends")
        return self


TickerKind = Literal[
    "kick_off",
    "goal",
    "shot",
    "foul",
    "free_kick",
    "card",
    "substitution",
    "half_time",
    "second_half",
    "full_time",
    "pass_badge",
]


class TickerLine(_Strict):
    """A templated one-liner from `ambient/i18n/`; never model text."""

    event_id: str
    at: MatchClock
    kind: TickerKind
    team: str | None = None
    text: LocalizedText


class AmbientRules(_Strict):
    """The thresholds and windows the feed was computed with, for surfaces to state."""

    sprint_kmh: float = Field(gt=0)
    shot_kmh: float = Field(gt=0)
    badge_difficulty: int = Field(ge=0, le=100)
    momentum_half_life_min: float = Field(gt=0)
    control_window_min: int = Field(gt=0)
    control_min_actions: int = Field(gt=0)


class AmbientFeed(_Strict):
    match_id: str
    home: str
    away: str
    rules: AmbientRules
    speed_tags: list[SpeedTag]
    pass_badges: list[PassBadge]
    momentum: list[MomentumPoint]
    control: list[ControlPoint]
    ticker: list[TickerLine]

    @model_validator(mode="after")
    def _known_teams(self) -> "AmbientFeed":
        teams = {self.home, self.away}
        if len(teams) != 2:
            raise ValueError("home and away are different teams")
        named = [*self.speed_tags, *self.pass_badges, *(t for t in self.ticker if t.team)]
        if any(item.team not in teams for item in named):
            raise ValueError("every ambient item names one of the match's teams")
        return self
