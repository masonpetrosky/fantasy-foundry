#!/usr/bin/env python3
"""Fail if Ruff per-file ignores drift beyond the approved allowlist."""

from __future__ import annotations

import ast
from pathlib import Path

EXPECTED_IGNORES: dict[str, set[str]] = {
    "backend/dynasty_roto_values.py": {"F401", "I001"},
}


def _load_ruff_per_file_ignores(pyproject_path: Path) -> dict[str, set[str]]:
    lines = pyproject_path.read_text(encoding="utf-8").splitlines()
    section_start = None
    for index, raw in enumerate(lines):
        if raw.strip() == "[tool.ruff.lint.per-file-ignores]":
            section_start = index + 1
            break

    if section_start is None:
        return {}

    parsed: dict[str, set[str]] = {}
    for raw in lines[section_start:]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            break
        if "=" not in stripped:
            continue
        key_text, value_text = stripped.split("=", 1)
        path = ast.literal_eval(key_text.strip())
        codes = ast.literal_eval(value_text.strip())
        parsed[str(path)] = {str(code) for code in codes}
    return parsed


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    actual = _load_ruff_per_file_ignores(pyproject_path)

    if actual == EXPECTED_IGNORES:
        print("Ruff per-file ignores check passed.")
        return 0

    print("Ruff per-file ignores check failed.")
    print("Expected:")
    for path in sorted(EXPECTED_IGNORES):
        print(f" - {path}: {sorted(EXPECTED_IGNORES[path])}")
    print("Found:")
    for path in sorted(actual):
        print(f" - {path}: {sorted(actual[path])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
