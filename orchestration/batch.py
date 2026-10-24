"""Batch mode: every case the detector opens on a folder of matches, through one variant.

Each match's results are written to <out>/<variant>/<match_id>.json: when it started, and
every case with its outcome, its card if one was published and its revision once a
follow-up settled, its tool calls, tokens and recovery flag. The
Evaluator scores those files against the sealed ground truth; this module never reads it.
"""

import asyncio
import json
import time
import traceback
from pathlib import Path
from typing import Any

from agents.llm import Model
from contracts.eval_run import Variant
from detector.cusum import detect
from orchestration.case import run_case
from tools_server.server import DirectorySource


async def _one(variant: Variant, agents: Model, verifier: Model, case, feed) -> dict[str, Any]:
    record: dict[str, Any] = {
        "case_id": case.case_id,
        "moment": case.moment_type.value,
        "window": str(case.window),
    }
    try:
        outcome = await run_case(variant, agents, verifier, case, feed)
    except Exception as exc:  # one failed case is recorded, not the end of the batch
        return record | {"error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()}
    f = outcome.finding
    card = outcome.verdict.card if outcome.verdict else None
    final = outcome.followed.card if outcome.followed else None
    return record | {
        "outcome": f.ranking.outcome,
        "card": card.model_dump(mode="json") if card else None,
        "published": bool(card and card.status == "verified"),
        # The card's next revision once its follow-up settled, if it had one and it passed.
        "final": final.model_dump(mode="json") if final and final.status == "revised" else None,
        "tool_calls": f.tools.used,
        "tokens": [f.usage.input_tokens, f.usage.output_tokens],
        "recovered": f.recovered,
        "hypotheses": len(f.hypotheses),
        "counter_tests": len(f.exams),
    }


async def run_batch(
    data: Path, variant: Variant, out: Path, agents: Model, verifier: Model, concurrency: int = 3
) -> list[Path]:
    source = DirectorySource(data)
    folder = Path(out) / variant.value
    folder.mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(concurrency)
    written: list[Path] = []

    async def bounded(case, feed):
        async with gate:
            return await _one(variant, agents, verifier, case, feed)

    for match_dir in sorted(p for p in Path(data).iterdir() if (p / "events.jsonl").exists()):
        target = folder / f"{match_dir.name}.json"
        if target.exists():  # resumable: a finished match is not run again
            written.append(target)
            continue
        feed = source.feed(match_dir.name)
        cases = detect(feed.meta, feed.events)
        # When the match began: the Evaluator proves the flags were frozen before any run.
        started_at_ms = int(time.time() * 1000)
        results = await asyncio.gather(*(bounded(c, feed) for c in cases))
        doc = {
            "match_id": match_dir.name,
            "variant": variant.value,
            "started_at_ms": started_at_ms,
            "cases": results,
        }
        target.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        written.append(target)
        published = sum(r.get("published", False) for r in results)
        errors = sum("error" in r for r in results)
        summary = f"{len(cases)} cases, {published} cards, {errors} errors"
        print(f"{match_dir.name} {variant.value}: {summary}", flush=True)
    return written
