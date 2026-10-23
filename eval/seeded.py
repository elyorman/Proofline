"""Replay published cases, seed false claims and benchmark the unchanged Verifier."""

import asyncio
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from agents.llm import Model, Recording, Replay, Usage
from agents.verifier.checks import Record as ToolRecord
from agents.verifier.verify import verify
from contracts.card import InsightCard
from contracts.eval_run import (
    EvalRun,
    SeedCardResult,
    SeededRun,
    SeedTrial,
    SeedType,
    SeedTypeResult,
    Split,
    Suite,
    Variant,
)
from detector.cusum import detect
from eval.batch import BatchCase, BatchMatch
from eval.metrics import estimate
from eval.seed_checks import failed_checks
from eval.seeds import mutations
from orchestration.case import Outcome, run_case
from state.tools import Feed
from tools_server.server import DirectorySource


def digest_paths(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(
            path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes() + b"\0"
        )
    return digest.hexdigest()


def card_data(card: InsightCard) -> dict:
    data = card.model_dump(mode="json")
    data["provenance"].pop("trace_id", None)
    return data


def scoped_model(model: Model, name: str) -> Model:
    """Identical prompts in different trials must not overwrite recorded replies."""
    if isinstance(model, Recording):
        return Recording(model.model, Path(model.folder) / name)
    if isinstance(model, Replay):
        return Replay(Path(model.folder) / name)
    return model


async def replay_case(
    variant: Variant, expected: BatchCase, match_id: str, feed: Feed, exchanges: Path
) -> Outcome:
    cases = [c for c in detect(feed.meta, feed.events) if c.case_id == expected.case_id]
    if (
        len(cases) != 1
        or cases[0].window != expected.window
        or cases[0].moment_type != expected.moment
    ):
        raise ValueError(
            f"{match_id}/{expected.case_id}: recorded case does not match the detector"
        )
    replay = Replay(exchanges)
    outcome = await run_case(variant, replay, replay, cases[0], feed)
    actual = outcome.verdict.card if outcome.verdict else None
    if (
        actual is None
        or actual.status != "verified"
        or card_data(actual) != card_data(expected.card)
    ):
        raise ValueError(
            f"{match_id}/{expected.case_id}: replayed card differs from the batch beyond trace_id; "
            "tool/evidence IDs must be stable or persisted by the backend"
        )
    return outcome


async def benchmark_card(
    model: Model, card: InsightCard, record: ToolRecord, feed: Feed, exams
) -> tuple[SeedCardResult, Usage]:
    control = await verify(
        scoped_model(model, "control"), card.model_copy(deep=True), record, feed, exams
    )
    usage = control.usage
    trials = []
    for mutation in mutations(card, feed):
        if mutation.card is None:
            trials.append(
                SeedTrial(kind=mutation.kind, applied=False, skip_reason=mutation.skip_reason)
            )
            continue
        verdict = await verify(
            scoped_model(model, mutation.kind.value), mutation.card, record, feed, exams
        )
        usage = usage + verdict.usage
        trials.append(
            SeedTrial(
                kind=mutation.kind,
                applied=True,
                field=mutation.field,
                before=mutation.before,
                after=mutation.after,
                verification=verdict.card.verification,
                caught=verdict.card.verification.status == "rejected",
            )
        )
    return SeedCardResult(
        match_id=card.match_id,
        case_id=card.case_id,
        card_id=card.id,
        revision=card.revision,
        card_digest=hashlib.sha256(
            json.dumps(card_data(card), sort_keys=True).encode()
        ).hexdigest(),
        control=control.card.verification,
        trials=trials,
    ), usage


def summarize(cards: list[SeedCardResult], seed: int, resamples: int):
    types = []
    for kind in SeedType:
        rows = [
            (
                sum(bool(t.caught) for t in c.trials if t.kind == kind and t.applied),
                sum(t.applied for t in c.trials if t.kind == kind),
            )
            for c in cards
        ]
        checks = Counter(
            check
            for c in cards
            for t in c.trials
            if t.kind == kind
            for check in failed_checks(t.verification)
        )
        types.append(
            SeedTypeResult(
                kind=kind,
                seeded=sum(d for _, d in rows),
                caught=sum(n for n, _ in rows),
                checks=dict(checks),
                estimate=estimate(
                    kind.value, Suite.SEEDED_FALSE_CLAIMS, rows, seed=seed, resamples=resamples
                ),
            )
        )
    rows = [
        (sum(bool(t.caught) for t in c.trials if t.applied), sum(t.applied for t in c.trials))
        for c in cards
    ]
    catch = estimate(
        "verifier_catch_rate", Suite.SEEDED_FALSE_CLAIMS, rows, seed=seed, resamples=resamples
    )
    controls = estimate(
        "control_false_rejection_rate",
        Suite.SEEDED_FALSE_CLAIMS,
        [(int(c.control.status == "rejected"), 1) for c in cards],
        seed=seed,
        resamples=resamples,
    )
    return types, catch, controls


async def run_seeded(
    runs: Path,
    variant: Variant,
    data: Path,
    exchanges: Path,
    model: Model,
    verifier_exchanges: Path,
    *,
    split: Split,
    model_id: str | None = None,
    run_id: str | None = None,
    limit: int | None = None,
    concurrency: int = 1,
    seed: int = 0,
    resamples: int = 2000,
    evaluation: EvalRun | None = None,
) -> SeededRun:
    if concurrency < 1 or (limit is not None and limit < 1) or resamples < 1:
        raise ValueError("concurrency, limit and resamples must be positive")
    started = int(time.time() * 1000)
    folder = runs / variant.value
    paths = sorted(folder.glob("*.json"))
    if not paths:
        raise ValueError(f"no batch files in {folder}")
    if not exchanges.is_dir() or not list(exchanges.glob("*.json")):
        raise ValueError("the batch's recorded model exchanges are required")
    batch_digest = digest_paths(paths, folder)
    if evaluation and (evaluation.batch_digest, evaluation.variant, evaluation.split) != (
        batch_digest,
        variant,
        split,
    ):
        raise ValueError("the linked EvalRun must score this exact batch, variant and split")
    selected = []
    for path in paths:
        match = BatchMatch.model_validate_json(path.read_bytes())
        if match.variant != variant or path.stem != match.match_id:
            raise ValueError(f"{path}: batch identity mismatch")
        selected += [
            (match.match_id, c) for c in match.cases if isinstance(c, BatchCase) and c.published
        ]
    selected = selected if limit is None else selected[:limit]
    if not selected:
        raise ValueError("the selected batch contains no published cards")
    gate, source = asyncio.Semaphore(concurrency), DirectorySource(data)
    results, usage = [], Usage()
    feeds = {match: source.feed(match) for match, _ in selected}
    # Verify every replay before spending anything on seeded live verification.
    reconstructed = []
    for match, case in selected:
        reconstructed.append(await replay_case(variant, case, match, feeds[match], exchanges))

    async def one(match, outcome):
        async with gate:
            finding = outcome.finding
            card = outcome.verdict.card
            identity = f"{match}/{card.case_id}/{card.id}/{card.revision}"
            namespace = hashlib.sha256(identity.encode()).hexdigest()[:16]
            return await benchmark_card(
                scoped_model(model, namespace),
                card,
                ToolRecord.of(finding.tools.log, finding.evidence),
                feeds[match],
                finding.exams,
            )

    answers = await asyncio.gather(
        *(one(match, outcome) for (match, _), outcome in zip(selected, reconstructed, strict=True))
    )
    for result, consumed in answers:
        results.append(result)
        usage = usage + consumed
    types, catch, controls = summarize(results, seed, resamples)
    data_paths = [
        data / match / name for match in sorted(feeds) for name in ("meta.json", "events.jsonl")
    ]
    source_digest = digest_paths(list(exchanges.glob("*.json")), exchanges)
    verifier_digest = digest_paths(list(verifier_exchanges.rglob("*.json")), verifier_exchanges)
    content = [
        batch_digest,
        source_digest,
        verifier_digest,
        [c.model_dump(mode="json") for c in results],
        seed,
        resamples,
        model_id,
    ]
    identifier = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]
    return SeededRun(
        run_id=run_id or f"seeded-{variant}-{identifier}",
        split=split,
        variant=variant,
        model_id=model_id,
        batch_digest=batch_digest,
        exchanges_digest=source_digest,
        data_digest=digest_paths(data_paths, data),
        verifier_exchanges_digest=verifier_digest,
        suite_digest=evaluation.suite_digest if evaluation else None,
        flag_set_id=evaluation.flags.flag_set_id if evaluation and evaluation.flags else None,
        started_at_ms=started,
        finished_at_ms=int(time.time() * 1000),
        cards=results,
        types=types,
        catch_rate=catch,
        false_rejection_rate=controls,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        bootstrap_seed=seed,
        bootstrap_resamples=resamples,
    )
