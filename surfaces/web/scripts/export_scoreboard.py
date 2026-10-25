"""Write the Analyst Console's scoreboard fixture from the saved evaluation records.

Runs `python -m eval scoreboard --records eval/records --json` (the only source of numbers)
and keeps what the console shows: each record's estimates with their intervals and n. The
console computes nothing; values stay fractions, as the records hold them.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLLOW_UP = "-after-follow-up"


def _estimates(items: list[dict] | None) -> list[dict]:
    keep = ("name", "value", "ci_low", "ci_high", "n", "ci_method")
    return [{k: e.get(k) for k in keep} for e in items or [] if e]


def compact(board: dict) -> dict:
    out: dict = {"source": "eval/records", "detector": [], "comparisons": [], "questions": []}
    out["seeded"] = []
    for r in board["records"]:
        kind, rid = r["record_type"], r["id"]
        base = {"id": rid, "split": r.get("split"), "model_id": r.get("model_id")}
        if kind == "detector_run":
            out["detector"].append(
                base
                | {
                    "variant": r["variant"],
                    "after_follow_up": rid.endswith(FOLLOW_UP),
                    "metrics": _estimates(r.get("metrics")),
                    "failed_cases": r.get("failed_cases", 0),
                    "exclusions": len(r.get("exclusions") or []),
                }
            )
        elif kind in ("variant_comparison", "question_comparison"):
            first = r.get("run_a") or ""
            out["comparisons"].append(
                base
                | {
                    "type": r.get("comparison_type") or kind,
                    "variant_a": r.get("variant_a"),
                    "variant_b": r.get("variant_b"),
                    "after_follow_up": FOLLOW_UP in first,
                    "differences": _estimates(r.get("differences")),
                }
            )
        elif kind == "question_run":
            out["questions"].append(
                base
                | {
                    "variant": r["variant"],
                    "after_follow_up": bool(r.get("after_follow_up")),
                    "metrics": _estimates(r.get("metrics")),
                }
            )
        elif kind == "seeded_verifier":
            out["seeded"].append(
                base
                | {
                    name: _estimates([r.get(name)])[0] if r.get(name) else None
                    for name in ("catch_rate", "all_cards_catch_rate", "false_rejection_rate")
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=ROOT / "eval/records")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "surfaces/web/src/fixtures/scoreboard.json"
    )
    args = parser.parse_args(argv)
    board = subprocess.run(
        [sys.executable, "-m", "eval", "scoreboard", "--records", str(args.records), "--json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    args.out.write_text(json.dumps(compact(json.loads(board)), indent=1) + "\n")
    print(f"scoreboard written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
