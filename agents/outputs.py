"""What the model answers, as plain structures. Code turns them into contracts objects and
rejects anything that does not validate, with the reason, so a vague answer never reaches
a test."""

from pydantic import BaseModel, Field


class Proposal(BaseModel):
    cause: str = Field(
        description="a cause class from the taxonomy, e.g. tactical.press_intensity_up"
    )
    metric: str = Field(description="one of the measurable metrics")
    subject: str = Field(description="a team, 'Team.unit', or a player id")
    direction: str = Field(description="'up' or 'down'")
    min_change: float = Field(description="the smallest change that would support the cause")
    why: str = Field(description="one short sentence: why this cause would move this metric")


class Registration(BaseModel):
    hypotheses: list[Proposal]


class Ranking(BaseModel):
    outcome: str = Field(description="'explained', 'other' or 'none'")
    primary: str | None = Field(description="hypothesis id of the primary cause, or null")
    secondary: list[str] = Field(description="hypothesis ids of secondary causes")
    why: str = Field(description="one short sentence")
