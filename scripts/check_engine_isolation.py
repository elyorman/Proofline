#!/usr/bin/env python3
"""Fail if product code imports `engine` or reads sealed ground truth.

Only `engine/` itself, `eval/`, `tests/` and `scripts/` may reference the
engine package or ground-truth files. Everything else, including the Python
API under `surfaces/`, is product code and is checked.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXEMPT = {"engine", "eval", "tests", "scripts"}
NOT_PYTHON = {"docs", "infra", "data", "node_modules", ".git", ".venv", ".github"}
GROUND_TRUTH_RE = re.compile(r"ground_truth[^\s\"']*\.(ya?ml|json)")


def product_dirs(root: Path = ROOT) -> list[Path]:
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in EXEMPT | NOT_PYTHON
    )


def violations_in(path: Path) -> list[str]:
    out: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}: syntax error {exc}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "engine" or alias.name.startswith("engine."):
                    out.append(f"{path}:{node.lineno}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "engine" or mod.startswith("engine."):
                out.append(f"{path}:{node.lineno}: imports from {mod}")
    for i, line in enumerate(text.splitlines(), 1):
        if GROUND_TRUTH_RE.search(line):
            out.append(f"{path}:{i}: references a ground-truth file")
    return out


def scan(root: Path = ROOT) -> list[str]:
    found: list[str] = []
    for d in product_dirs(root):
        for py in d.rglob("*.py"):
            if any(part in NOT_PYTHON for part in py.relative_to(root).parts):
                continue
            found.extend(violations_in(py))
    return found


def main() -> int:
    found = scan()
    if found:
        print("Engine isolation violations:")
        print("\n".join(found))
        return 1
    print(f"Engine isolation OK ({len(product_dirs())} product packages checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
