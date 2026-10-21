"""proofline-engine: generate synthetic matches from tactical scripts."""

import argparse
import sys

from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proofline-engine", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="simulate one match from a script")
    gen.add_argument("--script", required=True, help="path to a tactical script (YAML)")
    gen.add_argument("--seed", type=int, default=None, help="overrides the script's seed")
    gen.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)

    script = load_script(args.script)
    sim = MatchSim(script, seed=args.seed)
    events = sim.run()
    write_match(sim, events, args.out)
    home, away = script.teams["home"].name, script.teams["away"].name
    print(
        f"{script.match_id} seed {sim.seed}: {len(events)} events, "
        f"{home} {sim.score['home']}-{sim.score['away']} {away}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
