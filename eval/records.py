"""Immutable JSON records: the sole input to the generated scoreboard."""

import json
import re
from pathlib import Path

from contracts.eval_run import EvalRun, SeededRun, VariantComparison

Record = EvalRun | VariantComparison | SeededRun


def identity(record: Record) -> str:
    return record.comparison_id if isinstance(record, VariantComparison) else record.run_id


def reuse_runs(runs: list[EvalRun], folder: Path) -> list[EvalRun]:
    """A comparison can reference saved inputs without rewriting their scoring timestamps."""
    result = []
    for run in runs:
        path = folder / f"{run.run_id}.json"
        if path.exists():
            previous = EvalRun.model_validate_json(path.read_bytes())
            without_clock = {"started_at_ms", "finished_at_ms"}
            if previous.model_dump(exclude=without_clock) != run.model_dump(exclude=without_clock):
                raise ValueError(f"saved run {run.run_id} disagrees with the scored batch")
            run = previous
        result.append(run)
    return result


def save_records(records: list[Record], folder: Path) -> None:
    names = [identity(record) for record in records]
    if len(set(names)) != len(names):
        raise ValueError("record IDs must be unique")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) for name in names):
        raise ValueError("record IDs must be safe file names")
    paths = [folder / f"{name}.json" for name in names]
    if any(path.exists() for path in paths):
        raise FileExistsError("a record already exists; records cannot be overwritten")
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        for path, record in zip(paths, records, strict=True):
            # Validate even instances whose nested fields were changed after construction.
            record = type(record).model_validate_json(record.model_dump_json())
            with path.open("x", encoding="utf-8") as target:
                written.append(path)
                target.write(record.model_dump_json(indent=2) + "\n")
    except Exception:
        for path in written:
            path.unlink()
        raise


def load_records(folder: Path) -> list[Record]:
    if not folder.is_dir():
        raise ValueError(f"record directory does not exist: {folder}")
    records = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("a record must be an object")
            model = (
                SeededRun
                if data.get("record_type") == "seeded_verifier"
                else VariantComparison
                if "comparison_id" in data
                else EvalRun
            )
            record = model.model_validate(data)
            if path.stem != identity(record):
                raise ValueError("record ID must match its file name")
            records.append(record)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
    return records
