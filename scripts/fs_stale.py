"""Staleness of the file system's living documents: did their sources change after verification?

A living document starts with front matter naming its ``owner``, the ``sources`` it describes
(git pathspec globs: ``*`` within a path segment, ``**`` across segments) and the commit at
which it was last ``verified``. A generated document declares ``generated_by`` instead of
``owner``/``verified``; its freshness is checked by its generator, so it is skipped here.

``stale`` reports every document whose sources were changed by a commit after ``verified``
(changes to the file system's own documents do not count). It is a report: problems that
make the check impossible (a glob matching no tracked file, an unknown commit)
are listed separately.
Read-only; standard library only.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FRONT_MATTER_KEYS = ("owner", "sources", "verified")
GENERATED_KEYS = ("generated_by", "sources")
_KEY = re.compile(r"^([a-z_]+):\s*(.*?)\s*$")
_ITEM = re.compile(r"^\s+-\s+(.+?)\s*$")


class FrontMatterError(ValueError):
    """The front matter block is present but malformed."""


def front_matter(text: str) -> dict[str, str | list[str]] | None:
    """Parse a leading ``---`` block of ``key: value`` and ``key:`` + ``  - item`` lines.

    Returns None when the text has no front matter. Only this small YAML subset is accepted.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    result: dict[str, str | list[str]] = {}
    current: str | None = None
    for number, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return result
        if not line.strip():
            continue
        item = _ITEM.match(line)
        if item and current is not None and isinstance(result[current], list):
            items = result[current]
            assert isinstance(items, list)
            items.append(item.group(1).strip("'\""))
            continue
        key = _KEY.match(line)
        if not key:
            raise FrontMatterError(f"line {number}: expected 'key: value' or '  - item'")
        name, value = key.group(1), key.group(2)
        if name in result:
            raise FrontMatterError(f"line {number}: duplicate key {name!r}")
        result[name] = value.strip("'\"") if value else []
        current = name
    raise FrontMatterError("front matter is not closed with '---'")


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def pathspecs(globs: list[str]) -> list[str]:
    return [f":(glob){pattern}" for pattern in globs]


def tracked_matches(root: Path, pattern: str) -> list[str]:
    return [p for p in git(root, "ls-files", "--", *pathspecs([pattern])).splitlines() if p]


def known_commit(root: Path, commit: str) -> str | None:
    """The full id of ``commit`` when it names a commit in this repository, else None."""
    if not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None if result.returncode == 0 else None


@dataclass
class Report:
    path: str
    verified: str
    changed_files: list[str] = field(default_factory=list)
    newest_commit: str | None = None
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "verified": self.verified,
            "changed_files": len(self.changed_files),
            "files": self.changed_files,
            "newest_commit": self.newest_commit,
            "problems": self.problems,
        }


def living_documents(root: Path) -> dict[str, dict[str, str | list[str]]]:
    """Tracked Markdown files whose front matter has ``owner``/``sources``/``verified``."""
    found: dict[str, dict[str, str | list[str]]] = {}
    for rel in git(root, "ls-files", "-z", "--", "*.md").split("\0"):
        path = root / rel
        if not rel or not path.is_file() or path.is_symlink():
            continue
        with path.open(encoding="utf-8") as handle:
            if handle.readline().strip() != "---":
                continue
        try:
            meta = front_matter(path.read_text(encoding="utf-8"))
        except FrontMatterError:
            continue  # Not a file-system document (other tools' YAML); the contract test owns ours.
        if meta is not None and "owner" in meta and "verified" in meta:
            found[rel] = meta
    return found


def check_document(
    root: Path, rel: str, meta: dict[str, str | list[str]], documents: tuple[str, ...] = ()
) -> Report:
    verified = meta.get("verified", "")
    sources = meta.get("sources", [])
    report = Report(rel, verified if isinstance(verified, str) else "")
    if not isinstance(sources, list) or not sources:
        report.problems.append("front matter has no 'sources' list")
        return report
    for pattern in sources:
        if not tracked_matches(root, pattern):
            report.problems.append(f"source glob matches no tracked file: {pattern}")
    commit = known_commit(root, report.verified)
    if commit is None:
        report.problems.append(f"'verified' is not a known commit: {report.verified or '(empty)'}")
    if report.problems:
        return report
    # Edits to file-system documents themselves (this one, or a routing file inside a source
    # tree) do not make a document stale: they are prose, checked by the link and contract tests.
    specs = [*pathspecs(sources), *(f":(exclude){doc}" for doc in sorted({rel, *documents}))]
    report.changed_files = [
        p
        for p in git(root, "diff", "--name-only", f"{commit}..HEAD", "--", *specs).splitlines()
        if p
    ]
    if report.changed_files:
        newest = git(root, "log", "-1", "--format=%H", f"{commit}..HEAD", "--", *specs).strip()
        report.newest_commit = newest or None
    return report


def stale(root: Path) -> list[Report]:
    """One report per living document, in path order."""
    documents = living_documents(root)
    names = tuple(documents)
    return [check_document(root, rel, meta, names) for rel, meta in sorted(documents.items())]


def render_text(reports: list[Report]) -> str:
    flagged = [r for r in reports if r.changed_files or r.problems]
    lines = [
        f"{len(reports)} living documents checked; {sum(bool(r.changed_files) for r in reports)} "
        f"stale; {sum(bool(r.problems) for r in reports)} with problems"
    ]
    for report in flagged:
        if report.problems:
            lines.append(f"PROBLEM {report.path}")
            lines.extend(f"  - {problem}" for problem in report.problems)
        else:
            lines.append(
                f"STALE   {report.path}: {len(report.changed_files)} source file(s) changed since "
                f"{report.verified}; newest change {report.newest_commit}"
            )
    if flagged:
        lines.append(
            "To fix: re-read the changed sources, correct the document, then set 'verified' to the "
            "commit you checked it against."
        )
    return "\n".join(lines)
