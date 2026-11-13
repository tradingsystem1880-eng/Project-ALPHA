"""Local Git hooks: only the commit-message format can refuse a commit.

CI on the pull request is the merge gate. Run `uv run python scripts/gate.py check` for fast
local feedback; nothing here requires it, and partial staging or work-in-progress commits are fine.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import gate

COMMIT_SUBJECT = re.compile(
    r"^(feat|fix|test|build|chore|docs|refactor|ci|style|data)(\([^)]+\))?!?: .+"
)


def install(root: Path) -> None:
    existing = gate._git(root, "config", "--get", "core.hooksPath", check=False).strip()
    if existing and existing != ".githooks":
        raise ValueError(f"Refusing to replace existing core.hooksPath={existing!r}")
    gate._git(root, "config", "--local", "core.hooksPath", ".githooks")


def check_message(path: Path) -> tuple[int, str]:
    lines = path.read_text().splitlines()
    if lines and COMMIT_SUBJECT.match(lines[0]):
        return 0, ""
    return 1, "Use a conventional commit subject: type(scope): summary."


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["install"]:
        install(gate.repo_root())
        print("Git hooks installed for this repository; relative path supports linked worktrees.")
        return 0
    if len(args) == 2 and args[0] == "commit-msg":
        code, message = check_message(Path(args[1]))
        if message:
            print(message, file=sys.stderr)
        return code
    raise SystemExit("usage: git_guard.py install|commit-msg MESSAGE_FILE")


if __name__ == "__main__":
    raise SystemExit(main())
