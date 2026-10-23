"""Who a metric is about: a team ("Northvale"), one of its units ("Northvale.defence") or a
player ("NV-04"), resolved through the match's roster rather than by reading the string."""

from dataclasses import dataclass
from typing import get_args

from contracts.meta import MatchMeta, Unit


@dataclass(frozen=True)
class Subject:
    team: str
    unit: str | None = None
    player_id: str | None = None

    @property
    def is_team(self) -> bool:
        return self.unit is None and self.player_id is None


def resolve(meta: MatchMeta, subject: str) -> Subject:
    for team in meta.teams.values():
        if subject == team.name:
            return Subject(team.name)
        unit = subject.removeprefix(f"{team.name}.")
        if unit != subject and unit in get_args(Unit):
            return Subject(team.name, unit=unit)
        if any(p.player_id == subject for p in team.players):
            return Subject(team.name, player_id=subject)
    raise ValueError(f"{subject!r} is not a team, unit or player in {meta.match_id}")


def opponent(meta: MatchMeta, team: str) -> str:
    return next(t.name for t in meta.teams.values() if t.name != team)


def players_of(meta: MatchMeta, subject: Subject) -> set[str]:
    """The player ids a subject covers."""
    if subject.player_id is not None:
        return {subject.player_id}
    team = next(t for t in meta.teams.values() if t.name == subject.team)
    return {p.player_id for p in team.players if subject.unit in (None, p.unit)}
