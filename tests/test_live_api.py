"""The live API answers typed questions through the same run_question as every other path;
here it replays the demo's recorded exchanges, with live model calls forbidden."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from agents.llm import Replay
from contracts.live import LiveJob
from contracts.question import Question
from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim
from ledger.store import MemoryLedger
from surfaces.api.app import Service, build
from tools_server.server import DirectorySource

ROOT = Path(__file__).resolve().parents[1]
RECORDED = ROOT / "tests" / "fixtures" / "questions" / "m01"


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    root = tmp_path_factory.mktemp("live-data")
    sim = MatchSim(load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml"))
    write_match(sim, sim.run(), root / "m01")
    return root


def _service(data, ids, **overrides):
    replay = Replay(RECORDED / "exchanges-A")
    return Service(
        source=DirectorySource(data),
        ledger=MemoryLedger(),
        models=lambda: (replay, replay),
        ids=iter(ids),
        **overrides,
    )


def _ask(client, text, at="68:00", locale="es", viewer="1.2.3.4"):
    body = {"match_id": "m01", "asked_at": at, "text": text, "locale": locale}
    return client.post("/api/questions", json=body, headers={"x-forwarded-for": viewer})


def _settled(client, job_id) -> LiveJob:
    for _ in range(1200):
        job = LiveJob.model_validate(client.get(f"/api/questions/{job_id}").json())
        if job.status in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("the job never finished")


@pytest.fixture(autouse=True)
def no_live_models():
    with patch("agents.llm.FoundryModel.ask", side_effect=AssertionError("no live model calls")):
        yield


def test_a_false_premise_is_turned_away_after_two_stages(data):
    service = _service(data, ["q3"])
    with TestClient(build(service, ["http://localhost:5173"])) as client:
        started = _ask(
            client, "¿Por qué se está cansando la defensa de Harbour City desde el minuto 58?"
        )
        assert started.status_code == 202 and started.json()["status"] == "queued"
        job = _settled(client, "q3")
    assert job.status == "done" and job.answer.outcome == "premise_false"
    assert [s.stage for s in job.stages] == ["framed", "premise"]
    assert job.answer.text["es"] and job.answer.card is None
    audit = service.ledger.containers["audit"][("m01", "q3")]
    assert audit["outcome"] == "premise_false" and audit["stages"][1]["stage"] == "premise"
    assert "cards" not in service.ledger.containers


def test_a_true_premise_is_investigated_verified_and_written_to_the_ledger(data):
    service = _service(data, ["q1"])
    with TestClient(build(service, [])) as client:
        _ask(client, "Why are Northvale hitting so many long balls since 58?", locale="en")
        job = _settled(client, "q1")
    assert job.status == "done" and job.answer.outcome == "explained"
    assert [s.stage for s in job.stages] == [
        "framed",
        "premise",
        "preregistered",
        "tested",
        "cross_examined",
        "synthesized",
        "verified",
    ]
    card = job.answer.card
    assert card.status == "verified"
    stored = service.ledger.containers["cards"]
    assert stored[("m01", f"{card.id}:r1")]["claim"] == card.claim
    assert stored[("m01", f"{card.id}:r2")]["revision"] == job.answer.final.revision == 2


def test_each_viewer_waits_a_minute_and_the_day_has_a_cap(data):
    service = _service(data, ["q3", "q4", "q5"], daily=2)
    with TestClient(build(service, [])) as client:
        q3 = "¿Por qué se está cansando la defensa de Harbour City desde el minuto 58?"
        assert _ask(client, q3).status_code == 202
        again = _ask(client, "¿Está cansado Ambrel desde el minuto 60?", at="76:00")
        assert again.status_code == 429 and again.json()["error"] == "per_viewer"
        other = _ask(
            client, "¿Está cansado Ambrel desde el minuto 60?", at="76:00", viewer="5.6.7.8"
        )
        assert other.status_code == 202
        third = _ask(client, "Who will win the match?", at="76:00", locale="en", viewer="9.9.9.9")
        assert third.status_code == 429 and third.json()["error"] == "daily"
        assert client.get("/api/health").json() == {
            "ok": True,
            "daily_cap": 2,
            "daily_used": 2,
            "busy": sum(j.status in ("queued", "running") for j in service.jobs.values()),
        }
        _settled(client, "q3"), _settled(client, "q4")


def test_a_question_must_be_about_the_replayed_match_and_after_half_time(data):
    service = _service(data, ["x1", "x2", "x3"])
    with TestClient(build(service, [])) as client:
        first_half = _ask(client, "Why are they pressing?", at="30:00", locale="en")
        assert first_half.status_code == 422 and "first half" in first_half.json()["detail"]
        body = {"match_id": "m99", "asked_at": "68:00", "text": "Why?", "locale": "en"}
        assert client.post("/api/questions", json=body).status_code == 422
        assert client.get("/api/questions/nope").status_code == 404
    assert service.used == 0


def test_a_job_has_an_answer_exactly_when_it_is_done():
    question = Question(question_id="q", match_id="m01", asked_at="68:00", text="Why now?")
    with pytest.raises(ValueError, match="answer exactly when"):
        LiveJob(job_id="q", question=question, status="done", created_ms=0)
    with pytest.raises(ValueError, match="error exactly when"):
        LiveJob(job_id="q", question=question, status="failed", created_ms=0)
    assert LiveJob(job_id="q", question=question, status="running", created_ms=0).stages == []
