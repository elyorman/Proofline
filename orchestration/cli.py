"""proofline: run the product pipeline against the deployed ledger.

Endpoints come from the environment (`azd env get-values`), credentials from the default
Azure credential; nothing here holds a key.
"""

import argparse
import os
import sys

from contracts.case import Case
from ledger.eventhubs import consume
from ledger.ingest import Ingest
from ledger.store import CosmosLedger

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
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    sys.exit(main())
