import asyncio
import json
import time
from pathlib import Path

from agents.cross_exam import Counters
from agents.llm import Usage
from agents.outputs import Proposal, Ranking, Registration
from agents.verifier.semantic import SemanticReport, SentenceCheck
from contracts.eval_run import Variant
from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim
from orchestration.batch import run_batch

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


class ByRole:
    def __init__(self, answers):
        self.answers, self.asked = answers, 0

    async def ask(self, role, instructions, prompt, schema):
        self.asked += 1
        return self.answers[role, schema.__name__], Usage(10, 5)


PRESS = Proposal(
    cause="tactical.press_intensity_up",
    metric="pressure_rate",
    subject="Harbour City",
    direction="up",
    min_change=1.5,
    why="a higher press",
)
ANSWERS = {
    ("single", "Registration"): Registration(hypotheses=[PRESS]),
    ("single", "Counters"): Counters(counters=[]),
    ("single", "Ranking"): Ranking(
        outcome="explained", primary="hyp-single-01", secondary=[], why="held"
    ),
    ("verifier", "SemanticReport"): SemanticReport(  # the claim, casual and analyst text
        sentences=[SentenceCheck(sentence="s", entailed=True, overstated=False, reason="ok")] * 3
    ),
}


def test_a_batch_writes_every_case_of_every_match_and_resumes(tmp_path):
    sim = MatchSim(load_script(M01))
    write_match(sim, sim.run(), tmp_path / "data" / "m01")
    model = ByRole(ANSWERS)
    out = tmp_path / "runs"
    before = int(time.time() * 1000)
    (written,) = asyncio.run(
        run_batch(tmp_path / "data", Variant.B_SINGLE_AGENT, out, model, model)
    )
    doc = json.loads(written.read_text())
    assert doc["match_id"] == "m01" and doc["variant"] == "B"
    assert before <= doc["started_at_ms"] <= int(time.time() * 1000)  # for the flag-freeze check
    by_id = {c["case_id"]: c for c in doc["cases"]}
    press = by_id["case-m01-063-pressure_shift"]
    assert press["published"] and press["card"]["subject"]["team"] == "Harbour City"
    # Register, register again (its causes were all on one side), self-check, rank.
    assert press["tokens"] == [40, 20] and "error" not in press
    asked = model.asked
    asyncio.run(run_batch(tmp_path / "data", Variant.B_SINGLE_AGENT, out, model, model))
    assert model.asked == asked  # a finished match is not run again
