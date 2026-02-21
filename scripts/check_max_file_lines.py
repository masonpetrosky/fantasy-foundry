#!/usr/bin/env python3
"""Fail CI when new source files exceed the max line-count threshold.

The threshold intentionally ignores existing legacy hotspots while preventing
new oversized modules from being introduced.
"""

from __future__ import annotations

from pathlib import Path

MAX_LINES = 1200
SOURCE_ROOTS = (
    ("backend", {".py"}),
    ("frontend/src", {".js", ".jsx"}),
)
EXEMPT_LEGACY_FILES = {
    Path("backend/runtime.py"),
    Path("backend/dynasty_roto_values.py"),
    Path("frontend/src/main.jsx"),
}
SKIP_PARTS = {".git", ".venv", "node_modules", "dist", "__pycache__"}


def _iter_candidate_files(repo_root: Path):
    for root_rel, allowed_exts in SOURCE_ROOTS:
        root = repo_root / root_rel
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(repo_root)
            if any(part in SKIP_PARTS for part in rel.parts):
                continue
            if file_path.suffix not in allowed_exts:
                continue
            yield rel


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    violations: list[tuple[Path, int]] = []
    legacy_oversized: list[tuple[Path, int]] = []

    for rel in sorted(_iter_candidate_files(repo_root)):
        count = _line_count(repo_root / rel)
        if count <= MAX_LINES:
            continue
        if rel in EXEMPT_LEGACY_FILES:
            legacy_oversized.append((rel, count))
            continue
        violations.append((rel, count))

    if violations:
        print(f"Line-count guardrail failed: files must be <= {MAX_LINES} lines.")
        for rel, count in violations:
            print(f" - {rel}: {count} lines")
        if legacy_oversized:
            print("Legacy exemptions currently above threshold:")
            for rel, count in legacy_oversized:
                print(f" - {rel}: {count} lines")
        return 1

    print(f"Line-count guardrail passed (max {MAX_LINES} lines for non-exempt files).")
    if legacy_oversized:
        print("Legacy exemptions currently above threshold:")
        for rel, count in legacy_oversized:
            print(f" - {rel}: {count} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
