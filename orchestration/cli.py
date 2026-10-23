"""proofline: run the product pipeline against the deployed ledger.

Endpoints come from the environment (`azd env get-values`), credentials from the default
Azure credential; nothing here holds a key.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from contracts.case import Case
from contracts.eval_run import Variant
from contracts.taxonomy import AgentRole
from detector.cusum import detect
from ledger.eventhubs import consume
from ledger.ingest import Ingest
from ledger.store import CosmosLedger
from orchestration.batch import run_batch
from orchestration.case import models, run_case
from tools_server.server import DirectorySource

ENV = ("AZURE_EVENTHUBS_NAMESPACE", "AZURE_EVENTHUB_NAME", "AZURE_COSMOS_ENDPOINT")


def _print_cases(cases: list[Case]) -> None:
    for case in cases:
        triggers = ", ".join(
            f"{t.metric} {t.subject} {t.baseline_value:.2f} -> {t.value:.2f} (n={t.n_events})"
            for t in case.triggers
        )
        print(f"{case.case_id} {case.window}: {triggers}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proofline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="read a match off the feed into Cosmos and detect")
    ingest.add_argument("--match", required=True, help="the match id to wait for")
    ingest.add_argument("--run-id", required=True, help="the Match Clock run to read")
    ingest.add_argument("--timeout", type=float, default=900, help="seconds to wait")
    case = sub.add_parser("case", help="investigate one detected case and verify its card")
    case.add_argument("--data", default="data", help="folder of engine-written matches")
    case.add_argument("--match", required=True)
    case.add_argument("--minute", type=int, required=True, help="the minute the case opened")
    case.add_argument("--variant", choices=["A", "B"], default="B")
    case.add_argument("--record", type=Path, help="save every model exchange here")
    case.add_argument("--replay", type=Path, help="answer from saved exchanges only")
    case.add_argument(
        "--kill-agent",
        action="append",
        default=[],
        choices=["tactics", "physical", "game_state"],
        help="stop this agent once mid-case, to show recovery from its checkpoint (variant A)",
    )
    batch = sub.add_parser("batch", help="run every detected case of a folder of matches")
    batch.add_argument("--data", type=Path, required=True, help="folder of match feeds")
    batch.add_argument("--variant", choices=["A", "B"], required=True)
    batch.add_argument("--out", type=Path, default=Path("runs"), help="results root")
    batch.add_argument("--concurrency", type=int, default=3)
    batch.add_argument("--record", type=Path, help="save every model exchange here")
    args = parser.parse_args(argv)
    if args.command == "case":
        return _case(parser, args)
    if args.command == "batch":
        _quiet()
        agents, verifier = models(args.record)
        asyncio.run(
            run_batch(
                args.data, Variant(args.variant), args.out, agents, verifier, args.concurrency
            )
        )
        return 0

    missing = [name for name in ENV if not os.getenv(name)]
    if missing:
        parser.error(f'set {", ".join(missing)} (eval "$(azd env get-values)")')
    database = os.getenv("AZURE_COSMOS_DATABASE", "proofline")
    run = Ingest(CosmosLedger(os.environ["AZURE_COSMOS_ENDPOINT"], database), args.run_id)
    print(f"waiting for {args.match} (run {args.run_id}) on the feed", flush=True)
    ended = consume(
        os.environ["AZURE_EVENTHUBS_NAMESPACE"],
        os.environ["AZURE_EVENTHUB_NAME"],
        run,
        args.match,
        _print_cases,
        args.timeout,
    )
    match = run.matches.get(args.match)
    stored, cases = (len(match.delivered), len(match.detector.cases)) if match else (0, 0)
    print(f"{args.match}: {stored} events stored, {cases} cases")
    return 0 if ended else 1


def _quiet() -> None:
    for name in ("httpx", "azure", "agent_framework"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _case(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    _quiet()
    feed = DirectorySource(Path(args.data)).feed(args.match)
    found = [c for c in detect(feed.meta, feed.events) if c.window.end.minute == args.minute]
    if not found:
        parser.error(f"no case on {args.match} opened at {args.minute}'")
    agents, verifier = models(args.record, args.replay)
    stop = {AgentRole(a): 1 for a in args.kill_agent}
    outcome = asyncio.run(run_case(Variant(args.variant), agents, verifier, found[0], feed, stop))
    f = outcome.finding
    print(f"{found[0].case_id}: {len(f.hypotheses)} hypotheses, {len(f.refused)} refused")
    for r in f.refused:
        print(f"  refused {r.proposal.cause} {r.proposal.metric}: {r.reason}")
    for t in f.tested:
        print(f"  {t.test.outcome:9s} {t.hypothesis.taxonomy}: {t.test.reason}")
    for e in f.exams:
        print(f"  counter-test by {e.challenger} on {e.hypothesis_id}: {e.result} ({e.reason})")
    for line in f.unrun:
        print(f"  counter-test {line}")
    for c in f.checkpoints:
        failed = f", failed: {', '.join(c.agents_failed)}" if c.agents_failed else ""
        print(f"  checkpoint {c.stage}: {c.note}{failed}")
    if f.recovered:
        print("  recovered_from_checkpoint: an agent was retried from its stage's checkpoint")
    print(f"  ranking: {f.ranking.outcome}, primary {f.ranking.primary}: {f.ranking.why}")
    print(f"  {f.tools.used} tool calls, {f.usage.input_tokens}+{f.usage.output_tokens} tokens")
    if outcome.verdict is None:
        print("  no card: the case closes as", f.ranking.outcome)
        return 0
    card = outcome.verdict.card
    v = card.verification
    print(f"  card {card.id}: {card.status}, support {v.support_level}, {v.rejection_reason or ''}")
    for audience, texts in card.variants.items():
        for locale, text in texts.items():
            print(f"    {audience}/{locale}: {text}")
    if outcome.verdict.report:
        for s in outcome.verdict.report.sentences:
            print(f"    semantic: entailed={s.entailed} overstated={s.overstated}: {s.reason}")
    out = Path("runs") / f"{card.id}-{args.variant}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(card.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"  written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
