"""Viewer profile: changes what is shown and how it is said, never the facts."""

from enum import StrEnum

from pydantic import BaseModel, Field

from contracts.taxonomy import LanguageLevel, Metric


class Expertise(StrEnum):
    CASUAL = "casual"
    CORE = "core"
    ANALYST = "analyst"


class ViewMode(StrEnum):
    CASUAL = "casual"
    DATA = "data"
    PLAYER_FOCUS = "player_focus"
    SINGLE_METRIC = "single_metric"  # stretch


DEFAULT_BUDGET: dict[Expertise, int] = {
    Expertise.CASUAL: 3,
    Expertise.CORE: 6,
    Expertise.ANALYST: 12,
}


class Profile(BaseModel):
    profile_id: str
    expertise: Expertise = Expertise.CASUAL
    language: str = Field(default="en", pattern=r"^[a-z]{2}$")
    favorite_club: str | None = None
    favorite_players: list[str] = Field(default_factory=list)
    mode: ViewMode = ViewMode.CASUAL
    focus_metric: Metric | None = None
    attention_budget_per_half: int | None = Field(default=None, ge=0)
    min_language_level: LanguageLevel = LanguageLevel.MEASURED
    tone: str = "warm"

    @property
    def budget(self) -> int:
        return (
            self.attention_budget_per_half
            if self.attention_budget_per_half is not None
            else DEFAULT_BUDGET[self.expertise]
        )
