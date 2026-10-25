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
from contracts.question import Answer, PlainAnswer, Premise, Question
from contracts.taxonomy import AgentRole, Cause
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from eval.questions import claim, keys, score
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
    # "Who ran the most?": a measure, but no one whose change to test.
    assert framed(_framing(subject=None))[0] is None
    assert "names no team, unit or player" in framed(_framing(subject=None))[1]


def test_a_false_premise_is_answered_with_what_happened_and_no_one_investigates(m01):
    tired = _framing(metric="sprint_count", subject="Harbour City.defence", direction="down")
    model = ByRole({("single", "Framing"): tired})
    question = _question("¿Por qué se cansa la defensa de Harbour City desde el 58?")
    answer = asyncio.run(run_question(Variant.B_SINGLE_AGENT, model, model, question, m01))
    assert answer.outcome == "premise_false" and answer.card is None
    assert model.asked == [("single", "Framing")]  # no cause was looked for
    # Pressing, their defence sprints more, not less: +2.07 sd against a premise of a fall.
    assert not answer.premise_test.holds and "short of 1.5 sd down" in answer.reason
    assert answer.text["en"].startswith("The other way: Sprints a minute")
    assert answer.text["es"].startswith("Al contrario: Esprints por minuto")
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
    # m225's tired player does not show in one match (its frozen flag), so it is not scored.
    assert [k.question.match_id for k in suite if k.excluded] == ["m225"]


def test_the_suite_scores_right_causes_and_counts_every_false_claim(m01):
    suite = keys("dev")
    assert score([], suite)["missing"] == 31  # the excluded question is not missing
    result = score([], suite)
    assert result["answered_right"] == "0/11" and result["false_claims"] == 0
    assert result["excluded"] == [next(k.question.question_id for k in suite if k.excluded)]


class ToolUser:
    """A scripted tool-using model: calls the tools it is given, then answers."""

    def __init__(self, calls, reply):
        self.calls, self.reply, self.seen = calls, reply, []

    async def ask_with_tools(self, role, instructions, prompt, schema, tools):
        by_name = {t.__name__: t for t in tools}
        for name, kwargs in self.calls:
            self.seen.append(await by_name[name](**kwargs))
        return self.reply, Usage(3, 2)


def test_the_plain_agent_answers_with_the_tools_it_chose_and_nothing_checks_it(m01):
    from agents.plain import Reply
    from agents.plain import answer as plain

    press = dict(name="pressure_rate", subject="Harbour City")
    model = ToolUser(
        [
            ("baseline", press | {"scope": "first_half"}),
            ("metric", press | {"window": "58:00-68:00"}),
            ("metric", press | {"window": "70:00-80:00"}),  # after the question: refused
        ],
        Reply(happening=True, cause="game_state.chasing_result", team="Harbour City", answer="x"),
    )
    question = _question("Why are Harbour City tiring since 58?")  # nothing checks the premise
    got = asyncio.run(plain(model, question, m01))
    assert '"value":0.32' in model.seen[0] and '"value":0.77' in model.seen[1]
    assert model.seen[2].startswith("error:") and "has not finished" in model.seen[2]
    assert got.claims and got.cause == Cause.CHASING_RESULT and got.tool_calls == 3
    assert PlainAnswer.model_validate_json(got.model_dump_json()) == got


def test_a_plain_claim_on_a_false_premise_counts_as_a_false_claim():
    suite = keys("dev")
    false = next(k for k in suite if not k.premise_true)
    claims = PlainAnswer(
        question=false.question,
        happening=True,
        cause="physical.unit_fatigue",
        team="Northvale",
        text="They are tiring.",
        tool_calls=4,
    )
    row = next(
        r for r in score([claims], suite)["rows"] if r["question_id"] == claims.question.question_id
    )
    assert row["claimed"] and row["false_claim"] and not row["right"]
    declines = claims.model_copy(update={"happening": False, "cause": None, "team": None})
    assert not claim(declines)[0]


def test_a_tool_using_answer_is_recorded_and_replayed_without_its_tool_calls(tmp_path):
    from agents.llm import Recording, Replay
    from agents.plain import Reply

    reply = Reply(happening=False, cause=None, team=None, answer="Not really.")
    recorded = Recording(ToolUser([], reply), tmp_path)
    assert asyncio.run(recorded.ask_with_tools("plain", "i", "p", Reply, []))[0] == reply
    assert asyncio.run(Replay(tmp_path).ask_with_tools("plain", "i", "p", Reply, []))[0] == reply


def test_whoever_reads_a_viewers_words_sees_the_players_names(m01):
    from agents import prompts

    players = prompts.roster(m01.meta)["home"]["players"]
    first = m01.meta.teams["home"].players[0]
    assert players[0].startswith(f"{first.player_id} {first.name}, ")


def test_the_demo_questions_replay_from_their_recorded_exchanges(tmp_path):
    from agents.llm import Replay
    from engine.io import write_match
    from orchestration.question import answer_all

    recorded = ROOT / "tests" / "fixtures" / "questions" / "m01"
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    write_match(sim, sim.run(), tmp_path / "data" / "m01")
    replay = Replay(recorded / "exchanges-A")
    asyncio.run(
        answer_all(
            tmp_path / "data",
            recorded / "questions.jsonl",
            Variant.A_PROOFLINE,
            tmp_path / "out",
            replay,
            replay,
        )
    )

    def answers(path):
        out = {}
        for line in path.read_text().splitlines():
            a = Answer.model_validate_json(line)
            if a.card:  # a card's trace id is minted per run
                a = a.model_copy(
                    update={"card": a.card.model_copy(update={"provenance": None})}, deep=True
                )
            # A card's trace id is minted per run, for the first card and its settled revision.
            out[a.question.question_id] = a.model_dump(
                mode="json", exclude={"card": {"provenance"}, "final": {"provenance"}}
            )
        return out

    fresh, committed = (
        answers(tmp_path / "out" / "A" / "answers.jsonl"),
        answers(recorded / "A" / "answers.jsonl"),
    )
    assert fresh == committed
    assert {a["outcome"] for a in committed.values()} >= {
        "explained",
        "premise_false",
        "unanswerable",
    }
    assert any(a["final"] for a in committed.values())  # a follow-up settled after a question
