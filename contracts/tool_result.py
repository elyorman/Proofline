"""What a State Builder tool returns, and how its evidence is tracked.

Every tool call stores one EvidenceSet (the event refs it read) and returns a
ToolResult that points at it. The dependency index maps each event id to the
evidence sets and cards that depend on it, so the Correction Watcher finds
dependents with one lookup.
"""

from pydantic import BaseModel, Field

from contracts.clock import Window
from contracts.event import EventRef
from contracts.taxonomy import BaselineScope, Metric


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


class ToolResult(BaseModel):
    tool_call_id: str
    tool: str = Field(description="metric | compare | baseline | events | shape | ...")
    match_id: str
    metric: Metric | None = None
    subject: str
    window: Window | None = None
    value: float | None = None
    baseline: BaselineValue | None = None
    std: float | None = Field(default=None, ge=0, description="from distribution, for sigma")
    n_events: int = Field(ge=0)
    evidence_set_id: str
    computed_at_ms: int = Field(ge=0)


class DependencyEntry(BaseModel):
    """Partition key: event_id. One document per event with dependents."""

    event_id: str
    match_id: str
    evidence_set_ids: list[str] = Field(default_factory=list)
    card_ids: list[str] = Field(default_factory=list)
