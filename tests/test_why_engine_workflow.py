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
from contracts.case_file import CaseFile
from contracts.eval_run import Variant
from contracts.taxonomy import AgentRole
from detector.cusum import detect
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from orchestration.case import case_file, run_case
from orchestration.workflow import AgentDown, investigate
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
    min_change=1.5,
    why="a higher press",
)
TIRED = Proposal(
    cause="physical.unit_fatigue",
    metric="sprint_count",
    subject="Northvale.midfield",
    direction="down",
    min_change=1.5,
    why="tired legs",
)
CONTROL = Counter(
    hypothesis_id="hyp-tactics-01",
    kind="control",
    metric=None,
    direction=None,
    subject="Northvale",
    min_change=1.5,
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
    ("verifier", "SemanticReport"): SemanticReport(  # the claim, casual and analyst text
        sentences=[SentenceCheck(sentence="s", entailed=True, overstated=False, reason="ok")] * 3
    ),
}


def test_the_demo_case_is_cross_examined_and_verified_from_recorded_exchanges(m01):
    # One recorded live run: the structure is pinned, that run's judgement is not.
    feed, case = m01
    replay = Replay(FIXTURES)
    outcome = asyncio.run(run_case(Variant.A_PROOFLINE, replay, replay, case, feed))
    finding, card = outcome.finding, outcome.verdict.card
    assert finding.agents == [AgentRole.TACTICS, AgentRole.PHYSICAL, AgentRole.GAME_STATE]
    assert finding.exams and all(
        e.challenger != e.hypothesis_id.split("-")[1] for e in finding.exams
    )
    assert [c.stage for c in finding.checkpoints] == [
        CaseStage.PREREGISTERED,
        CaseStage.TESTED,
        CaseStage.CROSS_EXAMINED,
        CaseStage.SYNTHESIZED,
    ]
    assert card.status == "verified" and not finding.recovered
    # Rival causes survived, so the case kept watching and settled on 68-83'.
    assert card.follow_up and outcome.followed.card.follow_up.status != "pending"


def test_a_control_on_the_other_team_is_run_and_scored_by_code(m01):
    feed, case = m01
    finding = asyncio.run(investigate(ByRole(SCRIPT), case, feed))
    (exam,) = finding.exams
    assert exam.challenger == AgentRole.PHYSICAL and exam.counter_prediction.subject == "Northvale"
    assert exam.hypothesis_change == pytest.approx(4.12, abs=0.01)  # in sd of ordinary play
    assert exam.result == "holds"  # Northvale did not press harder too
    assert finding.ranking.primary == "hyp-tactics-01"


def test_a_corollary_another_agent_asks_for_corroborates_the_press_on_the_card(m01):
    feed, case = m01
    corollary = Counter(
        hypothesis_id="hyp-tactics-01",
        kind="corollary",
        metric="long_ball_share",
        direction="up",
        subject="Northvale",
        min_change=1.5,
        reason="a real press forces the other side long",
    )
    script = SCRIPT | {("game_state", "Counters"): Counters(counters=[corollary])}
    outcome = asyncio.run(run_case(Variant.A_PROOFLINE, ByRole(script), ByRole(script), case, feed))
    exam = next(e for e in outcome.finding.exams if e.corollary)
    assert exam.challenger == AgentRole.GAME_STATE and exam.result == "holds"
    # 11% to 61% over 58-68', the window confirmation ran on to: 7.2 sd of ordinary play.
    assert exam.observed_change == pytest.approx(7.17, abs=0.01)
    card = outcome.verdict.card
    assert [(e.metric, e.subject) for e in card.evidence] == [
        ("pressure_rate", "Harbour City"),
        ("long_ball_share", "Northvale"),
    ]
    assert "game_state corollary on tactics's tactical.press_intensity_up: holds" in (
        card.investigation.cross_examination
    )
    assert card.status == "verified"


def test_the_case_file_holds_the_whole_investigation_for_the_console(m01):
    feed, case = m01
    corollary = Counter(
        hypothesis_id="hyp-tactics-01",
        kind="corollary",
        metric="long_ball_share",
        direction="up",
        subject="Northvale",
        min_change=1.5,
        reason="a real press forces the other side long",
    )
    script = SCRIPT | {("game_state", "Counters"): Counters(counters=[corollary])}
    outcome = asyncio.run(run_case(Variant.A_PROOFLINE, ByRole(script), ByRole(script), case, feed))
    filed = case_file(outcome, Variant.A_PROOFLINE)
    assert CaseFile.model_validate_json(filed.model_dump_json()) == filed
    assert filed.case.stage == "closed" and filed.case.card_id == outcome.verdict.card.id
    assert [h.agent for h in filed.hypotheses] == [AgentRole.TACTICS, AgentRole.PHYSICAL]
    assert {e.challenger for e in filed.cross_examinations} == {
        AgentRole.PHYSICAL,
        AgentRole.GAME_STATE,
    }
    assert any(e.corollary and e.result == "holds" for e in filed.cross_examinations)
    assert len(filed.tool_calls) == outcome.finding.tools.used
    assert filed.case.detected_at.minute == 63 and str(filed.case.window) == "58:00-68:00"
    assert [p.holds for p in filed.confirmation] == [True]  # 63-68' held the change
    assert any(c.tool == "game_state" and c.values for c in filed.tool_calls)
    assert [c.stage for c in filed.case.checkpoints][-1] == CaseStage.SYNTHESIZED


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
    finding, card = outcome.finding, outcome.verdict.card
    assert finding.recovered and finding.agents == [AgentRole.TACTICS, AgentRole.GAME_STATE]
    assert all(c.agents_failed == [AgentRole.PHYSICAL] for c in finding.checkpoints)
    assert "physical failed: AgentDown('physical stopped')" in finding.checkpoints[0].note
    assert not finding.exams and card.status == "verified"
    assert card.investigation.recovered_from_checkpoint  # the console reads it from the card


def test_a_case_every_agent_failed_is_an_error_not_a_finding(m01):
    feed, case = m01
    down = {a: 2 for a in (AgentRole.TACTICS, AgentRole.PHYSICAL, AgentRole.GAME_STATE)}
    with pytest.raises(AgentDown, match="every agent failed"):
        asyncio.run(investigate(ByRole(SCRIPT), case, feed, down))
