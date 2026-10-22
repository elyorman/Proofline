"""Tactical script DSL: mechanisms, not labels (spec §7.1).

A script names two teams and their starting parameters, then interventions that
ramp a parameter to a new value from a match time. Cause-taxonomy names never
appear here; the mapping from an intervention to a cause lives in the suite's
sealed ground-truth file, which only eval/ reads.

Interventions on the same parameter compose in time order, so the later one wins;
a ramp still running at half-time completes at the start of the second half.
"""

import math
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.clock import MatchClock, Window
from contracts.event import CoordinateShift, EventType

Side = Literal["home", "away"]
TEAM_PARAMS = frozenset({"press_height", "directness", "quality"})
PLAYER_PARAMS = frozenset({"stamina_decay"})
PARAM_RANGES = {
    "press_height": (0.0, 1.0),
    "directness": (0.0, 1.0),
    "quality": (0.0, 1.0),
    "stamina_decay": (0.0, 5.0),
}
PLAYER_ID = r"^[A-Z]{2}-(0[1-9]|1[01])$"  # one of the 11 starters in engine.teams
AMENDABLE = frozenset({EventType.PASS, EventType.CARRY, EventType.DRIBBLE})
_RAMP_RE = re.compile(r"^(\d+)(m|s)$")


class TeamSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    code: str = Field(pattern=r"^[A-Z]{2}$", description="player id prefix, e.g. HC")
    formation: Literal["4-3-3", "4-2-3-1", "4-4-2", "3-5-2"] = "4-3-3"
    press_height: float = Field(default=0.5, ge=0, le=1)
    directness: float = Field(default=0.08, ge=0, le=1)
    quality: float = Field(default=0.5, ge=0, le=1)


class Intervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    at: MatchClock
    ramp: str = Field(default="0m", pattern=_RAMP_RE.pattern)
    team: Side
    player: str | None = Field(default=None, pattern=PLAYER_ID)
    set: dict[str, float] = Field(min_length=1)

    @property
    def ramp_seconds(self) -> int:
        amount, unit = _RAMP_RE.match(self.ramp).groups()
        return int(amount) * (60 if unit == "m" else 1)

    @model_validator(mode="after")
    def _known_params(self) -> "Intervention":
        level = "player" if self.player else "team"
        allowed = PLAYER_PARAMS if self.player else TEAM_PARAMS
        unknown = sorted(set(self.set) - allowed)
        if unknown:
            raise ValueError(
                f"{self.id}: {unknown} not valid {level} parameter(s); use {sorted(allowed)}"
            )
        for key, value in self.set.items():
            lo, hi = PARAM_RANGES[key]
            if not lo <= value <= hi:  # also rejects NaN
                raise ValueError(f"{self.id}: {key}={value} outside [{lo}, {hi}]")
        return self


class AmendmentFilter(BaseModel):
    """Events whose true start and end both lie in [y_min, y_max]; v1 shows them displaced."""

    model_config = ConfigDict(extra="forbid")

    types: list[EventType] = Field(min_length=1)
    team: Side
    window: Window
    y_min: float = Field(default=0, ge=0, le=68)
    y_max: float = Field(default=68, ge=0, le=68)

    @model_validator(mode="after")
    def _band(self) -> "AmendmentFilter":
        if not set(self.types) <= AMENDABLE:
            refused = ", ".join(sorted(set(self.types) - AMENDABLE))
            raise ValueError(
                f"{refused} cannot be amended: amendments relocate "
                f"{', '.join(sorted(AMENDABLE))} events only"
            )
        if self.y_min > self.y_max:
            raise ValueError(f"y_min {self.y_min} is above y_max {self.y_max}")
        return self


class AmendmentBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filter: AmendmentFilter
    shift: CoordinateShift


class AmendmentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    at: MatchClock
    batch: AmendmentBatch
    reason: str

    @model_validator(mode="after")
    def _coherent(self) -> "AmendmentSpec":
        band, dy = self.batch.filter, self.batch.shift.dy_m
        if self.batch.shift.dx_m != 0:
            raise ValueError(f"{self.id}: shifts are lateral only, so dx_m must be 0")
        if not math.isfinite(dy) or dy == 0:
            raise ValueError(f"{self.id}: dy_m must be a finite, non-zero shift")
        if self.at < band.window.end:
            raise ValueError(f"{self.id}: the correction at {self.at} comes before its window ends")
        if band.y_min - dy < 0 or band.y_max - dy > 68:  # v1 shows events at true y - dy
            raise ValueError(f"{self.id}: the displaced v1 band leaves the pitch")
        return self


class MatchScript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    seed: int = Field(ge=0)
    teams: dict[Side, TeamSpec]
    scripts: list[Intervention] = Field(default_factory=list)
    amendments: list[AmendmentSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "MatchScript":
        if set(self.teams) != {"home", "away"}:
            raise ValueError("a script needs exactly a home and an away team")
        if self.teams["home"].code == self.teams["away"].code:
            raise ValueError("home and away need different player-id codes")
        ids = [s.id for s in self.scripts] + [a.id for a in self.amendments]
        if len(ids) != len(set(ids)):
            raise ValueError("script and amendment ids must be unique")
        for s in self.scripts:
            if s.player and not s.player.startswith(f"{self.teams[s.team].code}-"):
                raise ValueError(f"{s.id}: player {s.player} is not on the {s.team} team")
        return self


def load_script(path: str | Path) -> MatchScript:
    return MatchScript.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
