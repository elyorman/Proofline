import asyncio
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from contracts.clock import MatchClock
from contracts.tool_result import ToolResult
from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim
from tools_server.server import DirectorySource, MemorySink, build_server

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    root = tmp_path_factory.mktemp("matches")
    sim = MatchSim(load_script(M01))
    write_match(sim, sim.run(), root / "m01")
    return root


def _call(server, tool, **arguments):
    result = asyncio.run(server.call_tool(tool, {"match_id": "m01", **arguments}))
    assert not result.is_error
    return ToolResult.model_validate(result.structured_content)


def test_agents_get_the_state_builders_numbers_with_their_evidence(data):
    sink = MemorySink()
    server = build_server(DirectorySource(data), sink, {"m01": MatchClock.parse("63:00")})
    tools = {t.name for t in asyncio.run(server.list_tools())}
    assert tools == {"metric", "baseline", "game_state"}
    press = _call(
        server, "metric", name="pressure_rate", subject="Harbour City", window="58:00-63:00"
    )
    first = _call(
        server, "baseline", name="pressure_rate", subject="Harbour City", scope="first_half"
    )
    score = _call(server, "game_state")
    assert (round(press.value, 2), press.n_events) == (0.83, 18)
    assert round(first.baseline.value, 2) == 0.32
    assert score.values == {"home_goals": 1.0, "away_goals": 3.0}  # 77:09 has not happened
    assert set(sink.evidence) == {r.evidence_set_id for r in (press, first, score)}


@pytest.mark.parametrize(
    "arguments,message",
    [
        (dict(window="63:00-68:00"), "has not finished at 63:00"),
        (dict(window="58:00-63:00", subject="Harbour"), "not a team, unit or player"),
        (dict(window="58:00-63:00", match_id="m02"), "no open case on m02"),
    ],
)
def test_an_agent_cannot_measure_past_its_case_or_outside_the_match(data, arguments, message):
    server = build_server(DirectorySource(data), MemorySink(), {"m01": MatchClock.parse("63:00")})
    request = {"match_id": "m01", "name": "pressure_rate", "subject": "Harbour City"} | arguments
    with pytest.raises(ToolError, match=message):
        asyncio.run(server.call_tool("metric", request))


def test_a_call_is_named_by_its_question_so_a_replay_names_it_the_same(data):
    def server(cutoff):
        return build_server(DirectorySource(data), MemorySink(), {"m01": MatchClock.parse(cutoff)})

    press = dict(name="pressure_rate", subject="Harbour City", window="58:00-63:00")
    first = _call(server("63:00"), "metric", **press)
    again = _call(server("63:00"), "metric", **press)
    assert first.tool_call_id == again.tool_call_id
    assert first.evidence_set_id == again.evidence_set_id
    other = _call(server("63:00"), "metric", **press | {"subject": "Northvale"})
    later = _call(server("64:00"), "metric", **press)
    assert len({first.tool_call_id, other.tool_call_id, later.tool_call_id}) == 3
