"""Score product batch files or cards, and compare variants: python -m eval --help."""

import argparse
import json
import sys
from pathlib import Path

import yaml

from contracts.card import InsightCard
from contracts.eval_run import EvalRun, VariantComparison
from eval.batch import evaluate_batch
from eval.compare import compare
from eval.metrics import METRIC_NAMES, PLANTED_RECALL
from eval.runner import evaluate
from eval.suites import load_suite


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "compare":
        return _compare(argv[1:])
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
                    **options,
                )
                for variant in variants
            ]
            result = (
                compare(*runs, metric=args.metric, seed=args.seed, resamples=args.resamples)
                if args.compare
                else runs[0]
            )
            _emit(result, args.out)
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
        _emit(run, args.out)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    return 0


def _emit(record: EvalRun | VariantComparison, out: Path | None) -> None:
    serialized = record.model_dump_json(indent=2) + "\n"
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
    args = parser.parse_args(argv)
    try:
        a = EvalRun.model_validate_json(args.run_a.read_text(encoding="utf-8"))
        b = EvalRun.model_validate_json(args.run_b.read_text(encoding="utf-8"))
        comparison = compare(a, b, metric=args.metric, seed=args.seed, resamples=args.resamples)
        _emit(comparison, args.out)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
