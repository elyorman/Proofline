"""Variant A: three domain agents, cross-examination and synthesis as an Agent Framework
workflow, replayed or scripted; nothing here calls a live model."""

import asyncio
from pathlib import Path

import pytest

from agents.cross_exam import Counter, Counters
from agents.llm import Replay, Usage
from agents.outputs import Proposal, Ranking, Registration
from agents.verifier.semantic import SemanticReport, SentenceCheck
from contracts.case import CaseStage
from contracts.eval_run import Variant
from contracts.taxonomy import AgentRole, Cause
from detector.cusum import detect
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from orchestration.case import run_case
from orchestration.workflow import investigate
from state.tools import Feed

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cases" / "m01-063-A"


@pytest.fixture(scope="module")
def m01():
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    events = sim.run()
    feed = Feed(meta=match_meta(sim), events=events, data_version="feed-1")
    case = next(c for c in detect(feed.meta, events) if c.window.end.minute == 63)
    return feed, case


class ByRole:
    """A scripted model that answers by role and schema, whatever order agents run in."""

    def __init__(self, answers):
        self.answers = answers

    async def ask(self, role, instructions, prompt, schema):
        return self.answers[role, schema.__name__], Usage(1, 1)


PRESS = Proposal(
    cause="tactical.press_intensity_up",
    metric="pressure_rate",
    subject="Harbour City",
    direction="up",
    min_change=0.15,
    why="a higher press",
)
TIRED = Proposal(
    cause="physical.unit_fatigue",
    metric="sprint_count",
    subject="Northvale.midfield",
    direction="down",
    min_change=0.5,
    why="tired legs",
)
CONTROL = Counter(
    hypothesis_id="hyp-tactics-01",
    kind="control",
    subject="Northvale",
    compare_to="first_half",
    min_change=0.15,
    reason="is the press shared?",
)
SCRIPT = {
    ("tactics", "Registration"): Registration(hypotheses=[PRESS]),
    ("physical", "Registration"): Registration(hypotheses=[TIRED]),
    ("game_state", "Registration"): Registration(hypotheses=[]),
    ("physical", "Counters"): Counters(counters=[CONTROL]),
    ("game_state", "Counters"): Counters(counters=[]),
    ("synthesis", "Ranking"): Ranking(
        outcome="explained", primary="hyp-tactics-01", secondary=[], why="the press held"
    ),
    ("verifier", "SemanticReport"): SemanticReport(
        sentences=[SentenceCheck(sentence="s", entailed=True, overstated=False, reason="ok")]
    ),
}


def test_the_demo_press_survives_cross_examination_from_recorded_exchanges(m01):
    feed, case = m01
    replay = Replay(FIXTURES)
    outcome = asyncio.run(run_case(Variant.A_PROOFLINE, replay, replay, case, feed))
    finding, card = outcome.finding, outcome.verdict.card
    assert finding.agents == [AgentRole.TACTICS, AgentRole.PHYSICAL, AgentRole.GAME_STATE]
    assert finding.exams and all(e.result == "holds" for e in finding.exams)
    assert [c.stage for c in finding.checkpoints] == [
        CaseStage.PREREGISTERED,
        CaseStage.TESTED,
        CaseStage.CROSS_EXAMINED,
        CaseStage.SYNTHESIZED,
    ]
    assert card.status == "verified" and card.primary_cause.cause == Cause.PRESS_INTENSITY_UP
    assert card.subject.team == "Harbour City" and not finding.recovered


def test_a_control_on_the_other_team_is_run_and_scored_by_code(m01):
    feed, case = m01
    finding = asyncio.run(investigate(ByRole(SCRIPT), case, feed))
    (exam,) = finding.exams
    assert exam.challenger == AgentRole.PHYSICAL and exam.counter_prediction.subject == "Northvale"
    assert exam.hypothesis_change == pytest.approx(0.513, abs=1e-3)
    assert exam.result == "holds"  # Northvale did not press harder too
    assert finding.ranking.primary == "hyp-tactics-01"


def test_an_agent_stopped_once_is_retried_from_its_checkpoint(m01):
    feed, case = m01
    finding = asyncio.run(investigate(ByRole(SCRIPT), case, feed, {AgentRole.PHYSICAL: 1}))
    assert finding.recovered and AgentRole.PHYSICAL in finding.agents
    assert any(h.agent == AgentRole.PHYSICAL for h in finding.hypotheses)


def test_an_agent_that_stays_down_is_left_out_and_the_case_still_completes(m01):
    feed, case = m01
    outcome = asyncio.run(
        run_case(
            Variant.A_PROOFLINE,
            ByRole(SCRIPT),
            ByRole(SCRIPT),
            case,
            feed,
            {AgentRole.PHYSICAL: 2},
        )
    )
    finding = outcome.finding
    assert finding.recovered and finding.agents == [AgentRole.TACTICS, AgentRole.GAME_STATE]
    assert all(c.agents_failed == [AgentRole.PHYSICAL] for c in finding.checkpoints)
    assert not finding.exams and outcome.verdict.card.status == "verified"
