from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "refresh_projection_workbook.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("refresh_projection_workbook", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_main_copies_workbook_runs_preprocess_and_stages(monkeypatch, tmp_path):
    module = _load_module()
    repo_root = tmp_path / "repo"
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True)
    target_workbook = data_dir / "Dynasty Baseball Projections.xlsx"
    target_workbook.write_bytes(b"old-workbook")
    source_workbook = tmp_path / "updated-workbook.xlsx"
    source_workbook.write_bytes(b"new-workbook")

    monkeypatch.setattr(module, "REPO_ROOT", repo_root)
    monkeypatch.setattr(module, "TARGET_WORKBOOK_PATH", target_workbook)

    commands: list[tuple[list[str], Path]] = []

    def fake_run(command, check, cwd):
        commands.append((list(command), Path(cwd)))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    exit_code = module.main([str(source_workbook), "--stage", "--quality-report", "tmp/report.json"])

    assert exit_code == 0
    assert target_workbook.read_bytes() == b"new-workbook"
    assert commands == [
        (
            [
                sys.executable,
                str(repo_root / "preprocess.py"),
                "--quality-report",
                "tmp/report.json",
            ],
            repo_root,
        ),
        (
            ["git", "add", "--", *module.TRACKED_PROJECTION_RELATIVE_PATHS],
            repo_root,
        ),
    ]


def test_main_uses_existing_workbook_without_copy(monkeypatch, tmp_path):
    module = _load_module()
    repo_root = tmp_path / "repo"
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True)
    target_workbook = data_dir / "Dynasty Baseball Projections.xlsx"
    target_workbook.write_bytes(b"existing-workbook")

    monkeypatch.setattr(module, "REPO_ROOT", repo_root)
    monkeypatch.setattr(module, "TARGET_WORKBOOK_PATH", target_workbook)

    commands: list[tuple[list[str], Path]] = []

    def fake_run(command, check, cwd):
        commands.append((list(command), Path(cwd)))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    exit_code = module.main(["--skip-dynasty-cache"])

    assert exit_code == 0
    assert target_workbook.read_bytes() == b"existing-workbook"
    assert commands == [
        (
            [
                sys.executable,
                str(repo_root / "preprocess.py"),
                "--skip-dynasty-cache",
            ],
            repo_root,
        ),
    ]


def test_main_rejects_non_xlsx_source(tmp_path):
    module = _load_module()
    text_file = tmp_path / "not-a-workbook.txt"
    text_file.write_text("bad", encoding="utf-8")

    exit_code = module.main([str(text_file)])

    assert exit_code == 2


def test_normalize_input_path_accepts_windows_drive_paths():
    module = _load_module()
    normalized = module._normalize_input_path(r"C:\Users\me\Dynasty Baseball Projections.xlsx")

    assert normalized == Path("/mnt/c/Users/me/Dynasty Baseball Projections.xlsx")
