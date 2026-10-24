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
from contracts.question import Question
from contracts.taxonomy import AgentRole
from detector.cusum import detect
from ledger.eventhubs import consume
from ledger.ingest import Ingest
from ledger.store import CosmosLedger
from orchestration.batch import run_batch
from orchestration.case import case_file, models, run_case
from orchestration.question import answer_all, run_question
from orchestration.studio import studio, write
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
    ask = sub.add_parser("ask", help="answer one viewer question about a match so far")
    ask.add_argument("--data", default="data", help="folder of engine-written matches")
    ask.add_argument("--match", required=True)
    ask.add_argument("--at", required=True, help="the match clock when it is asked, e.g. 68:00")
    ask.add_argument("--question", required=True)
    ask.add_argument("--locale", choices=["en", "es"], default="en")
    ask.add_argument("--variant", choices=["A", "B"], default="A")
    ask.add_argument("--record", type=Path, help="save every model exchange here")
    ask.add_argument("--replay", type=Path, help="answer from saved exchanges only")
    asked = sub.add_parser("questions", help="answer every question in a questions file")
    asked.add_argument("--data", type=Path, required=True, help="folder of match feeds")
    asked.add_argument("--questions", type=Path, required=True, help="questions.jsonl")
    asked.add_argument(
        "--variant", choices=["A", "B", "P"], required=True, help="P: the plain agent baseline"
    )
    asked.add_argument("--out", type=Path, required=True, help="answers go to <out>/<variant>/")
    asked.add_argument("--concurrency", type=int, default=2)
    asked.add_argument("--record", type=Path, help="save every model exchange here")
    asked.add_argument("--replay", type=Path, help="answer from saved exchanges only")
    run = sub.add_parser("run", help="run a whole match through the product")
    run.add_argument("--mode", choices=["studio"], default="studio")
    run.add_argument("--data", type=Path, default=Path("data"), help="folder of written matches")
    run.add_argument("--match", required=True)
    run.add_argument("--variant", choices=["A", "B"], default="A")
    run.add_argument("--record", type=Path, help="save every model exchange here")
    run.add_argument("--replay", type=Path, help="answer from saved exchanges only")
    run.add_argument("--out", type=Path, default=Path("runs/studio"), help="ledger root")
    args = parser.parse_args(argv)
    if args.command == "run":
        _quiet()
        agents, verifier = models(args.record, args.replay)
        source = DirectorySource(args.data)
        ledger = asyncio.run(studio(source, args.match, agents, verifier, Variant(args.variant)))
        shown = [c for c in ledger["cards"] if c["lane"] == "full" and c["timing"]["published_at"]]
        print(
            f"{args.match}: {len(ledger['case_files'])} cases, {len(shown)} card revisions "
            f"shown, {len(ledger['corrections'])} corrections, {len(ledger['cues'])} cues"
        )
        for c in shown:
            at = c["timing"]["published_at"]
            when = f"{at['minute']}:{at['second']:02d}"
            print(f"  {when} r{c['revision']} {c['status']}: {c['claim']}")
        for c in ledger["corrections"]:
            print(f"  correction: {c['card_id']} {c['decision']} after {c['amendment_id']}")
        print(f"  written to {write(ledger, args.out)}")
        return 0
    if args.command == "case":
        return _case(parser, args)
    if args.command == "ask":
        _quiet()
        feed = DirectorySource(Path(args.data)).feed(args.match)
        question = Question(
            question_id="q1",
            match_id=args.match,
            asked_at=args.at,
            text=args.question,
            locale=args.locale,
        )
        agents, verifier = models(args.record, args.replay)
        answer = asyncio.run(run_question(Variant(args.variant), agents, verifier, question, feed))
        if answer.premise:
            p = answer.premise
            print(f"premise: {p.metric} of {p.subject} {p.direction} since {p.since}")
        print(f"{answer.outcome}: {answer.reason}")
        for locale, text in answer.text.items():
            print(f"  {locale}: {text}")
        return 0
    if args.command == "questions":
        _quiet()
        agents, verifier = models(args.record, args.replay)
        asyncio.run(
            answer_all(
                args.data,
                args.questions,
                args.variant if args.variant == "P" else Variant(args.variant),
                args.out,
                agents,
                verifier,
                args.concurrency,
            )
        )
        return 0
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
    filed = Path("runs") / f"{found[0].case_id}-{args.variant}.json"
    filed.parent.mkdir(exist_ok=True)
    filed.write_text(case_file(outcome, Variant(args.variant)).model_dump_json(indent=2) + "\n")
    print(f"  case file written to {filed}")
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
    if outcome.followed:  # keep watching: the decisive tests, measured once played
        later = outcome.followed.card
        for t in later.follow_up.tests:
            print(
                f"  decisive test, {t.side} ({t.cause.value}): {t.metric} of {t.subject} "
                f"{t.direction}; {'holds' if t.holds else 'fails'}: {t.measured}"
            )
        rejected = later.verification.rejection_reason or ""
        print(
            f"  follow-up {later.follow_up.status}: revision {later.revision} {later.status} "
            f"{rejected}"
        )
        for locale, text in later.variants.get("casual", {}).items():
            print(f"    casual/{locale}: {text}")
        settled = Path("runs") / f"{card.id}-{args.variant}-r{later.revision}.json"
        settled.write_text(later.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"  written to {settled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
