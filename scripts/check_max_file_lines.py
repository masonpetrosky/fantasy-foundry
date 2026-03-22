#!/usr/bin/env python3
"""Fail CI when new source files exceed the max line-count threshold.

The threshold intentionally ignores existing legacy hotspots while preventing
new oversized modules from being introduced.
"""

from __future__ import annotations

from pathlib import Path

MAX_LINES = 1200
MAX_LINES_BY_PREFIX = (
    (Path("backend/core/runtime_projection_helpers.py"), 500),
    (Path("backend/core/runtime_security.py"), 500),
    (Path("backend/core/points_calculator.py"), 500),
    (Path("backend/core/points_calculator_preparation.py"), 500),
    (Path("backend/core/points_calculator_usage.py"), 500),
    (Path("backend/core/points_calculator_output.py"), 750),
    (Path("backend/valuation/cli_args.py"), 500),
    (Path("frontend/src/main.tsx"), 500),
    (Path("frontend/src/dynasty_calculator.tsx"), 500),
    (Path("frontend/src/features/projections/container.tsx"), 500),
    (Path("frontend/src/dynasty_calculator_config.ts"), 500),
    (Path("frontend/src/app_state_storage.ts"), 500),
    (Path("frontend/src/hooks"), 500),
    (Path("frontend/src/features/projections/hooks"), 500),
    (Path("frontend/src/features/projections/components"), 500),
)
SOURCE_ROOTS = (
    ("backend", {".py"}),
    ("frontend/src", {".js", ".jsx", ".ts", ".tsx"}),
)
EXEMPT_LEGACY_FILES: set[Path] = set()
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


def _max_lines_for(rel_path: Path) -> int:
    for prefix, limit in MAX_LINES_BY_PREFIX:
        if rel_path.is_relative_to(prefix):
            return limit
    return MAX_LINES


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    violations: list[tuple[Path, int, int]] = []
    legacy_oversized: list[tuple[Path, int]] = []

    for rel in sorted(_iter_candidate_files(repo_root)):
        count = _line_count(repo_root / rel)
        max_allowed = _max_lines_for(rel)
        if count <= max_allowed:
            continue
        if rel in EXEMPT_LEGACY_FILES:
            legacy_oversized.append((rel, count))
            continue
        violations.append((rel, count, max_allowed))

    if violations:
        print("Line-count guardrail failed.")
        print(f"Default max: {MAX_LINES} lines")
        for prefix, limit in MAX_LINES_BY_PREFIX:
            scope_label = f"{prefix}/**" if not prefix.suffix else str(prefix)
            print(f"Scoped max: {scope_label} <= {limit} lines")
        for rel, count, max_allowed in violations:
            print(f" - {rel}: {count} lines (max {max_allowed})")
        if legacy_oversized:
            print("Legacy exemptions currently above threshold:")
            for rel, count in legacy_oversized:
                print(f" - {rel}: {count} lines")
        return 1

    print(f"Line-count guardrail passed (default max {MAX_LINES} lines for non-exempt files).")
    for prefix, limit in MAX_LINES_BY_PREFIX:
        scope_label = f"{prefix}/**" if not prefix.suffix else str(prefix)
        print(f"Scoped max enforced: {scope_label} <= {limit} lines")
    if legacy_oversized:
        print("Legacy exemptions currently above threshold:")
        for rel, count in legacy_oversized:
            print(f" - {rel}: {count} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
