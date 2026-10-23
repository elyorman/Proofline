"""What a feed says about a match before its first event: who plays.

Product code reads only this. It never carries the seed, which tells a suite match
from a decoy, the score, which the events deliver as they happen, or how long a half
ran, which only its period_end event says.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Side = Literal["home", "away"]
Unit = Literal["goalkeeper", "defence", "midfield", "attack"]


class RosterPlayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    name: str
    role: str = Field(description="position in the formation, e.g. RB or ST")
    unit: Unit


class TeamMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    code: str = Field(pattern=r"^[A-Z]{2}$", description="player id prefix, e.g. HC")
    formation: str
    players: list[RosterPlayer] = Field(min_length=11, max_length=11)

    @model_validator(mode="after")
    def _own_players(self) -> "TeamMeta":
        ids = [p.player_id for p in self.players]
        if len(set(ids)) != len(ids) or any(not i.startswith(f"{self.code}-") for i in ids):
            raise ValueError(f"{self.name}: player ids are unique and start with {self.code}-")
        return self


class MatchMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    teams: dict[Side, TeamMeta]

    @model_validator(mode="after")
    def _two_teams(self) -> "MatchMeta":
        if set(self.teams) != {"home", "away"}:
            raise ValueError("a match has a home and an away team")
        if self.teams["home"].name == self.teams["away"].name:
            raise ValueError("the two teams have different names")
        return self
