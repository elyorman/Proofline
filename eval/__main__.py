"""Score product batch files or cards, and compare variants: python -m eval --help."""

import argparse
import json
import sys
from pathlib import Path

import yaml

from contracts.card import InsightCard
from contracts.eval_run import EvalRun, SeededRun, Split, Variant, VariantComparison
from eval.batch import evaluate_batch
from eval.compare import compare
from eval.metrics import METRIC_NAMES, PLANTED_RECALL
from eval.records import reuse_runs, save_records
from eval.runner import evaluate
from eval.suites import load_suite


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "compare":
        return _compare(argv[1:])
    if argv and argv[0] == "scoreboard":
        return _scoreboard(argv[1:])
    if argv and argv[0] == "seeded":
        return _seeded(argv[1:])
    parser = argparse.ArgumentParser(
        prog="proofline-eval",
        description=__doc__,
        epilog="Compare saved runs with: proofline-eval compare --help",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--cards", type=Path)
    source.add_argument("--runs", type=Path, help="batch split root containing A/ and B/")
    parser.add_argument("--suite", default="planted,decoys")
    parser.add_argument("--split", choices=["dev", "heldout"], required=True)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--variant", choices=["A", "B"])
    operation.add_argument("--compare", nargs=2, choices=["A", "B"], metavar=("FIRST", "SECOND"))
    parser.add_argument("--run-id")
    parser.add_argument("--model-id")
    parser.add_argument("--model-tier", choices=["dev", "final"], default="dev")
    parser.add_argument("--tool-call-budget", type=int)
    parser.add_argument("--wall-time-budget-s", type=float)
    parser.add_argument("--started-at-ms", type=int, help="epoch ms; defaults to scoring start")
    parser.add_argument("--finished-at-ms", type=int, help="epoch ms; defaults to scoring finish")
    parser.add_argument("--suites-root", type=Path, default=Path("engine/suites"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--metric", choices=METRIC_NAMES, default=PLANTED_RECALL)
    parser.add_argument("--out", type=Path, help="also save JSON to a new file")
    parser.add_argument("--record-dir", type=Path, help="save immutable committed-number records")
    parser.add_argument(
        "--after-follow-up", action="store_true", help="score each card as its follow-up left it"
    )
    args = parser.parse_args(argv)
    try:
        suites = [
            load_suite(args.suites_root, s.strip(), args.split) for s in args.suite.split(",")
        ]
        options = dict(
            model_id=args.model_id,
            model_tier=args.model_tier,
            tool_call_budget=args.tool_call_budget,
            wall_time_budget_s=args.wall_time_budget_s,
            seed=args.seed,
            resamples=args.resamples,
            started_at_ms=args.started_at_ms,
            finished_at_ms=args.finished_at_ms,
        )
        if args.runs is not None:
            variants = args.compare or [args.variant]
            runs = [
                evaluate_batch(
                    args.runs,
                    suites,
                    variant=variant,
                    run_id=(
                        f"{args.run_id}-{variant}" if args.compare and args.run_id else args.run_id
                    ),
                    after_follow_up=args.after_follow_up,
                    **options,
                )
                for variant in variants
            ]
            if args.compare and args.record_dir:
                runs = reuse_runs(runs, args.record_dir)
            result = (
                compare(*runs, metric=args.metric, seed=args.seed, resamples=args.resamples)
                if args.compare
                else runs[0]
            )
            dependencies = runs if args.compare else []
            _emit(result, args.out, args.record_dir, dependencies)
            return 0
        if args.compare:
            raise ValueError("--compare requires --runs")
        if not args.run_id or not args.model_id:
            raise ValueError("--cards requires --run-id and --model-id")
        if not args.cards.is_dir():
            raise ValueError("--cards must be a directory")
        cards = []
        for path in sorted(args.cards.rglob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            cards.extend(
                InsightCard.model_validate(c) for c in (data if isinstance(data, list) else [data])
            )
        options["tool_call_budget"] = 16 if args.tool_call_budget is None else args.tool_call_budget
        options["wall_time_budget_s"] = (
            20 if args.wall_time_budget_s is None else args.wall_time_budget_s
        )
        run = evaluate(
            suites,
            cards,
            run_id=args.run_id,
            variant=args.variant,
            **options,
        )
        _emit(run, args.out, args.record_dir)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    return 0


def _emit(
    record: EvalRun | VariantComparison | SeededRun,
    out: Path | None,
    record_dir: Path | None = None,
    dependencies: list[EvalRun] | None = None,
) -> None:
    serialized = record.model_dump_json(indent=2) + "\n"
    if out is not None and out.exists():
        raise FileExistsError(f"output already exists: {out}")
    if record_dir is not None:
        missing = [r for r in dependencies or [] if not (record_dir / f"{r.run_id}.json").exists()]
        save_records([*missing, record], record_dir)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as output:
            output.write(serialized)
    print(serialized, end="")


def _compare(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="proofline-eval compare", description="Paired difference of two saved EvalRun records."
    )
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--metric", choices=METRIC_NAMES, default=PLANTED_RECALL)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--record-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        a = EvalRun.model_validate_json(args.run_a.read_text(encoding="utf-8"))
        b = EvalRun.model_validate_json(args.run_b.read_text(encoding="utf-8"))
        comparison = compare(a, b, metric=args.metric, seed=args.seed, resamples=args.resamples)
        if args.record_dir:
            reuse_runs([a, b], args.record_dir)
        _emit(comparison, args.out, args.record_dir, [a, b])
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


def _scoreboard(argv: list[str]) -> int:
    from eval.scoreboard import scoreboard

    parser = argparse.ArgumentParser(prog="python -m eval scoreboard")
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    try:
        print(scoreboard(args.records, args.check), end="")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


def _seeded(argv: list[str]) -> int:
    import asyncio
    import os
    from contextlib import redirect_stdout

    from eval.seeded import replay_settings, run_seeded
    from orchestration.case import models

    parser = argparse.ArgumentParser(prog="python -m eval seeded")
    for name in ("runs", "data", "exchanges"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--variant", choices=["A", "B"], required=True)
    parser.add_argument("--split", choices=["dev", "heldout"])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", type=Path, help="record live Verifier exchanges")
    mode.add_argument("--replay", type=Path, help="use recorded Verifier exchanges only")
    parser.add_argument("--limit", type=int, help="maximum number of published cards")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--resamples", type=int)
    parser.add_argument("--model-id")
    parser.add_argument("--run-id")
    parser.add_argument("--eval-run", type=Path, help="link an EvalRun for suite/flag provenance")
    parser.add_argument("--record-dir", type=Path, default=Path("eval/records"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.record and args.record.resolve() == args.exchanges.resolve():
            raise ValueError("record seeded verification into a separate exchange directory")
        if args.record and any(args.record.rglob("*.json")):
            raise ValueError("seeded --record requires a fresh exchange directory; use --replay")
        split = Split(args.split or args.runs.name)
        settings = replay_settings(args.replay) if args.replay else {}
        seed = args.seed if args.seed is not None else settings.get("seed", 0)
        resamples = (
            args.resamples if args.resamples is not None else settings.get("resamples", 2000)
        )
        limit = args.limit if args.limit is not None else settings.get("limit")
        _, model = models(record=args.record, replay=args.replay)
        evaluation = (
            EvalRun.model_validate_json(args.eval_run.read_bytes()) if args.eval_run else None
        )
        model_id = args.model_id or (
            os.getenv("AZURE_VERIFIER_DEPLOYMENT") if args.record else None
        )
        with redirect_stdout(sys.stderr):
            result = asyncio.run(
                run_seeded(
                    args.runs,
                    Variant(args.variant),
                    args.data,
                    args.exchanges,
                    model,
                    args.record or args.replay,
                    split=split,
                    model_id=model_id,
                    run_id=args.run_id,
                    limit=limit,
                    concurrency=args.concurrency,
                    seed=seed,
                    resamples=resamples,
                    evaluation=evaluation,
                )
            )
        if args.replay:
            stored = args.record_dir / f"{result.run_id}.json"
            if stored.exists():
                previous = SeededRun.model_validate_json(stored.read_bytes())
                without_clock = {"started_at_ms", "finished_at_ms"}
                if previous.model_dump(exclude=without_clock) != result.model_dump(
                    exclude=without_clock
                ):
                    raise ValueError("replay differs from the stored seeded record")
                print(f"Replay verified against {stored}; wrote nothing.", file=sys.stderr)
                print(previous.model_dump_json(indent=2))
            else:
                print(
                    "Replay reproduced the run; no stored record to verify; wrote nothing.",
                    file=sys.stderr,
                )
                print(result.model_dump_json(indent=2))
        else:
            _emit(result, args.out, args.record_dir)
    except (OSError, ValueError, LookupError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
