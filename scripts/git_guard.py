"""Thin, bypassable local Git feedback; CI and owner authorization stay independent."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import gate


def install(root: Path) -> None:
    existing = gate._git(root, "config", "--get", "core.hooksPath", check=False).strip()
    if existing and existing != ".githooks":
        raise ValueError(f"Refusing to replace existing core.hooksPath={existing!r}")
    gate._git(root, "config", "--local", "core.hooksPath", ".githooks")


def check_commit(root: Path) -> tuple[int, str]:
    stamp = gate.read_json(root / gate.STATE_DIR / gate.STAMP_FILE)
    if not stamp or not gate.stamp_is_valid(root, "full"):
        return 1, "No full gate result for this tree. Run uv run python scripts/gate.py full."
    staged_tree = gate._git(root, "write-tree").strip()
    staged_hash = hashlib.sha256(staged_tree.encode()).hexdigest()
    if staged_hash != stamp.get("tree_hash") or staged_hash != gate.compute_tree_hash(root):
        return (
            1,
            "The staged tree differs from the tested worktree; stage the exact tested contents.",
        )
    # Classify both the removed and added paths even when Git detects a rename.
    paths = gate._git(root, "diff", "--cached", "--no-renames", "--name-only", "-z").split("\0")
    review_paths = [
        path
        for path in paths
        if gate.matches_risk(path)
        or gate.protected_reason(path)
        or path.startswith(".githooks/")
        or path
        in {
            "pyproject.toml",
            "scripts/git_guard.py",
            "scripts/gate_components.py",
            "scripts/wheel_smoke.py",
        }
    ]
    if review_paths:
        artifact = gate.read_json(root / gate.STATE_DIR / gate.REVIEW_VERDICT_FILE) or {}
        verdict = artifact.get("verdict", {})
        if (
            not gate.review_verdict_valid(root)
            or verdict.get("reviewed_tree_hash") != staged_hash
            or set(review_paths) - set(verdict.get("files_reviewed", []))
        ):
            return (
                1,
                "Risk/protected changes require independent tree-bound APPROVE review evidence.",
            )
    if any(gate.matches_quant(path) for path in paths) and not gate.quant_attestation_valid(root):
        return 1, "Quant changes require source-verification evidence for the current diff."
    return 0, ""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = gate.repo_root()
    if args == ["install"]:
        install(root)
        print("Git hooks installed for this repository; relative path supports linked worktrees.")
        return 0
    if args == ["pre-commit"]:
        code, message = check_commit(root)
    elif len(args) == 2 and args[0] == "commit-msg":
        lines = Path(args[1]).read_text().splitlines()
        message = lines[0] if lines else ""
        code = (
            0
            if re.match(
                r"^(feat|fix|test|build|chore|docs|refactor|ci|style|data)(\([^)]+\))?!?: .+",
                message,
            )
            else 1
        )
        message = "Use a conventional commit subject: type(scope): summary." if code else ""
    else:
        raise SystemExit("usage: git_guard.py install|pre-commit|commit-msg MESSAGE_FILE")
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
