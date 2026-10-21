"""Tactical script DSL: mechanisms, not labels (spec §7.1).

A script names two teams and their starting parameters, then interventions that
ramp a parameter to a new value from a match time. Cause-taxonomy names never
appear here; the mapping from an intervention to a cause lives in the suite's
sealed ground-truth file, which only eval/ reads.
"""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.clock import MatchClock, Window
from contracts.event import CoordinateShift

Side = Literal["home", "away"]
TEAM_PARAMS = frozenset({"press_height", "directness", "quality"})
PLAYER_PARAMS = frozenset({"stamina_decay"})
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
    player: str | None = None
    set: dict[str, float] = Field(min_length=1)

    @property
    def ramp_seconds(self) -> int:
        amount, unit = _RAMP_RE.match(self.ramp).groups()
        return int(amount) * (60 if unit == "m" else 1)

    @model_validator(mode="after")
    def _known_params(self) -> "Intervention":
        allowed = PLAYER_PARAMS if self.player else TEAM_PARAMS
        unknown = sorted(set(self.set) - allowed)
        if unknown:
            raise ValueError(f"{self.id}: unknown parameter(s) {unknown}")
        return self


class AmendmentFilter(BaseModel):
    """Events whose true start and end both lie in [y_min, y_max]; v1 shows them displaced."""

    model_config = ConfigDict(extra="forbid")

    type: str
    team: Side
    window: Window
    y_min: float = Field(default=0, ge=0, le=68)
    y_max: float = Field(default=68, ge=0, le=68)


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
