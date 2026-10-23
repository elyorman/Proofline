#!/usr/bin/env python3
"""Fail if product code imports `engine` or reads sealed ground truth.

Only `engine/` itself, `eval/`, `tests/` and `scripts/` may reference the
engine package or ground-truth files. Everything else, including the Python
API under `surfaces/` and loose files at the repo root, is product code and is checked.

Paths are found in string literals, never in comments or docstrings, so prose that
states the rule passes. This is a developer check, not a sandbox: the deployed images
are what keep the suites out of reach at runtime.
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
# A script reveals its planted moment as plainly as ground truth does.
ENGINE_DATA_RE = re.compile(r"\bengine[\\/]+(scripts|suites)\b")
ENGINE_DATA_PARTS = ("scripts", "suites")


def product_dirs(root: Path = ROOT) -> list[Path]:
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in EXEMPT | NOT_PYTHON
    )


def _strings(tree: ast.AST) -> list[ast.Constant]:
    """Every string literal except docstrings."""
    docs = set()
    for node in ast.walk(tree):
        scopes = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        if isinstance(node, scopes) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
    ]


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
    strings = _strings(tree)
    for s in strings:
        if GROUND_TRUTH_RE.search(s.value):
            out.append(f"{path}:{s.lineno}: references a ground-truth file")
        elif ENGINE_DATA_RE.search(s.value):
            out.append(f"{path}:{s.lineno}: references engine scripts or suites")
    # The path joined from parts: Path("engine") / "suites", .joinpath("scripts"), ...
    engine = [s for s in strings if s.value.strip("/\\") == "engine"]
    parts = [s for s in strings if s.value.strip("/\\").startswith(ENGINE_DATA_PARTS)]
    if engine and parts:
        out.append(f"{path}:{engine[0].lineno}: references engine scripts or suites")
    return out


def scan(root: Path = ROOT) -> list[str]:
    found: list[str] = []
    for py in sorted(root.glob("*.py")):
        found.extend(violations_in(py))
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
