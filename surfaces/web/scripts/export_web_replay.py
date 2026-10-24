"""Export the real Studio ledger unchanged after public-contract validation."""

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.card import InsightCard
from contracts.case_file import CaseFile
from contracts.cue import Cue
from contracts.eval_run import Variant
from contracts.event import Event, EventAmendment
from contracts.meta import MatchMeta
from contracts.profile import Profile
from contracts.tool_result import DependencyEntry

WEB = Path(__file__).resolve().parents[1]


class CorrectionRecord(BaseModel):
    """The Studio correction summary; the backend currently exports a plain dict."""

    model_config = ConfigDict(extra="forbid")
    card_id: str
    decision: Literal["revise", "withdraw"]
    revision: int = Field(ge=2)
    amendment_id: str


def validate_studio(raw: dict, match_id: str) -> None:
    if raw["match_id"] != match_id:
        raise ValueError("Studio ledger belongs to a different match")
    Variant(raw["variant"])
    Profile.model_validate(raw["profile"])
    contracts = {
        "cards": InsightCard,
        "cues": Cue,
        "case_files": CaseFile,
        "amendments": EventAmendment,
        "dependencies": DependencyEntry,
        "corrections": CorrectionRecord,
    }
    for field, contract in contracts.items():
        for item in raw[field]:
            contract.model_validate(item)
            if "match_id" in item and item["match_id"] != match_id:
                raise ValueError(f"{field} belongs to a different match")
    keys = [(c["id"], c["revision"]) for c in raw["cards"]]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate card id and revision")
    for correction in raw["corrections"]:
        if (correction["card_id"], correction["revision"]) not in keys:
            raise ValueError("correction names a missing revision")
        if correction["amendment_id"] not in {a["amendment_id"] for a in raw["amendments"]}:
            raise ValueError("correction names a missing amendment")


def export(
    source_dir: Path,
    match_id: str,
    output_dir: Path,
    card_paths: list[Path],
    ledger_path: Path = WEB / "src/fixtures/ledger.json",
    studio_path: Path | None = None,
) -> None:
    raw = json.loads((source_dir / "meta.json").read_text(encoding="utf-8"))
    meta = MatchMeta.model_validate(dict(match_id=raw["match_id"], teams=raw["teams"]))
    if meta.match_id != match_id:
        raise ValueError("source metadata belongs to a different match")
    events = [
        Event.model_validate_json(line)
        for line in (source_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if any(e.match_id != match_id for e in events):
        raise ValueError("source events belong to a different match")
    real = [json.loads(path.read_text(encoding="utf-8")) for path in card_paths]
    for raw_card in real:
        if InsightCard.model_validate(raw_card).match_id != match_id:
            raise ValueError("card belongs to a different match")
    if studio_path:
        ledger = json.loads(studio_path.read_text(encoding="utf-8"))
        validate_studio(ledger, match_id)
        if real:
            raise ValueError("use either Studio ledger or individual cards")
    else:
        ledger = dict(
            match_id=match_id,
            cards=real,
            cues=[],
            case_files=[],
            amendments=[],
            dependencies=[],
            corrections=[],
        )
    # Preserve every backend payload. All previous stand-ins now have real producers.
    ledger = ledger | {"stand_ins": {"cards": [], "cues": []}}
    keys = [(c["id"], c.get("revision", 1)) for c in ledger["cards"]]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate card id and revision")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "meta.json").write_text(meta.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (output_dir / "events.jsonl").write_text(
        "".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8"
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Exported {match_id}: {len(ledger['cards'])} real revisions, "
        f"{len(ledger['cues'])} cues and {len(ledger['case_files'])} case files."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--match", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cards", type=Path, nargs="+", default=[])
    parser.add_argument("--studio-ledger", type=Path)
    parser.add_argument("--ledger", type=Path, default=WEB / "src/fixtures/ledger.json")
    args = parser.parse_args()
    export(args.source, args.match, args.out, args.cards, args.ledger, args.studio_ledger)
