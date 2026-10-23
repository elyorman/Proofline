"""One message on the match feed (Event Hubs), as the Match Clock sends it and ingest reads it.

A run opens with the match's metadata, then delivers its events in clock order. Every
message carries the run id, so a reader can skip what earlier runs left on the hub.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from contracts.event import Event
from contracts.meta import MatchMeta


class FeedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    match_id: str
    kind: Literal["meta", "event"]
    meta: MatchMeta | None = None
    event: Event | None = None

    @model_validator(mode="after")
    def _one_body(self) -> "FeedMessage":
        body = self.meta if self.kind == "meta" else self.event
        other = self.event if self.kind == "meta" else self.meta
        if body is None or other is not None:
            raise ValueError(f"a {self.kind} message carries its {self.kind} and nothing else")
        if body.match_id != self.match_id:
            raise ValueError("the message and its body name different matches")
        return self
