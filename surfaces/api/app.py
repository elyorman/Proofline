"""The live API (spec §12.2 Run live, §8.2 "Why?"): a viewer's typed question about the
replayed match, answered by the real agents on Foundry, verified, and written to the ledger.

The public link replays recordings and never depends on this API: it asks here only what
the recordings do not hold. Questions run one at a time, at most one per viewer a minute and
a capped number a day, and each reports its stages as they happen. Every sentence a viewer
reads is still written by the Narrator's templates from verified propositions, so a typed
question cannot make Proofline say anything the Verifier did not pass.

    uvicorn surfaces.api.app:create --factory --port 8000
"""

import asyncio
import logging
import os
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agents.llm import Model
from contracts.eval_run import Variant
from contracts.live import LiveJob, LiveStage, LiveStageName
from contracts.question import Answer, Question
from ledger.store import CosmosLedger, Ledger
from orchestration import progress
from orchestration.case import models
from orchestration.question import run_question
from tools_server.server import DirectorySource

MATCHES = {"m01"}  # the matches the public link replays
PER_VIEWER_S = 60  # one live question per viewer a minute (spec §7.4)
WAITING = 3  # questions that may wait behind the one running
JOB_TIMEOUT_S = 420  # a full investigation takes one to three minutes
KEPT = 500  # finished jobs kept for polling
STAGES = set(get_args(LiveStageName))
WEB = (
    "https://nice-coast-044d8740f.5.azurestaticapps.net,http://localhost:5173,http://localhost:4173"
)


@dataclass
class Job:
    question: Question
    created_ms: int
    status: str = "queued"
    stages: list[LiveStage] = field(default_factory=list)
    answer: Answer | None = None
    error: str | None = None
    trace_id: str | None = None

    def view(self, job_id: str, status: str | None = None) -> LiveJob:
        return LiveJob(
            job_id=job_id,
            question=self.question,
            status=status or self.status,
            stages=self.stages,
            answer=self.answer,
            error=self.error,
            trace_id=self.trace_id,
            created_ms=self.created_ms,
        )


def _live_models() -> tuple[Model, Model]:
    return models()


def _ids() -> Iterator[str]:
    while True:
        yield f"live-{uuid.uuid4().hex[:10]}"


@dataclass
class Service:
    source: DirectorySource
    ledger: Ledger | None = None
    models: Callable[[], tuple[Model, Model]] = _live_models
    ids: Iterator[str] = field(default_factory=_ids)
    daily: int = 60
    jobs: dict[str, Job] = field(default_factory=dict)
    asked: dict[str, float] = field(default_factory=dict)
    day: str = ""
    used: int = 0
    gate: asyncio.Lock = field(default_factory=asyncio.Lock)
    tasks: set[asyncio.Task] = field(default_factory=set)

    def admit(self, viewer: str, now: float) -> tuple[int, dict[str, Any]] | None:
        """Why a question may not run now, or None when it may."""
        today = time.strftime("%Y-%m-%d", time.gmtime(now))
        if today != self.day:
            self.day, self.used = today, 0
        if self.used >= self.daily:
            return 429, {"error": "daily", "detail": "today's live questions are used up"}
        wait = PER_VIEWER_S - (now - self.asked.get(viewer, -PER_VIEWER_S))
        if wait > 0:
            return 429, {"error": "per_viewer", "retry_after_s": int(wait) + 1}
        if sum(j.status in ("queued", "running") for j in self.jobs.values()) > WAITING:
            return 503, {"error": "busy", "detail": "other questions are being answered"}
        return None

    async def answer(self, job_id: str) -> None:
        job = self.jobs[job_id]
        async with self.gate:
            job.status = "running"

            def heard(stage: str, note: str) -> None:
                if stage in STAGES:
                    job.stages.append(
                        LiveStage(stage=stage, at_ms=int(time.time() * 1000), note=note[:300])
                    )

            token = progress.listener.set(heard)
            try:
                with _tracer().start_as_current_span("proofline.question") as span:
                    context = span.get_span_context()
                    job.trace_id = f"{context.trace_id:032x}" if context.is_valid else None
                    span.set_attribute("proofline.match_id", job.question.match_id)
                    span.set_attribute("proofline.question_id", job.question.question_id)
                    feed = self.source.feed(job.question.match_id)
                    agents, verifier = self.models()
                    answer = await asyncio.wait_for(
                        run_question(Variant.A_PROOFLINE, agents, verifier, job.question, feed),
                        JOB_TIMEOUT_S,
                    )
                    span.set_attribute("proofline.outcome", answer.outcome)
                job.answer = answer
            except Exception as exc:  # the viewer sees that it failed, not a stack trace
                job.error = f"{type(exc).__name__}: {str(exc)[:200]}"
            finally:
                progress.listener.reset(token)
        ended = "done" if job.answer is not None else "failed"
        if self.ledger is not None:  # recorded before the viewer is told it ended
            try:
                await asyncio.to_thread(_record, self.ledger, job.view(job_id, ended))
            except Exception as exc:  # a ledger outage does not take the answer away
                logging.getLogger(__name__).warning("ledger write failed for %s: %r", job_id, exc)
        job.status = ended
        while len(self.jobs) > KEPT:  # forget the oldest finished job
            oldest = next(k for k, j in self.jobs.items() if j.status in ("done", "failed"))
            del self.jobs[oldest]


def _record(ledger: Ledger, job: LiveJob) -> None:
    """The answer's cards go to the ledger beside every other card; the job to the audit."""
    match_id = job.question.match_id
    a = job.answer
    cards = [c for c in ([a.card, a.final] if a else []) if c is not None]
    if cards:
        ledger.put(
            "cards",
            match_id,
            [
                {**c.model_dump(mode="json"), "id": f"{c.id}:r{c.revision}", "card_id": c.id}
                for c in cards
            ],
        )
    audit = {
        "id": job.job_id,
        "kind": "live_question",
        "match_id": match_id,
        "status": job.status,
        "outcome": a.outcome if a else None,
        "question": job.question.model_dump(mode="json"),
        "stages": [s.model_dump(mode="json") for s in job.stages],
        "trace_id": job.trace_id,
        "input_tokens": a.input_tokens if a else 0,
        "output_tokens": a.output_tokens if a else 0,
        "error": job.error,
    }
    ledger.put("audit", match_id, [audit])


def _tracer():
    from opentelemetry import trace

    return trace.get_tracer("proofline.api")


def _viewer(request: Request) -> str:
    """The address the ingress saw: it appends it last, after anything the client sent."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[-1].strip() or (request.client.host if request.client else "?")


def build(service: Service, origins: list[str]) -> Starlette:
    async def ask(request: Request) -> JSONResponse:
        try:
            body = await request.json()
            question = Question(
                question_id="pending",  # minted once the question is admitted
                match_id=body.get("match_id", ""),
                asked_at=body.get("asked_at", ""),
                text=str(body.get("text", "")).strip(),
                locale=body.get("locale", "en"),
            )
        except (ValueError, ValidationError, AttributeError) as exc:
            detail = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
            return JSONResponse({"error": "invalid", "detail": detail[:200]}, status_code=422)
        if question.match_id not in MATCHES:
            return JSONResponse({"error": "invalid", "detail": "unknown match"}, status_code=422)
        now, viewer = time.time(), _viewer(request)
        refused = service.admit(viewer, now)
        if refused:
            status, payload = refused
            return JSONResponse(payload, status_code=status)
        service.asked[viewer], service.used = now, service.used + 1
        job_id = next(service.ids)
        question = question.model_copy(update={"question_id": job_id})
        service.jobs[job_id] = Job(question=question, created_ms=int(now * 1000))
        task = asyncio.create_task(service.answer(job_id))
        service.tasks.add(task)
        task.add_done_callback(service.tasks.discard)
        return JSONResponse(service.jobs[job_id].view(job_id).model_dump(mode="json"), 202)

    async def poll(request: Request) -> JSONResponse:
        job_id = request.path_params["job_id"]
        job = service.jobs.get(job_id)
        if job is None:
            return JSONResponse({"error": "unknown job"}, status_code=404)
        return JSONResponse(job.view(job_id).model_dump(mode="json"))

    async def health(_: Request) -> JSONResponse:
        running = sum(j.status in ("queued", "running") for j in service.jobs.values())
        return JSONResponse(
            {"ok": True, "daily_cap": service.daily, "daily_used": service.used, "busy": running}
        )

    return Starlette(
        routes=[
            Route("/api/questions", ask, methods=["POST"]),
            Route("/api/questions/{job_id}", poll, methods=["GET"]),
            Route("/api/health", health, methods=["GET"]),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_methods=["GET", "POST"],
                allow_headers=["content-type"],
            )
        ],
    )


def _trace_to_app_insights() -> None:
    connection = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection:
        return
    from agent_framework.observability import configure_otel_providers
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

    configure_otel_providers(
        service_name="proofline-api",
        exporters=[AzureMonitorTraceExporter(connection_string=connection)],
    )


def create() -> Starlette:
    """The deployed app: live models, the Cosmos ledger, traces to Application Insights."""
    _trace_to_app_insights()
    endpoint, database = os.getenv("AZURE_COSMOS_ENDPOINT"), os.getenv("AZURE_COSMOS_DATABASE")
    ledger = CosmosLedger(endpoint, database or "proofline") if endpoint else None
    service = Service(
        source=DirectorySource(Path(os.getenv("PROOFLINE_DATA", "data"))),
        ledger=ledger,
        daily=int(os.getenv("PROOFLINE_DAILY_QUESTIONS", "60")),
    )
    return build(service, os.getenv("PROOFLINE_WEB_ORIGINS", WEB).split(","))
