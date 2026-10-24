"""Viewer questions: the Lead's framing, the premise test, the shared investigation, and the
question suite's scoring. Models are scripted; nothing here calls a live model."""

import asyncio
from pathlib import Path

import pytest

from agents.cross_exam import Counters
from agents.lead import frame
from agents.llm import Usage
from agents.outputs import Framing, Proposal, Ranking, Registration
from agents.verifier.semantic import SemanticReport, SentenceCheck
from contracts.eval_run import Variant
from contracts.question import Answer, Premise, Question
from contracts.taxonomy import AgentRole, Cause
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from eval.questions import keys, score
from orchestration.question import run_question
from state.tools import Feed

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def m01():
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    return Feed(meta=match_meta(sim), events=sim.run(), data_version="feed-1")


class ByRole:
    """Answers by role and schema; records who was asked."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    async def ask(self, role, instructions, prompt, schema):
        self.asked.append((role, schema.__name__))
        return self.answers[role, schema.__name__], Usage(1, 1)


def _question(text="Why are Northvale hitting so many long balls since 58?", at="68:00"):
    return Question(question_id="q1", match_id="m01", asked_at=at, text=text)


def _framing(**overrides):
    base = dict(
        answerable=True,
        metric="long_ball_share",
        subject="Northvale",
        direction="up",
        since="58:00",
        why="it assumes Northvale go long more",
    )
    return Framing(**base | overrides)


SOUND = SemanticReport(
    sentences=[SentenceCheck(sentence="s", entailed=True, overstated=False, reason="ok")] * 3
)


def test_the_lead_states_what_a_question_assumes_or_why_it_cannot(m01):
    def framed(answer):
        model = ByRole({("lead", "Framing"): answer})
        return asyncio.run(frame(model, AgentRole.LEAD, _question(), m01.meta))

    premise, _, _ = framed(_framing())
    assert premise == Premise(
        metric="long_ball_share", subject="Northvale", direction="up", since="58:00"
    )
    assert framed(_framing(answerable=False, why="who will win?"))[:2] == (None, "who will win?")
    assert "not measurable" in framed(_framing(metric="xg"))[1]
    assert "at least 5 minutes" in framed(_framing(since="66:00"))[1]  # 66-68' is too short


def test_a_false_premise_is_answered_with_what_happened_and_no_one_investigates(m01):
    tired = _framing(metric="sprint_count", subject="Harbour City.defence", direction="down")
    model = ByRole({("single", "Framing"): tired})
    question = _question("¿Por qué se cansa la defensa de Harbour City desde el 58?")
    answer = asyncio.run(run_question(Variant.B_SINGLE_AGENT, model, model, question, m01))
    assert answer.outcome == "premise_false" and answer.card is None
    assert model.asked == [("single", "Framing")]  # no cause was looked for
    assert answer.premise_test.sigmas < 2 and "short of 2 sd down" in answer.reason
    assert answer.text["en"].startswith("Not beyond ordinary play")
    assert answer.text["es"].startswith("No más allá de lo normal")
    assert Answer.model_validate_json(answer.model_dump_json()) == answer


def test_a_true_premise_is_investigated_and_verified_like_a_detected_moment(m01):
    press = Proposal(
        cause="tactical.press_intensity_up",
        metric="pressure_rate",
        subject="Harbour City",
        direction="up",
        min_change=1.5,
        why="a higher press forces Northvale long",
    )
    script = {
        ("lead", "Framing"): _framing(),
        ("tactics", "Registration"): Registration(hypotheses=[press]),
        ("physical", "Registration"): Registration(hypotheses=[]),
        ("game_state", "Registration"): Registration(hypotheses=[]),
        ("physical", "Counters"): Counters(counters=[]),
        ("game_state", "Counters"): Counters(counters=[]),
        ("synthesis", "Ranking"): Ranking(
            outcome="explained", primary="hyp-tactics-01", secondary=[], why="the press held"
        ),
        ("verifier", "SemanticReport"): SOUND,
    }
    model = ByRole(script)
    answer = asyncio.run(run_question(Variant.A_PROOFLINE, model, model, _question(), m01))
    assert answer.premise_test.holds and answer.outcome == "explained"
    card = answer.card
    assert card.case_id == "case-m01-q1" and card.status == "verified"
    assert (
        card.primary_cause.cause == Cause.PRESS_INTENSITY_UP and card.subject.team == "Harbour City"
    )
    assert answer.text == card.variants["casual"]
    assert ("lead", "Framing") in model.asked and ("synthesis", "Ranking") in model.asked


def test_the_question_suite_has_a_true_and_a_false_premise_per_planted_match():
    suite = keys("dev")
    assert len(suite) == 32 and len({k.question.question_id for k in suite}) == 32
    assert sum(k.premise_true for k in suite) == 12
    assert {k.question.locale for k in suite} == {"en", "es"}
    true = next(k for k in suite if k.premise_true and k.cause == Cause.PRESS_INTENSITY_DOWN)
    assert true.team not in true.question.text  # asked about the other team's long balls


def test_the_suite_scores_right_causes_and_counts_every_false_claim(m01):
    suite = keys("dev")
    assert score([], suite)["missing"] == 32
    result = score([], suite)
    assert result["answered_right"] == "0/12" and result["false_claims"] == 0
