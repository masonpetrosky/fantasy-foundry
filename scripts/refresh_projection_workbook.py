#!/usr/bin/env python3
"""Refresh projection artifacts from a local workbook copy."""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_WORKBOOK_PATH = REPO_ROOT / "data" / "Dynasty Baseball Projections.xlsx"
TRACKED_PROJECTION_RELATIVE_PATHS = (
    "data/Dynasty Baseball Projections.xlsx",
    "data/bat.json",
    "data/pitch.json",
    "data/bat_prev.json",
    "data/pit_prev.json",
    "data/meta.json",
    "data/dynasty_lookup.json",
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy an updated projection workbook into data/, run preprocess.py, "
            "and optionally stage the expected projection artifacts."
        ),
    )
    parser.add_argument(
        "source_xlsx",
        nargs="?",
        help=(
            "Optional path to the updated .xlsx workbook. If omitted, reuse "
            "data/Dynasty Baseball Projections.xlsx in-place."
        ),
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="Run git add for the expected projection workbook/data files after preprocess succeeds.",
    )
    parser.add_argument(
        "--skip-dynasty-cache",
        action="store_true",
        help="Pass through to preprocess.py for a faster run without rebuilding dynasty_lookup.json.",
    )
    parser.add_argument(
        "--quality-report",
        default="",
        help="Optional path passed through to preprocess.py --quality-report.",
    )
    return parser.parse_args(argv)


def _shell_join(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _normalize_input_path(raw_path: str) -> Path:
    text = str(raw_path or "").strip()
    if len(text) >= 3 and text[1] == ":" and text[0].isalpha() and text[2] in {"\\", "/"}:
        drive = text[0].lower()
        suffix = text[2:].replace("\\", "/").lstrip("/")
        return Path("/mnt") / drive / suffix
    return Path(text).expanduser()


def _resolve_source_path(raw_path: str) -> Path:
    path = _normalize_input_path(raw_path)
    resolved = path.resolve()
    if resolved.suffix.lower() != ".xlsx":
        raise ValueError(f"Expected an .xlsx workbook, got: {resolved}")
    if not resolved.exists():
        raise FileNotFoundError(f"Workbook not found: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"Workbook path is not a file: {resolved}")
    return resolved


def _copy_workbook(source_path: Path, *, target_path: Path) -> None:
    source_resolved = source_path.resolve()
    target_resolved = target_path.resolve()
    if source_resolved == target_resolved:
        print(f"Workbook already in place: {target_resolved}")
        return
    shutil.copy2(source_resolved, target_resolved)
    print(f"Copied workbook: {source_resolved} -> {target_resolved}")


def _build_preprocess_command(*, skip_dynasty_cache: bool, quality_report: str) -> list[str]:
    command = [sys.executable, str(REPO_ROOT / "preprocess.py")]
    if skip_dynasty_cache:
        command.append("--skip-dynasty-cache")
    report_path = str(quality_report or "").strip()
    if report_path:
        command.extend(["--quality-report", report_path])
    return command


def _run_command(command: Sequence[str], *, cwd: Path) -> None:
    print(f"$ {_shell_join(command)}")
    completed = subprocess.run(list(command), check=False, cwd=cwd)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _stage_projection_files() -> None:
    command = ["git", "add", "--", *TRACKED_PROJECTION_RELATIVE_PATHS]
    _run_command(command, cwd=REPO_ROOT)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        if args.source_xlsx:
            source_path = _resolve_source_path(args.source_xlsx)
            _copy_workbook(source_path, target_path=TARGET_WORKBOOK_PATH)
        elif not TARGET_WORKBOOK_PATH.exists():
            print(f"Workbook not found in repo: {TARGET_WORKBOOK_PATH}", file=sys.stderr)
            return 2
        else:
            print(f"Using existing workbook: {TARGET_WORKBOOK_PATH}")

        preprocess_command = _build_preprocess_command(
            skip_dynasty_cache=bool(args.skip_dynasty_cache),
            quality_report=args.quality_report,
        )
        _run_command(preprocess_command, cwd=REPO_ROOT)

        if args.stage:
            _stage_projection_files()
            print("Staged projection workbook artifacts.")
        else:
            print("Preprocess completed. Stage the projection artifacts when ready:")
            print(f"  git add -- {' '.join(TRACKED_PROJECTION_RELATIVE_PATHS)}")

        print('Next: git commit -m "Update projections"')
        print("Next: git push")
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
