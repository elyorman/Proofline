"""proofline-engine: generate synthetic matches from tactical scripts."""

import argparse
import sys

import yaml
from pydantic import ValidationError

from contracts.eval_run import Split
from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim
from engine.suite_builder import decoys, planted, write


def _seed(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("seed must be zero or positive")
    return value


def _size(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("size must be at least 1")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proofline-engine", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="simulate one match from a script")
    gen.add_argument("--script", required=True, help="path to a tactical script (YAML)")
    gen.add_argument("--seed", type=_seed, default=None, help="overrides the script's seed")
    gen.add_argument("--out", required=True, help="output directory")
    suite = sub.add_parser("suite", help="build a planted or decoy suite with sealed ground truth")
    suite.add_argument("--suite", choices=["planted", "decoys"], required=True)
    suite.add_argument("--split", choices=["dev", "heldout"], required=True)
    suite.add_argument("--out", default="engine/suites", help="suites root directory")
    suite.add_argument(
        "--size", type=_size, default=None, help="scripts per class (planted) or matches (decoys)"
    )
    args = parser.parse_args(argv)
    if args.command == "suite":
        return _suite(parser, args)

    try:
        script = load_script(args.script)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        parser.error(f"cannot load {args.script}: {exc}")
    sim = MatchSim(script, seed=args.seed)
    events = sim.run()
    try:
        write_match(sim, events, args.out)
    except OSError as exc:
        parser.error(f"cannot write {args.out}: {exc}")
    home, away = script.teams["home"].name, script.teams["away"].name
    print(
        f"{script.match_id} seed {sim.seed}: {len(events)} events, "
        f"{home} {sim.score['home']}-{sim.score['away']} {away}"
    )
    return 0


def _suite(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    split = Split(args.split)
    try:
        built = planted(split, args.size) if args.suite == "planted" else decoys(split, args.size)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        out = write(built, args.out)
    except OSError as exc:
        parser.error(f"cannot write {args.out}: {exc}")
    excluded = len(built.flags.exclusions) if built.flags else 0
    print(f"{args.suite} {args.split}: {len(built.scripts)} matches, {excluded} not observable")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
