#!/usr/bin/env python3
"""Fail if product code imports `engine` or reads sealed ground truth.

Only `engine/` itself and `eval/` may reference the engine package or
ground-truth files. Run in CI and before every commit.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = {"engine", "eval", "tests", "scripts"}
PRODUCT_DIRS = [
    p
    for p in ROOT.iterdir()
    if p.is_dir()
    and not p.name.startswith(".")
    and p.name not in ALLOWED_ROOTS | {"docs", "infra", "surfaces", "data"}
]
GROUND_TRUTH_RE = re.compile(r"ground_truth[^\s\"']*\.(ya?ml|json)")


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


def main() -> int:
    found: list[str] = []
    for d in PRODUCT_DIRS:
        for py in d.rglob("*.py"):
            found.extend(violations_in(py))
    if found:
        print("Engine isolation violations:")
        print("\n".join(found))
        return 1
    print(f"Engine isolation OK ({len(PRODUCT_DIRS)} product packages checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
