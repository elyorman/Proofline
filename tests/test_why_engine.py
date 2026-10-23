"""The Why Engine's single agent and Verifier, replayed from recorded model exchanges or
answered by a scripted model; nothing here calls a live model."""

import asyncio
from pathlib import Path

import pytest

from agents import narrator
from agents.investigation import Tools, cause_team, rank, register, run_test
from agents.llm import Recording, Replay, Usage
from agents.outputs import Proposal, Ranking, Registration
from agents.propose import propose
from agents.single import case_tools, investigate
from agents.verifier.checks import Record
from agents.verifier.semantic import SemanticReport, SentenceCheck
from agents.verifier.verify import verify
from contracts.eval_run import Variant
from contracts.prediction import Direction, Hypothesis
from contracts.taxonomy import AgentRole, CaseOutcome, Cause
from detector.cusum import detect
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from orchestration.case import run_case
from state.tools import MEASURED, Feed

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cases" / "m01-063-B"


@pytest.fixture(scope="module")
def m01():
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    events = sim.run()
    feed = Feed(meta=match_meta(sim), events=events, data_version="feed-1")
    case = next(c for c in detect(feed.meta, events) if c.window.end.minute == 63)
    return feed, case


class Scripted:
    """A model that gives queued answers, one per schema, in order."""

    def __init__(self, *answers):
        self.answers = list(answers)

    async def ask(self, role, instructions, prompt, schema):
        answer = self.answers.pop(0)
        assert isinstance(answer, schema), (answer, schema)
        return answer, Usage(1, 1)


def _proposal(**overrides):
    base = dict(
        cause="tactical.press_intensity_up",
        metric="pressure_rate",
        subject="Harbour City",
        direction="up",
        min_change=0.15,
        why="a higher press",
    )
    return Proposal(**base | overrides)


def test_the_single_agent_replays_its_demo_case_from_recorded_exchanges(m01):
    # Recorded live: with no table of what each cause moves, the single agent predicted a
    # press through midfield sprints, and nothing it registered survived its own test.
    feed, case = m01
    replay = Replay(FIXTURES)
    outcome = asyncio.run(run_case(Variant.B_SINGLE_AGENT, replay, replay, case, feed))
    finding = outcome.finding
    assert finding.ranking.outcome == CaseOutcome.NONE and outcome.verdict is None
    assert finding.tested and not any(t.supported for t in finding.tested)
    assert finding.tools.used <= case.tool_call_budget


def test_vague_or_misplaced_predictions_are_refused_before_testing(m01):
    feed, case = m01
    answer = Registration(
        hypotheses=[
            _proposal(),
            _proposal(metric="xg"),  # not measurable
            _proposal(subject="Harbour"),  # no such team
            _proposal(cause="physical.unit_fatigue"),  # outside the tactics domain
            _proposal(direction="flat"),  # a hypothesis predicts a change
        ]
    )
    score = {"home_goals": 1.0, "away_goals": 3.0}
    accepted, refused, _ = asyncio.run(
        register(Scripted(answer), AgentRole.TACTICS, case, feed.meta, score, 6)
    )
    assert [h.hypothesis_id for h in accepted] == ["hyp-tactics-01"]
    assert len(refused) == 4


def test_a_game_state_cause_needs_the_score_to_give_its_team_the_reason(m01):
    feed, case = m01
    chase = dict(cause="game_state.chasing_result", direction="up")
    answer = Registration(
        hypotheses=[
            _proposal(**chase),  # Harbour City trail 1-3
            _proposal(**chase, subject="Northvale"),
            _proposal(cause="game_state.protecting_lead", direction="down"),
        ]
    )
    score = {"home_goals": 1.0, "away_goals": 3.0}
    accepted, refused, _ = asyncio.run(
        register(Scripted(answer), AgentRole.GAME_STATE, case, feed.meta, score, 3)
    )
    assert [h.prediction.subject for h in accepted] == ["Harbour City"]
    assert [r.reason for r in refused] == [
        "Northvale is not behind, so the score gives no reason for this cause",
        "Harbour City is not ahead, so the score gives no reason for this cause",
    ]


def _hypothesis(case, **prediction):
    base = dict(
        metric="pressure_rate",
        subject="Harbour City",
        window=case.window,
        compare_to="first_half",
        direction="up",
        min_change=0.15,
    )
    return Hypothesis(
        hypothesis_id="hyp-1",
        case_id=case.case_id,
        agent=AgentRole.SINGLE,
        taxonomy=Cause.PRESS_INTENSITY_UP,
        prediction=base | prediction,
    )


def test_code_judges_each_prediction_on_the_tools_within_the_budget(m01):
    feed, case = m01
    tools, _ = case_tools(case, feed)
    held = asyncio.run(run_test(tools, _hypothesis(case)))
    missed = asyncio.run(run_test(tools, _hypothesis(case, min_change=0.6)))
    assert held.supported and round(held.test.observed_change, 3) == 0.513
    assert not missed.supported and "claim of up by 0.6" in missed.test.reason
    spent = Tools(tools.server, case.match_id, budget=1)
    assert "spent" in asyncio.run(run_test(spent, _hypothesis(case))).test.reason


def test_code_judges_nothing_on_fewer_events_than_a_card_may_rest_on(m01):
    feed, case = m01
    tools, _ = case_tools(case, feed)
    # HC-09 sprinted once in 58-63'; a sprint speed needs three sprints.
    one_sprint = _hypothesis(
        case, metric="sprint_speed", subject="HC-09", direction="down", min_change=0.5
    )
    tested = asyncio.run(run_test(tools, one_sprint))
    assert not tested.supported
    assert tested.test.reason == "too little data: 1 events, fewer than the 3 a claim needs"


def test_a_ranking_that_names_nothing_real_falls_back_to_the_strongest_margin(m01):
    feed, case = m01
    tools, _ = case_tools(case, feed)
    survivors = [asyncio.run(run_test(tools, _hypothesis(case)))]
    made_up = Ranking(outcome="explained", primary="hyp-9", secondary=[], why="?")
    score = {"home_goals": 1.0, "away_goals": 3.0}
    ranking, _ = asyncio.run(
        rank(Scripted(made_up), AgentRole.SINGLE, case, feed.meta, score, survivors)
    )
    assert ranking.primary == "hyp-1" and "did not fit" in ranking.why
    none, _ = asyncio.run(rank(Scripted(), AgentRole.SINGLE, case, feed.meta, score, []))
    assert none.outcome == CaseOutcome.NONE


def test_a_press_seen_in_the_opponents_long_balls_is_the_pressing_teams(m01):
    feed, case = m01
    seen = _hypothesis(case, metric="long_ball_share", subject="Northvale", min_change=0.1)
    assert cause_team(feed.meta, seen) == "Harbour City"


def test_every_measured_change_can_be_narrated_in_both_languages():
    for metric in MEASURED:
        assert all(narrator.LABEL[metric])
        for direction in (Direction.UP, Direction.DOWN):
            assert all(narrator.CHANGE[metric, direction])


def _proposed(feed, case, survivor):
    answer = Registration(hypotheses=[survivor])
    ranking = Ranking(outcome="explained", primary="hyp-single-01", secondary=[], why="clear")
    finding = asyncio.run(investigate(Scripted(answer, ranking), case, feed))
    return finding, propose(finding, feed)


SOUND = SemanticReport(
    sentences=[SentenceCheck(sentence="s", entailed=True, overstated=False, reason="ok")] * 3
)


def test_the_verifier_catches_a_tampered_number_and_an_overstatement(m01):
    feed, case = m01
    finding, card = _proposed(feed, case, _proposal())
    record = Record.of(finding.tools.log, finding.evidence)
    passed = asyncio.run(verify(Scripted(SOUND), card, record, feed, [])).card
    assert passed.status == "verified"
    tampered = card.model_copy(
        update={"evidence": [card.evidence[0].model_copy(update={"value": 0.9})]}
    )
    rejected = asyncio.run(verify(Scripted(), tampered, record, feed, [])).card
    assert rejected.status == "rejected" and rejected.verification.recompute == "mismatch"
    overstated = SemanticReport(
        sentences=[SentenceCheck(sentence="s", entailed=True, overstated=True, reason="too sure")]
    )
    flagged = asyncio.run(verify(Scripted(overstated), card, record, feed, [])).card
    assert flagged.status == "rejected" and "too sure" in flagged.verification.rejection_reason


def test_card_text_lists_each_measurement_once_and_names_each_ruled_out_teams_own(m01):
    feed, case = m01
    answer = Registration(
        hypotheses=[
            _proposal(),
            _proposal(cause="game_state.chasing_result"),  # the same test as the press
            _proposal(cause="game_state.protecting_lead", subject="Northvale", direction="down"),
        ]
    )
    ranking = Ranking(
        outcome="explained", primary="hyp-single-01", secondary=["hyp-single-02"], why="clear"
    )
    finding = asyncio.run(investigate(Scripted(answer, ranking), case, feed))
    card = propose(finding, feed)
    assert len(card.evidence) == 1
    assert [r.team for r in card.rejected_alternatives] == ["Northvale"]
    record = Record.of(finding.tools.log, finding.evidence)
    verdict = asyncio.run(verify(Scripted(SOUND), card, record, feed, []))
    assert "Ruled out: Northvale protecting their lead." in verdict.card.variants["analyst"]["en"]


class Unanswering:
    async def ask(self, role, instructions, prompt, schema):
        raise ValueError(f"no {schema.__name__} in the reply")


def test_a_semantic_check_that_gives_no_answer_keeps_the_card_off_every_surface(m01):
    feed, case = m01
    finding, card = _proposed(feed, case, _proposal())
    record = Record.of(finding.tools.log, finding.evidence)
    verdict = asyncio.run(verify(Unanswering(), card, record, feed, []))
    assert verdict.card.status == "rejected" and verdict.report is None
    assert verdict.card.verification.semantic_check == "failed"
    assert "gave no answer" in verdict.card.verification.rejection_reason


def test_a_reply_with_no_answer_is_recorded_and_replayed_as_one(tmp_path):
    recorded = Recording(Unanswering(), tmp_path)
    with pytest.raises(ValueError, match="no SemanticReport"):
        asyncio.run(recorded.ask("verifier", "i", "p", SemanticReport))
    with pytest.raises(ValueError, match="no SemanticReport"):
        asyncio.run(Replay(tmp_path).ask("verifier", "i", "p", SemanticReport))


def test_a_seeded_false_number_in_the_text_fails_the_number_check(m01):
    feed, case = m01
    finding, card = _proposed(feed, case, _proposal())
    false_claim = card.model_copy(update={"claim": "Harbour City are pressing 0.95 higher."})
    record = Record.of(finding.tools.log, finding.evidence)
    verdict = asyncio.run(verify(Scripted(SOUND), false_claim, record, feed, []))
    assert verdict.card.status == "rejected"
    assert verdict.card.verification.number_check == "failed"
