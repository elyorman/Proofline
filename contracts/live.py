"""A question asked live on the public link (spec §8.2 "Why?", §12.2 Run live): the job the
API runs for it, and what the page polls while it runs.

A job reports its stages as they happen: the Lead states the premise, code tests it, and a
premise that holds goes through the same investigation, Verifier and follow-up as any
question, so the viewer watches each stage arrive.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.question import Answer, Question

LiveStageName = Literal[
    "framed",  # the Lead stated the premise, or found none
    "premise",  # code tested the premise against normal variation
    "preregistered",
    "tested",
    "cross_examined",
    "synthesized",
    "verified",  # the Verifier passed or rejected the card
]


class LiveStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: LiveStageName
    at_ms: int = Field(ge=0, description="wall clock when it was reached")
    note: str = Field(default="", description="what code recorded at that stage")


class LiveJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    question: Question
    status: Literal["queued", "running", "done", "failed"]
    stages: list[LiveStage] = Field(default_factory=list)
    answer: Answer | None = None
    error: str | None = Field(default=None, description="why the job failed, for the viewer")
    trace_id: str | None = Field(default=None, description="its OpenTelemetry trace, if traced")
    created_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _outcome(self) -> "LiveJob":
        if (self.status == "done") != (self.answer is not None):
            raise ValueError("a job has an answer exactly when it is done")
        if (self.status == "failed") != (self.error is not None):
            raise ValueError("a job has an error exactly when it failed")
        if self.answer is not None and self.answer.question != self.question:
            raise ValueError("the answer is to the job's own question")
        return self
