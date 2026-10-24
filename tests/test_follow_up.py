"""Keep watching: when a rival cause survives beside the primary, each side pre-registers a
decisive test for the minutes after the card, and code settles it once they are played. On
the demo match, Harbour City press from 56' while 1-3 down: a deliberate press and chasing
the result both fit 58-68'. Agents are scripted; nothing here calls a live model."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cross_exam import Counters
from agents.follow_up import minutes_after, rivals
from agents.llm import Usage
from agents.outputs import Decisive, Proposal, Ranking, Registration
from agents.verifier.semantic import SemanticReport, SentenceCheck
from contracts.card import InsightCard
from contracts.clock import MatchClock
from contracts.eval_run import Variant
from contracts.taxonomy import AgentRole, CardStatus, Cause
from detector.cusum import detect
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from eval.questions import claim
from orchestration.case import run_case
from state.tools import Feed

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def m01():
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    events = sim.run()
    feed = Feed(meta=match_meta(sim), events=events, data_version="feed-1")
    case = next(c for c in detect(feed.meta, events) if c.window.end.minute == 63)
    return feed, case


class ByRole:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    async def ask(self, role, instructions, prompt, schema):
        self.asked.append((role, schema.__name__, prompt))
        return self.answers[role, schema.__name__], Usage(1, 1)


def _proposal(cause, min_change):
    return Proposal(
        cause=cause,
        metric="pressure_rate",
        subject="Harbour City",
        direction="up",
        min_change=min_change,
        why="they press harder",
    )


SOUND = SemanticReport(
    sentences=[SentenceCheck(sentence="s", entailed=True, overstated=False, reason="ok")] * 3
)


def _script(primary):
    return {
        ("tactics", "Registration"): Registration(
            hypotheses=[_proposal("tactical.press_intensity_up", 1.5)]
        ),
        ("physical", "Registration"): Registration(hypotheses=[]),
        ("game_state", "Registration"): Registration(
            hypotheses=[_proposal("game_state.chasing_result", 1.0)]
        ),
        ("tactics", "Counters"): Counters(counters=[]),
        ("game_state", "Counters"): Counters(counters=[]),
        ("synthesis", "Ranking"): Ranking(
            outcome="explained", primary=primary, secondary=[], why="both fit; this one more"
        ),
        # Each side's decisive test for 68-83': chasing goes direct, a press does not.
        ("game_state", "Decisive"): Decisive(
            metric="long_ball_share",
            subject="Harbour City",
            direction="up",
            why="chasing goes long",
        ),
        ("tactics", "Decisive"): Decisive(
            metric="long_ball_share",
            subject="Harbour City",
            direction="flat",
            why="a press wins the ball high; it does not hit it long",
        ),
        ("verifier", "SemanticReport"): SOUND,
    }


def test_a_rival_that_survives_is_settled_on_the_minutes_after_the_card(m01):
    feed, case = m01
    model = ByRole(_script(primary="hyp-game_state-01"))  # chasing first, the press its rival
    outcome = asyncio.run(run_case(Variant.A_PROOFLINE, model, model, case, feed))
    first, later = outcome.verdict.card, outcome.followed.card
    assert first.status == CardStatus.VERIFIED and first.follow_up.status == "pending"
    assert [r.cause for r in first.follow_up.rivals] == [Cause.PRESS_INTENSITY_UP]
    assert str(first.follow_up.window) == "68:00-83:00"
    assert first.variants["casual"]["en"].endswith(
        "We'll check it against a deliberate step up in Harbour City's press by 83'."
    )
    assert "antes del minuto 83" in first.variants["casual"]["es"]
    # Each side was asked by its own agent, after the first card's window was closed.
    asked = [(role, schema) for role, schema, _ in model.asked if schema == "Decisive"]
    assert asked == [("game_state", "Decisive"), ("tactics", "Decisive")]
    # 68-83': Harbour City's own long balls stayed ordinary, so chasing's prediction failed.
    f = later.follow_up
    assert f.status == "overturned" and later.status == CardStatus.REVISED
    chasing, press = f.tests
    assert (chasing.holds, press.holds) == (False, True) and abs(press.sigmas) < 1
    assert later.primary_cause.cause == Cause.PRESS_INTENSITY_UP and later.revision == 2
    (ruled,) = [r for r in later.rejected_alternatives if r.rejected_by == "follow_up"]
    assert ruled.taxonomy == Cause.CHASING_RESULT and "did not come true" in ruled.reason
    assert str(later.timing.verified_at) == "83:00"
    assert later.revisions[-1].reason == "follow-up over 68:00-83:00: overturned"
    assert "Checked by 83': not Harbour City chasing the result." in later.variants["casual"]["en"]
    assert "68'-83': Long-ball share (Harbour City)" in later.variants["analyst"]["en"]
    assert InsightCard.model_validate_json(later.model_dump_json()) == later
    # Scored as the follow-up left it, the answer names the press.
    answer = SimpleNamespace(card=first, final=later)
    assert claim(answer)[1] == Cause.CHASING_RESULT
    assert claim(answer, after_follow_up=True)[1] == Cause.PRESS_INTENSITY_UP


def test_the_same_minutes_confirm_a_primary_whose_prediction_came_true(m01):
    feed, case = m01
    model = ByRole(_script(primary="hyp-tactics-01"))
    later = asyncio.run(run_case(Variant.A_PROOFLINE, model, model, case, feed)).followed.card
    assert later.follow_up.status == "confirmed"
    assert later.primary_cause.cause == Cause.PRESS_INTENSITY_UP
    assert "Checked by 83': not Harbour City chasing the result." in later.variants["casual"]["en"]


def test_minutes_that_fit_both_leave_the_card_open_and_claim_no_cause(m01):
    feed, case = m01
    script = _script(primary="hyp-tactics-01")
    # Both come true over 68-83': Northvale press no more, and Harbour City go no longer.
    script["tactics", "Decisive"] = Decisive(
        metric="pressure_rate", subject="Northvale", direction="flat", why="they do not press back"
    )
    script["game_state", "Decisive"] = Decisive(
        metric="long_ball_share", subject="Harbour City", direction="flat", why="they keep it short"
    )
    model = ByRole(script)
    outcome = asyncio.run(run_case(Variant.A_PROOFLINE, model, model, case, feed))
    later = outcome.followed.card
    assert later.follow_up.status == "unresolved"
    assert later.variants["casual"]["en"].endswith(
        "It could be a deliberate step up in Harbour City's press or Harbour City chasing the "
        "result: by 83' the numbers still fit both."
    )
    assert claim(SimpleNamespace(card=outcome.verdict.card, final=later), True) == (
        False,
        None,
        None,
    )


def test_with_one_cause_left_nothing_stays_open(m01):
    feed, case = m01
    script = _script(primary="hyp-tactics-01")
    script["game_state", "Registration"] = Registration(hypotheses=[])
    model = ByRole(script)
    outcome = asyncio.run(run_case(Variant.A_PROOFLINE, model, model, case, feed))
    assert outcome.verdict.card.follow_up is None and outcome.followed is None
    assert rivals(outcome.finding, feed) == []
    assert not any(schema == "Decisive" for _, schema, _ in model.asked)


@pytest.mark.parametrize(
    "at,minutes", [("68:00", "68:00-83:00"), ("78:00", "78:00-90+0:00"), ("81:00", None)]
)
def test_a_follow_up_needs_ten_minutes_of_the_match_left(at, minutes):
    window = minutes_after(MatchClock.parse(at))
    assert (str(window) if window else None) == minutes


class Single(ByRole):
    """The single agent: one role for every step, so its decisive test follows its side."""

    async def ask(self, role, instructions, prompt, schema):
        if schema is Decisive:
            self.asked.append((role, "Decisive", prompt))
            own = json.loads(prompt[prompt.index("{") :])["your_cause"]["cause"]
            side = "game_state" if own == "game_state.chasing_result" else "tactics"
            return self.answers[side, "Decisive"], Usage(1, 1)
        return await super().ask(role, instructions, prompt, schema)


def test_the_single_agent_answers_for_both_sides(m01):
    feed, case = m01
    script = _script(primary="hyp-single-02")  # chasing, registered second
    both = [
        _proposal("tactical.press_intensity_up", 1.5),
        _proposal("game_state.chasing_result", 1),
    ]
    script |= {
        ("single", "Registration"): Registration(hypotheses=both),
        ("single", "Counters"): Counters(counters=[]),
        ("single", "Ranking"): script["synthesis", "Ranking"],
    }
    model = Single(script)
    outcome = asyncio.run(run_case(Variant.B_SINGLE_AGENT, model, model, case, feed))
    asked = [role for role, schema, _ in model.asked if schema == "Decisive"]
    assert asked == [AgentRole.SINGLE.value] * 2
    assert outcome.followed.card.follow_up.status == "overturned"


class Queued(ByRole):
    """Answers a role's decisive tests in turn, so a refused one can be put back."""

    async def ask(self, role, instructions, prompt, schema):
        if schema is Decisive and isinstance(self.answers[role, "Decisive"], list):
            self.asked.append((role, "Decisive", prompt))
            return self.answers[role, "Decisive"].pop(0), Usage(1, 1)
        return await super().ask(role, instructions, prompt, schema)


def test_a_test_that_is_the_other_sides_own_claim_is_put_back_once(m01):
    feed, case = m01
    script = _script(primary="hyp-tactics-01")
    script["game_state", "Decisive"] = [
        # Harbour City pressing harder is the press's own claim: it cannot decide.
        Decisive(metric="pressure_rate", subject="Harbour City", direction="up", why="chasing"),
        script["game_state", "Decisive"],
    ]
    model = Queued(script)
    later = asyncio.run(run_case(Variant.A_PROOFLINE, model, model, case, feed)).followed.card
    retry = [prompt for role, schema, prompt in model.asked if role == "game_state"][-1]
    assert "Your test was refused: that is a rival's own claim" in retry
    chasing = next(t for t in later.follow_up.tests if t.side == "rival")
    assert chasing.metric == "long_ball_share" and later.follow_up.status == "confirmed"


class ByCause(ByRole):
    """Answers each side's decisive test by the cause it argues for, whichever agent asks."""

    async def ask(self, role, instructions, prompt, schema):
        if schema is Decisive:
            self.asked.append((role, "Decisive", prompt))
            own = json.loads(prompt[prompt.index("{") :])["your_cause"]["cause"]
            return self.answers[own], Usage(1, 1)
        return await super().ask(role, instructions, prompt, schema)


def test_every_rival_is_watched_and_each_must_fail_for_the_card_to_stand(m01):
    feed, case = m01
    higher = Proposal(
        cause="tactical.block_higher",
        metric="long_ball_share",
        subject="Northvale",
        direction="up",
        min_change=1.5,
        why="Northvale push up and go long",
    )
    script = _script(primary="hyp-tactics-01")
    script["tactics", "Registration"] = Registration(
        hypotheses=[_proposal("tactical.press_intensity_up", 1.5), higher]
    )
    script |= {
        "tactical.press_intensity_up": script["tactics", "Decisive"],  # Harbour City stay short
        "game_state.chasing_result": script["game_state", "Decisive"],  # they go long: fails
        "tactical.block_higher": Decisive(
            metric="pressure_rate", subject="Northvale", direction="up", why="a high block presses"
        ),
    }
    outcome = asyncio.run(
        run_case(Variant.A_PROOFLINE, ByCause(script), ByCause(script), case, feed)
    )
    first, later = outcome.verdict.card, outcome.followed.card
    assert [r.cause for r in first.follow_up.rivals] == [
        Cause.CHASING_RESULT,
        Cause.BLOCK_HIGHER,
    ]
    assert first.variants["casual"]["en"].endswith(
        "We'll check it against Harbour City chasing the result and Northvale pushing their "
        "block higher by 83'."
    )
    assert later.follow_up.status == "confirmed"
    assert all(t.sigmas is not None for t in later.follow_up.tests)  # all three measured
    assert later.variants["casual"]["en"].endswith(
        "Checked by 83': not Harbour City chasing the result or Northvale pushing their block "
        "higher."
    )
    assert later.variants["casual"]["es"].endswith(
        "no es Harbour City buscando el resultado ni Northvale adelantando su bloque."
    )


def test_a_test_that_a_change_already_under_way_goes_on_is_put_back_once(m01):
    feed, case = m01
    script = _script(primary="hyp-tactics-01")
    script["game_state", "Decisive"] = [
        # Northvale's long balls are +7 sd over 58-68' already: every cause fits that.
        Decisive(metric="long_ball_share", subject="Northvale", direction="up", why="chasing"),
        script["game_state", "Decisive"],
    ]
    model = Queued(script)
    later = asyncio.run(run_case(Variant.A_PROOFLINE, model, model, case, feed)).followed.card
    retry = [prompt for role, schema, prompt in model.asked if role == "game_state"][-1]
    assert "that change is already under way" in retry
    assert later.follow_up.status == "confirmed"
