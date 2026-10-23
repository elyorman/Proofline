#!/usr/bin/env python3
"""Export the public contracts to docs/*.schema.json. Commit the output."""

import json
from pathlib import Path

from contracts import (
    Case,
    Cue,
    EvalRun,
    Event,
    EventAmendment,
    FeedMessage,
    InsightCard,
    MatchMeta,
    Profile,
    ToolResult,
    VariantComparison,
)
from contracts.prediction import Hypothesis

DOCS = Path(__file__).resolve().parents[1] / "docs"
SCHEMAS = {
    "event": Event,
    "event-amendment": EventAmendment,
    "match-meta": MatchMeta,
    "feed-message": FeedMessage,
    "tool-result": ToolResult,
    "hypothesis": Hypothesis,
    "case": Case,
    "insight-card": InsightCard,
    "cue": Cue,
    "profile": Profile,
    "eval-run": EvalRun,
    "variant-comparison": VariantComparison,
}


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    for name, model in SCHEMAS.items():
        path = DOCS / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
        print(f"wrote {path.relative_to(DOCS.parent)}")


if __name__ == "__main__":
    main()
