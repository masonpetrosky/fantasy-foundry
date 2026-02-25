#!/usr/bin/env python3
"""Fail CI on vulnerable direct Python dependencies.

This wraps `pip-audit` and filters findings to dependencies declared directly in
requirements.txt so transitive-only findings can be handled separately.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", str(name or "").strip().lower())


def _direct_requirement_names(requirements_path: Path) -> set[str]:
    direct: set[str] = set()
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", "--")):
            continue
        package = re.split(r"[<>=!~\s;\[]", line, maxsplit=1)[0].strip()
        if package:
            direct.add(_normalize_name(package))
    return direct


def _dependencies_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        deps = payload.get("dependencies", [])
        return [dep for dep in deps if isinstance(dep, dict)]
    if isinstance(payload, list):
        return [dep for dep in payload if isinstance(dep, dict)]
    return []


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    requirements_path = repo_root / "requirements.txt"
    if not requirements_path.exists():
        print(f"Requirements file not found: {requirements_path}")
        return 2

    direct_requirements = _direct_requirement_names(requirements_path)
    if not direct_requirements:
        print("No direct requirements discovered; skipping pip-audit gate.")
        return 0

    command = [sys.executable, "-m", "pip_audit", "-r", str(requirements_path), "-f", "json"]
    cache_root = Path(os.getenv("FF_PIP_AUDIT_CACHE_DIR", "/tmp/fantasy-foundry-pip-audit-cache"))
    cache_root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("XDG_CACHE_HOME", str(cache_root))
    result = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
    if result.returncode not in {0, 1}:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        return result.returncode

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if not stdout:
        if stderr:
            print(stderr, file=sys.stderr)
            return result.returncode or 1
        print("pip-audit produced no JSON output.", file=sys.stderr)
        return 2

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(f"Failed to parse pip-audit JSON output: {exc}", file=sys.stderr)
        return 2

    direct_findings: list[tuple[str, str, list[str]]] = []
    for dependency in _dependencies_from_payload(payload):
        package_name = str(dependency.get("name") or "").strip()
        package_key = _normalize_name(package_name)
        vulns = dependency.get("vulns") or []
        if package_key not in direct_requirements or not isinstance(vulns, list) or not vulns:
            continue
        vuln_ids = [str(item.get("id") or "unknown") for item in vulns if isinstance(item, dict)]
        direct_findings.append((package_name, str(dependency.get("version") or "unknown"), vuln_ids))

    if direct_findings:
        print("Direct Python dependency vulnerabilities detected:")
        for package_name, version, vuln_ids in sorted(direct_findings):
            ids = ", ".join(vuln_ids) if vuln_ids else "unknown"
            print(f" - {package_name} ({version}): {ids}")
        return 1

    print("No vulnerable direct Python dependencies detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
