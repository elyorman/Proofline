"""Microsoft Foundry's built-in evaluators on what a viewer reads in the demo take: every card
revision it published (casual and analyst text, English and Spanish) and every answer that
turned a premise away. Each is judged against the facts our Verifier saw (or, for a premise,
code's test), never the agents' reasoning: an outside judge beside our own semantic check,
which reads only the English.

    uv run python -m eval.foundry_evals --ledger surfaces/web/src/fixtures/ledger.json \\
        --data data --out eval/foundry/demo-take.json
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from agents import narrator
from agents.verifier.semantic import facts
from contracts.card import InsightCard
from contracts.meta import MatchMeta
from contracts.question import Answer
from contracts.taxonomy import SupportLevel

EVALUATORS = ["groundedness", "relevance", "coherence", "fluency"]
MODES = ("casual", "analyst")
LOCALES = ("en", "es")


def items(ledger: dict[str, Any], meta: MatchMeta) -> list[dict[str, str]]:
    """One item per text a viewer reads: the query, the text, and what it must rest on."""
    out = []
    for raw in ledger["cards"]:
        card = InsightCard.model_validate(raw)
        support = card.verification.support_level if card.verification else None
        if card.lane != "full" or support is None:  # a withdrawal or a goal is a template
            continue
        context = json.dumps(facts(card, SupportLevel(support), meta), ensure_ascii=False)
        at = card.timing.published_at or card.timing.verified_at
        for mode in MODES:
            for locale in LOCALES:
                out.append(
                    {
                        "id": f"{card.id}:r{card.revision}:{mode}:{locale}",
                        "query": f"Explain, in {locale}, for a {mode} viewer, what changed in "
                        f"the match by {at.minute}' and why.",
                        "response": card.variants[mode][locale],
                        "context": context,
                    }
                )
    for raw in ledger.get("answers", []):
        answer = Answer.model_validate(raw)
        if answer.outcome != "premise_false" or answer.premise_test is None:
            continue
        test = answer.premise_test
        names = {answer.premise.subject: narrator.who(meta, answer.premise.subject)[0]}
        context = json.dumps(
            {"premise_test": test.reason, "holds": test.holds, "names": names},
            ensure_ascii=False,
        )
        for locale in LOCALES:
            out.append(
                {
                    "id": f"{answer.question.question_id}:{locale}",
                    "query": answer.question.text,
                    "response": answer.text[locale],
                    "context": context,
                }
            )
    return out


async def run(rows: list[dict[str, str]], name: str, concurrency: int = 2) -> dict[str, Any]:
    """One Foundry evaluation run per item: its results come back without the item they
    judged, so a run of one is the only way to say which text a judge failed."""
    from agent_framework import EvalItem, Message
    from agent_framework.foundry import FoundryChatClient, FoundryEvals
    from azure.identity import DefaultAzureCredential

    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    credential = DefaultAzureCredential()
    gate = asyncio.Semaphore(concurrency)

    def judge() -> FoundryEvals:  # one client per run: a finished run closes its connection
        client = FoundryChatClient(
            project_endpoint=os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"],
            model=deployment,
            credential=credential,
        )
        return FoundryEvals(client=client, evaluators=EVALUATORS, timeout=900, poll_interval=10)

    async def one(row: dict[str, str]) -> dict[str, Any]:
        item = EvalItem(
            conversation=[
                Message(role="user", contents=[row["query"]]),
                Message(role="assistant", contents=[row["response"]]),
            ],
            context=row["context"],
        )
        async with gate:
            for attempt in range(3):  # a dropped connection is not the judge's verdict
                try:
                    result = await judge().evaluate([item], eval_name=f"{name} {row['id']}")
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(5 * (attempt + 1))
        scores = {
            s.name: {"score": s.score, "passed": s.passed} for i in result.items for s in i.scores
        }
        return {"id": row["id"], "status": result.status, "scores": scores}

    judged = await asyncio.gather(*(one(r) for r in rows))
    counts = {
        e: sum(j["scores"].get(e, {}).get("passed") is True for j in judged) for e in EVALUATORS
    }
    return {
        "judge_model": deployment,
        "items": len(judged),
        "passed": counts,
        "per_item": judged,
    }


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    for attr in ("model_dump", "to_dict", "as_dict"):
        if hasattr(value, attr):
            return _plain(getattr(value, attr)())
    return str(value)


def main(argv: list[str] | None = None) -> int:
    from tools_server.server import DirectorySource

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    meta = DirectorySource(args.data).feed(ledger["match_id"]).meta
    rows = items(ledger, meta)
    report = {
        "what": "Foundry built-in evaluators on the demo take's viewer-facing text",
        "ledger": str(args.ledger),
        "evaluated_on": time.strftime("%Y-%m-%d"),
        "evaluators": EVALUATORS,
        "texts": {r["id"]: r["response"] for r in rows},
        "foundry": asyncio.run(run(rows, "proofline demo take")),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["foundry"], indent=1)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
