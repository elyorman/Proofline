"""A viewer's question about the match so far ("Why?", spec §8.2 and §9.1), and what it
assumes.

A question carries an assumption: "why are Northvale tiring?" assumes they are. Before anyone
investigates a cause, the Lead (in variant B, the single agent) states that assumption as a
premise: one measurable change since a minute. Code tests the premise against normal
variation; a question whose premise does not hold is answered with what did happen.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.card import InsightCard
from contracts.case_file import Persistence
from contracts.clock import MatchClock, Window
from contracts.eval_run import Variant
from contracts.prediction import Direction
from contracts.taxonomy import Cause, Metric

MIN_PREMISE_MINUTES = 5  # the shortest stretch of play a premise is measured over


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)
    match_id: str
    asked_at: MatchClock = Field(description="the moment the viewer asks, in the second half")
    text: str = Field(min_length=3, max_length=300)
    locale: Literal["en", "es"] = "en"

    @model_validator(mode="after")
    def _second_half(self) -> "Question":
        if self.asked_at.period != 2:
            raise ValueError("a question is measured against the first half, so it comes after it")
        return self


class Premise(BaseModel):
    """What a question assumes, as a change since a minute against the first half."""

    model_config = ConfigDict(extra="forbid")

    metric: Metric
    subject: str
    direction: Direction
    since: MatchClock

    @model_validator(mode="after")
    def _a_change(self) -> "Premise":
        if self.direction == Direction.FLAT:
            raise ValueError("a premise assumes a change")
        if self.since.period != 2:
            raise ValueError("a premise is a change since a second-half minute")
        return self

    def window(self, asked_at: MatchClock) -> Window:
        """The stretch of play the premise is measured over: from `since` to the question."""
        window = Window(start=self.since, end=asked_at)
        minutes = (asked_at.seconds_in_period - self.since.seconds_in_period) / 60
        if minutes < MIN_PREMISE_MINUTES:
            raise ValueError(
                f"a premise needs at least {MIN_PREMISE_MINUTES} minutes of play to measure"
            )
        return window


class Answer(BaseModel):
    """What a question got: its premise and how code found it, then the case's outcome and the
    card, or why there is none. The viewer's text comes from the Narrator, never a model."""

    model_config = ConfigDict(extra="forbid")

    question: Question
    variant: Variant
    premise: Premise | None = None
    premise_test: Persistence | None = None
    outcome: Literal["unanswerable", "premise_false", "explained", "other", "none"]
    reason: str
    card: InsightCard | None = Field(default=None, description="the verified card, if any")
    text: dict[str, str] = Field(description="the answer as the viewer reads it, by locale")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _one_story(self) -> "Answer":
        if (self.outcome == "unanswerable") != (self.premise is None):
            raise ValueError("a question is unanswerable exactly when it has no premise")
        tested = self.premise_test is not None and self.premise_test.holds
        if (self.outcome == "premise_false") == tested and self.outcome != "unanswerable":
            raise ValueError("the premise is false exactly when its test did not hold")
        if self.card is not None and self.outcome != "explained":
            raise ValueError("only an explained question carries a card")
        if set(self.text) != {"en", "es"}:
            raise ValueError("an answer is written in English and Spanish")
        return self


class PlainAnswer(BaseModel):
    """What a plain tool-using agent answered (the baseline of spec §11.2): one model with the
    State Builder's tools and the case budget, answering directly, with none of Proofline's
    checks. Measured only; never shown to a viewer."""

    model_config = ConfigDict(extra="forbid")

    question: Question
    happening: bool = Field(description="whether it says what the question assumes is happening")
    cause: Cause | None = Field(default=None, description="the cause it names, if any")
    team: str | None = None
    text: str = Field(description="its answer to the viewer, as it wrote it")
    tool_calls: int = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    @property
    def claims(self) -> bool:
        """It publishes a cause: it says the change is happening and names a class for it."""
        return self.happening and self.cause is not None and self.cause.domain != "fallback"
