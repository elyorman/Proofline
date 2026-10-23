"""The Correction Watcher on the demo match: Northvale's 45-55' actions were first shown 22 m
to the right, a flank card was published on them, and the 68' amendment moves them back.
Agents are scripted; nothing here calls a live model."""

import asyncio
from pathlib import Path

import pytest

from agents.llm import Usage
from agents.outputs import Proposal, Ranking, Registration
from agents.propose import propose
from agents.single import investigate
from agents.verifier.checks import Record
from agents.verifier.semantic import SemanticReport, SentenceCheck
from agents.verifier.verify import verify
from contracts.taxonomy import CardStatus
from corrections.watcher import DependencyIndex, Published, correct
from detector.cusum import detect
from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim
from tools_server.server import DirectorySource

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


class Scripted:
    """Queued answers, one per call, in order; asking for more is an error."""

    def __init__(self, *answers):
        self.answers = list(answers)

    async def ask(self, role, instructions, prompt, schema):
        answer = self.answers.pop(0)
        assert isinstance(answer, schema), (answer, schema)
        return answer, Usage(1, 1)


SOUND = SemanticReport(
    sentences=[SentenceCheck(sentence="s", entailed=True, overstated=False, reason="ok")] * 3
)


@pytest.fixture(scope="module")
def m01(tmp_path_factory):
    root = tmp_path_factory.mktemp("matches")
    sim = MatchSim(load_script(M01))
    write_match(sim, sim.run(), root / "m01")
    source = DirectorySource(root)
    shown = source.feed("m01")
    (a1,) = source.amendments("m01")
    return shown, a1


def _published(feed, minute, proposal):
    case = next(c for c in detect(feed.meta, feed.events) if c.window.end.minute == minute)
    ranking = Ranking(outcome="explained", primary="hyp-single-01", secondary=[], why="clear")
    finding = asyncio.run(
        investigate(Scripted(Registration(hypotheses=[proposal]), ranking), case, feed)
    )
    card = propose(finding, feed)
    record = Record.of(finding.tools.log, finding.evidence)
    verified = asyncio.run(verify(Scripted(SOUND), card, record, feed, [])).card
    assert verified.status == CardStatus.VERIFIED, verified.verification
    return Published(verified, case, finding.hypotheses[0], finding.evidence)


def _flank(min_change):
    return Proposal(
        cause="tactical.flank_overload",
        metric="channel_share_right",
        subject="Northvale",
        direction="up",
        min_change=min_change,
        why="Northvale overloading the right",
    )


PRESS = Proposal(
    cause="tactical.press_intensity_up",
    metric="pressure_rate",
    subject="Harbour City",
    direction="up",
    min_change=0.15,
    why="a higher press",
)


def test_the_amendment_reaches_the_flank_card_and_leaves_the_press_card_alone(m01):
    shown, a1 = m01
    flank, press = _published(shown, 58, _flank(0.2)), _published(shown, 63, PRESS)
    index = DependencyIndex()
    index.add(flank)
    index.add(press)
    assert index.dependents(a1) == {flank.card.id}
    assert all(flank.card.id in e.card_ids for e in index.entries() if e.event_id in a1.event_ids)


def test_a_flank_card_the_corrected_feed_no_longer_supports_is_withdrawn(m01):
    shown, a1 = m01
    flank = _published(shown, 58, _flank(0.2))
    assert flank.card.verification.support_level == "moderate"
    fixed = shown.amended(a1)
    correction = asyncio.run(correct(Scripted(), flank, fixed, a1))  # no model is asked
    card = correction.card
    assert correction.decision == "withdraw" and card.status == CardStatus.WITHDRAWN
    assert card.revision == 2 and card.revisions[0].amendment_ids == ["a1"]
    assert card.depends_on.data_version == "feed-1+a1"
    (now,) = card.evidence
    (then,) = flank.card.evidence
    assert (round(then.value, 3), round(now.value, 3)) == (0.636, 0.39)
    assert "short of the claim of up by 0.2" in card.verification.rejection_reason
    assert card.variants["casual"]["en"].startswith("Corrected data no longer show that Northvale")
    assert card.variants["casual"]["es"].startswith("Los datos corregidos ya no muestran")
    assert "was 64%" in card.variants["analyst"]["en"]
    assert flank.card.status == CardStatus.VERIFIED and flank.card.revision == 1  # unchanged


def test_a_claim_that_still_holds_is_reverified_and_revised(m01):
    shown, a1 = m01
    flank = _published(shown, 58, _flank(0.1))
    correction = asyncio.run(correct(Scripted(SOUND), flank, shown.amended(a1), a1))
    card = correction.card
    assert correction.decision == "revise" and card.status == CardStatus.REVISED
    assert card.verification.status == "passed" and card.verification.support_level == "weak"
    assert card.variants["casual"]["en"].startswith("Updated after a data correction: ")
    assert card.variants["casual"]["es"].startswith("Actualizado tras una corrección de datos: ")


def test_a_card_whose_numbers_the_amendment_does_not_change_needs_nothing(m01):
    shown, a1 = m01
    press = _published(shown, 63, PRESS)
    assert asyncio.run(correct(Scripted(), press, shown.amended(a1), a1)) is None
