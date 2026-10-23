"""What a planted cause looks like, and the sealed record of what was planted (spec §7.1-7.3).

The observables of each plantable class are fixed here, before any script of that class
runs (spec §7.2). Ground truth records are written by the engine and read by `eval/`
alone; product code never opens the files (scripts/check_engine_isolation.py).
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from contracts.clock import MatchClock, Window
from contracts.eval_run import Split, Suite
from contracts.prediction import Direction
from contracts.taxonomy import Cause, Metric

SubjectRole = Literal["team", "opponent", "unit", "player"]


class CauseObservable(BaseModel):
    """An observable of a class: the metric, whose it is, and which way the class moves it."""

    model_config = {"frozen": True}

    metric: Metric
    subject: SubjectRole
    direction: Direction


def _obs(metric: Metric, subject: SubjectRole, direction: Direction) -> CauseObservable:
    return CauseObservable(metric=metric, subject=subject, direction=direction)


_UP, _DOWN = Direction.UP, Direction.DOWN

# The classes the Match Engine can plant, and what each moves. Classes missing here
# (block height, formation, flank, substitution, numerical change) have no mechanism
# yet and are never planted; an agent may still name them, and precision counts it.
CAUSE_OBSERVABLES: dict[Cause, tuple[CauseObservable, ...]] = {
    Cause.PRESS_INTENSITY_UP: (
        _obs(Metric.PRESSURE_RATE, "team", _UP),
        _obs(Metric.LONG_BALL_SHARE, "opponent", _UP),
    ),
    Cause.PRESS_INTENSITY_DOWN: (
        _obs(Metric.PRESSURE_RATE, "team", _DOWN),
        _obs(Metric.LONG_BALL_SHARE, "opponent", _DOWN),
    ),
    Cause.CHASING_RESULT: (
        _obs(Metric.PRESSURE_RATE, "team", _UP),
        _obs(Metric.LONG_BALL_SHARE, "team", _UP),
    ),
    Cause.PROTECTING_LEAD: (
        _obs(Metric.PRESSURE_RATE, "team", _DOWN),
        _obs(Metric.LONG_BALL_SHARE, "team", _UP),
    ),
    Cause.UNIT_FATIGUE: (
        _obs(Metric.SPRINT_COUNT, "unit", _DOWN),
        _obs(Metric.SPRINT_SPEED, "unit", _DOWN),
    ),
    Cause.PLAYER_FATIGUE: (
        _obs(Metric.SPRINT_COUNT, "player", _DOWN),
        _obs(Metric.SPRINT_SPEED, "player", _DOWN),
    ),
}


def _fills(role: SubjectRole, subject: str, team: str) -> bool:
    """Whether `subject` can be the `role` of a change planted on `team`."""
    if role == "team":
        return subject == team
    if role == "unit":
        return subject.startswith(f"{team}.")
    return subject != team and "." not in subject


class TruthObservable(BaseModel):
    metric: Metric
    subject: str = Field(min_length=1, description="team name, Team.unit, or player id")
    direction: Direction


class PlantedTruth(BaseModel):
    """What one suite match planted, or that it planted nothing (cause `none`)."""

    match_id: str
    cause: Cause
    team: str | None = None
    script_id: str | None = None
    started: MatchClock | None = Field(default=None, description="when the change began")
    window: Window | None = Field(default=None, description="where its effect is measured")
    observables: list[TruthObservable] = Field(default_factory=list)

    @model_validator(mode="after")
    def _complete(self) -> "PlantedTruth":
        planted = (self.team, self.script_id, self.started, self.window)
        if self.cause == Cause.NONE:
            if any(v is not None for v in planted) or self.observables:
                raise ValueError(f"{self.match_id}: a match with nothing planted names nothing")
            return self
        if self.cause not in CAUSE_OBSERVABLES:
            raise ValueError(f"{self.match_id}: {self.cause} cannot be planted")
        if any(v is None for v in planted):
            raise ValueError(f"{self.match_id}: a planted cause names its team, script and window")
        expected = [(o.metric, o.direction) for o in CAUSE_OBSERVABLES[self.cause]]
        if [(o.metric, o.direction) for o in self.observables] != expected:
            raise ValueError(f"{self.match_id}: observables must be {self.cause}'s, in order")
        roles = [o.subject for o in CAUSE_OBSERVABLES[self.cause]]
        for role, o in zip(roles, self.observables, strict=True):
            if not _fills(role, o.subject, self.team):
                raise ValueError(f"{self.match_id}: {o.subject} cannot be the {role} here")
        if self.window.start < self.started:
            raise ValueError(f"{self.match_id}: the window opens before the change began")
        return self


class GroundTruth(BaseModel):
    """The sealed answer key for one suite split."""

    suite: Suite
    split: Split
    entries: list[PlantedTruth] = Field(min_length=1)

    @model_validator(mode="after")
    def _fits_suite(self) -> "GroundTruth":
        if self.suite not in (Suite.PLANTED, Suite.DECOYS):
            raise ValueError(f"the {self.suite} suite has no planted ground truth")
        ids = [e.match_id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("each match appears once")
        nothing = [e.cause == Cause.NONE for e in self.entries]
        if self.suite == Suite.DECOYS and not all(nothing):
            raise ValueError("a decoy match plants nothing")
        if self.suite == Suite.PLANTED and any(nothing):
            raise ValueError("every planted-suite match plants a cause")
        return self
