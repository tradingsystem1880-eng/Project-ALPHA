"""Local coding-session README evidence. Checks freshness/scope, not semantic truth."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import gate
import gate_components

STATE_FILE = "readme-review.json"


def context(root: Path) -> dict[str, Any]:
    """Always consider the whole branch against locally fetched main, including removals."""
    result = gate_components.comparison_context(root, "origin/main")
    base = result["merge_base"]
    if not base:
        raise ValueError(
            "Fetch origin/main before reviewing README; comparison base is unavailable"
        )
    paths = gate._git(root, "diff", "--no-renames", "--name-only", "-z", base)
    paths += gate._git(root, "ls-files", "--others", "--exclude-standard", "-z")
    result["paths"] = sorted(set(filter(None, paths.split("\0"))))
    return result


def _validate(root: Path, report: dict[str, Any], scope: dict[str, Any]) -> None:
    if set(report) != {"reviewed_tree_hash", "disposition", "rationale"}:
        raise ValueError("README review report fields are invalid")
    if report.get("reviewed_tree_hash") != gate.compute_tree_hash(root):
        raise ValueError("README review is stale for the final branch tree")
    expected = "updated" if "README.md" in scope["paths"] else "no_change"
    if report.get("disposition") != expected:
        raise ValueError(f"README disposition must be {expected} for the branch diff")
    reason = report.get("rationale")
    if not isinstance(reason, str) or not 20 <= len(reason.strip()) <= 2000:
        raise ValueError("README review needs a substantive rationale (20–2000 characters)")
    readme = root / "README.md"
    if not readme.is_file() or readme.is_symlink():
        raise ValueError("README.md must be a regular repository file before delivery")
    tracked = set(gate._git(root, "ls-files", "-z").split("\0"))
    for target in re.findall(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", readme.read_text()):
        link = urlsplit(target)
        if link.scheme in {"http", "https", "mailto"}:
            continue  # External URLs and anchors still need the coding session's review.
        path = Path(unquote(link.path)) if link.path else Path("README.md")
        resolved = root / path
        if (
            link.scheme
            or path.is_absolute()
            or not resolved.resolve().is_relative_to(root.resolve())
            or not resolved.is_file()
        ):
            raise ValueError(f"README local link target is invalid: {target}")
        if resolved.resolve().relative_to(root.resolve()).as_posix() not in tracked:
            raise ValueError(f"README local link target is not in the staged repository: {target}")


def attest(root: Path, payload: str) -> int:
    """Record an explicit session decision through the existing native attest command."""
    from harness_models import ReadmeReview

    try:
        report = ReadmeReview.model_validate_json(payload)
        scope = context(root)
        _validate(root, report.model_dump(), scope)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"README review rejected: {exc}", file=sys.stderr)
        return 1
    gate.write_json_atomic(
        gate._state_dir(root) / STATE_FILE,
        {
            "schema_version": 1,
            "created_at": gate._now(),
            "comparison": gate_components.binding(scope),
            "changed_paths": scope["paths"],
            "report": report.model_dump(),
        },
    )
    gate.append_audit(root, "readme_reviewed", report.disposition)
    return 0


def check(root: Path) -> tuple[bool, str]:
    """Stdlib-only reader for installed Git hooks; no inference or network access."""
    artifact = gate.read_json(root / gate.STATE_DIR / STATE_FILE) or {}
    report = artifact.get("report")
    if artifact.get("schema_version") != 1 or not isinstance(report, dict):
        return False, "README review evidence is missing or malformed"
    try:
        scope = context(root)
        if (
            artifact.get("comparison") != gate_components.binding(scope)
            or artifact.get("changed_paths") != scope["paths"]
        ):
            raise ValueError("README review comparison/scope is stale")
        _validate(root, report, scope)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return True, ""
