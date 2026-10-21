"""What a State Builder tool returns, and how its evidence is tracked.

Every tool call stores one EvidenceSet (the event refs it read, including any it
then filtered out) and returns a ToolResult that points at it. The Verifier's
recompute re-runs the call over exactly that set at those versions. The
dependency index maps each event id to the evidence sets and cards that depend
on it, so the Correction Watcher finds dependents with one lookup.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, computed_field, model_validator

from contracts.clock import MatchClock, Window
from contracts.event import Event, EventRef
from contracts.taxonomy import BaselineScope, Metric


class ToolName(StrEnum):
    """The MCP tool catalog (spec §8.1)."""

    METRIC = "metric"
    COMPARE = "compare"
    BASELINE = "baseline"
    EVENTS = "events"
    SHAPE = "shape"
    PLAYER_LOAD = "player_load"
    GAME_STATE = "game_state"
    DISTRIBUTION = "distribution"


REQUIRED_FIELDS: dict[ToolName, tuple[str, ...]] = {
    ToolName.METRIC: ("metric", "subject", "window", "value"),
    ToolName.COMPARE: ("metric", "subject", "window", "value", "compared_with", "effect_size"),
    ToolName.BASELINE: ("metric", "subject", "baseline"),
    ToolName.EVENTS: ("window",),
    ToolName.SHAPE: ("subject", "window", "values"),
    ToolName.PLAYER_LOAD: ("subject", "window", "values"),
    ToolName.GAME_STATE: ("at", "values"),
    ToolName.DISTRIBUTION: ("metric", "subject", "window", "value", "std"),
}


class EvidenceSet(BaseModel):
    evidence_set_id: str
    match_id: str
    data_version: str
    events: list[EventRef] = Field(default_factory=list)

    @property
    def event_ids(self) -> set[str]:
        return {e.event_id for e in self.events}


class BaselineValue(BaseModel):
    scope: BaselineScope
    value: float
    n_events: int = Field(ge=0)
    evidence_set_id: str | None = Field(
        default=None, description="None for season_average, which comes from a static file"
    )


class WindowValue(BaseModel):
    """The second window of a `compare` call; its events are in the call's evidence set."""

    window: Window
    value: float
    n_events: int = Field(ge=0)


class ToolResult(BaseModel):
    """One result shape for the whole catalog; REQUIRED_FIELDS says what each tool fills."""

    tool_call_id: str
    tool: ToolName
    match_id: str
    metric: Metric | None = None
    subject: str | None = Field(default=None, description="team, unit or player; not game_state")
    window: Window | None = None
    at: MatchClock | None = Field(default=None, description="game_state only")
    value: float | None = None
    values: dict[str, float] = Field(
        default_factory=dict, description="named numbers from shape, player_load, game_state"
    )
    baseline: BaselineValue | None = None
    compared_with: WindowValue | None = None
    effect_size: float | None = None
    std: float | None = Field(default=None, ge=0, description="from distribution, for sigma")
    events: list[Event] = Field(default_factory=list, description="events tool, at their versions")
    n_events: int = Field(ge=0)
    evidence_set_id: str
    computed_at_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _fields_for_tool(self) -> "ToolResult":
        missing = [f for f in REQUIRED_FIELDS[self.tool] if getattr(self, f) in (None, {})]
        if missing:
            raise ValueError(f"{self.tool} result needs {', '.join(missing)}")
        return self


class DependencyEntry(BaseModel):
    """Partition key: event_id. One document per event with dependents."""

    event_id: str
    match_id: str
    evidence_set_ids: list[str] = Field(default_factory=list)
    card_ids: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def id(self) -> str:
        """Cosmos document id; unique even when two matches reuse an event id."""
        return f"{self.match_id}:{self.event_id}"
