"""The State Builder's tool catalog as an MCP server (spec §8.1).

Each tool reads only what its match had delivered at the cutoff the orchestrator set for
the open case, never a clock an agent supplies, so no agent can measure a minute that has
not happened. Every call stores its evidence set before it returns its result.
"""

import argparse
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from contracts.clock import MatchClock, Window
from contracts.event import Event
from contracts.meta import MatchMeta
from contracts.taxonomy import BaselineScope, Metric
from contracts.tool_result import EvidenceSet
from state import tools
from state.tools import Call, Feed


class Source(Protocol):
    def feed(self, match_id: str) -> Feed: ...


class EvidenceSink(Protocol):
    def put(self, evidence: EvidenceSet) -> None: ...


@dataclass
class DirectorySource:
    """Matches as the engine writes them: <root>/<match_id>/events.jsonl and meta.json."""

    root: Path
    data_version: str = "feed-1"

    def feed(self, match_id: str) -> Feed:
        folder = Path(self.root) / match_id
        meta = MatchMeta.model_validate_json((folder / "meta.json").read_text(encoding="utf-8"))
        with (folder / "events.jsonl").open(encoding="utf-8") as f:
            events = [Event.model_validate_json(line) for line in f if line.strip()]
        return Feed(meta=meta, events=events, data_version=self.data_version)


@dataclass
class FeedSource:
    """Matches already in memory, such as one a case is running on."""

    feeds: dict[str, Feed]

    def feed(self, match_id: str) -> Feed:
        if match_id not in self.feeds:
            raise ValueError(f"no feed for {match_id}")
        return self.feeds[match_id]


@dataclass
class MemorySink:
    evidence: dict[str, EvidenceSet] = field(default_factory=dict)

    def put(self, evidence: EvidenceSet) -> None:
        self.evidence[evidence.evidence_set_id] = evidence


@contextmanager
def _refusals() -> Iterator[None]:
    """A request the State Builder refuses (a window that has not finished, an unknown
    subject, a match with no open case) reaches the agent as a tool error it can read."""
    try:
        yield
    except (ValueError, FileNotFoundError) as exc:
        raise ToolError(str(exc)) from exc


def build_server(source: Source, sink: EvidenceSink, cutoffs: dict[str, MatchClock]) -> MCPServer:
    """A server over `source`; `cutoffs` maps each match with an open case to its clock."""
    server = MCPServer(
        "proofline-state",
        instructions="Deterministic match statistics. Every number an agent cites comes "
        "from one of these tools; never compute or estimate one yourself.",
    )

    def call(match_id: str) -> Call:
        if match_id not in cutoffs:
            raise ValueError(f"no open case on {match_id}")
        return Call(
            tool_call_id=f"tc-{uuid.uuid4().hex[:12]}",
            as_of=cutoffs[match_id],
            now_ms=int(time.time() * 1000),
        )

    def done(result_and_evidence) -> dict[str, Any]:
        result, evidence = result_and_evidence
        sink.put(evidence)
        return result.model_dump(mode="json", exclude_none=True)

    @server.tool()
    def metric(match_id: str, name: Metric, subject: str, window: str) -> dict[str, Any]:
        """One metric over a finished window such as "58:00-63:00", for a team
        ("Northvale"), one of its units ("Northvale.defence") or a player ("NV-04")."""
        with _refusals():
            at, span = call(match_id), Window.model_validate(window)
            return done(tools.metric(source.feed(match_id), name, subject, span, at))

    @server.tool()
    def baseline(match_id: str, name: Metric, subject: str, scope: BaselineScope) -> dict[str, Any]:
        """The same metric over the first half or the match so far, to compare a window
        against."""
        with _refusals():
            at = call(match_id)
            return done(tools.baseline(source.feed(match_id), name, subject, scope, at))

    @server.tool()
    def game_state(match_id: str) -> dict[str, Any]:
        """The score at the case's clock, from the goals scored so far."""
        with _refusals():
            at = call(match_id)
            return done(tools.game_state(source.feed(match_id), at))

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the State Builder over MCP (stdio).")
    parser.add_argument("--data", default="data", help="folder of engine-written matches")
    parser.add_argument("--match", required=True, help="match id with an open case")
    parser.add_argument("--as-of", required=True, help="the case's clock, e.g. 63:00")
    args = parser.parse_args()
    cutoffs = {args.match: MatchClock.parse(args.as_of)}
    build_server(DirectorySource(Path(args.data)), MemorySink(), cutoffs).run("stdio")


if __name__ == "__main__":
    main()
