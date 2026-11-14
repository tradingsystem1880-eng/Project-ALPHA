"""Search the tracked documentation: ranked excerpts with path, heading and lines.

Only Git-tracked regular files in the allow-listed documentation families below are read; owner
stores, data, tests, private suites and anything untracked are never inputs, symlinks are
refused, and links are returned as text, never followed. History is git log and pull requests,
not searched here. Results are pointers to read, not authority: a match does not prove that
anything is implemented.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

KINDS = ("all", "project", "feature", "task", "decision", "reference")
_ROOT_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    "CONTEXT.md",
    "STATUS.md",
    "docs/ARCHITECTURE.md",
}
# Workspace routing files: one CONTEXT.md per code area (never under the hidden test suite).
_ROUTING_NAME = "CONTEXT.md"
_HIDDEN_TESTS = "tests/holdout/"
# Reference material (Layer 3): every Markdown file under docs/reference/, at any depth.
_REFERENCE = "docs/reference/"
_FAMILIES = {
    "docs/adr": "decision",
    "docs/roadmap/backlog": "feature",
    "docs/roadmap/refactors": "feature",
    "docs/governance": "reference",
    "docs/operations": "reference",
    ".claude/rules": "reference",
}
# A task folder (docs/work/<task>/) holds a build's stage files while its pull request is open.
_TASK_FOLDER = re.compile(r"docs/work/[^/]+")
_TOKENS = re.compile(r"[a-z0-9]+")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_EXCERPT_LINES = 40
MAX_FILE_BYTES = 2_000_000
MAX_CORPUS_BYTES = 32_000_000
MAX_FILES = 2_000


@dataclass(frozen=True)
class Source:
    text: str
    kind: str


@dataclass(frozen=True)
class Section:
    path: str
    heading: str
    start: int
    end: int
    text: str
    kind: str
    score: int = 0

    def location(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "heading": self.heading,
            "start": self.start,
            "end": self.end,
            "kind": self.kind,
        }


def family(rel: str) -> str | None:
    """The document family of a tracked path, or None when it is not a search source."""
    if rel in _ROOT_FILES:
        return "project"
    path = PurePosixPath(rel)
    if rel.startswith(_HIDDEN_TESTS):
        return None
    if path.name == _ROUTING_NAME:
        return "project"
    if rel.startswith(_REFERENCE):
        return "reference" if path.suffix == ".md" else None
    if path.suffix not in {".md", ".txt", ".json"}:
        return None
    parent = path.parent.as_posix()
    if _TASK_FOLDER.fullmatch(parent):
        return "task" if path.suffix == ".md" else None
    return _FAMILIES.get(parent)


def read_sources(root: Path) -> dict[str, Source]:
    """Read current worktree bytes for Git-tracked, allow-listed regular files only."""
    root = root.resolve(strict=True)
    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached"],
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8")
    except subprocess.CalledProcessError as exc:
        raise ValueError("cannot enumerate tracked documents; root must be a Git checkout") from exc
    sources: dict[str, Source] = {}
    total = 0
    for rel in sorted(set(listing.rstrip("\0").split("\0"))):
        name = family(rel)
        if name is None:
            continue
        path = root / rel
        if any(part.is_symlink() for part in (path, *path.parents) if part != root):
            raise ValueError(f"document symlink is forbidden: {rel}")
        if not path.resolve(strict=True).is_relative_to(root):
            raise ValueError(f"document escapes repository: {rel}")
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"document must be a regular file <= 2 MB: {rel}")
        raw = path.read_bytes()
        total += len(raw)
        if total > MAX_CORPUS_BYTES or len(sources) >= MAX_FILES:
            raise ValueError("document corpus exceeds 32 MB / 2000 files")
        sources[rel] = Source(raw.decode("utf-8"), name)
    if not sources:
        raise ValueError("no tracked documents found")
    return sources


def sections(path: str, source: Source) -> list[Section]:
    """Heading-delimited excerpts of at most 40 lines; headings inside code fences are text."""
    lines = source.text.splitlines()
    found: list[Section] = []
    headings: list[tuple[int, str]] = []
    start = 0
    fence: str | None = None

    def emit(end: int) -> None:
        for first in range(start, end, _EXCERPT_LINES):
            last = min(first + _EXCERPT_LINES, end)
            text = "\n".join(lines[first:last])
            if text.strip():
                heading = " / ".join(title for _, title in headings)
                found.append(Section(path, heading, first + 1, last, text, source.kind))

    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else marker if fence is None else fence
        match = _HEADING.match(line) if fence is None else None
        if match:
            emit(index)
            level = len(match.group(1))
            headings = [(depth, title) for depth, title in headings if depth < level]
            headings.append((level, match.group(2)))
            start = index
    emit(len(lines))
    return found


def search_sections(sources: dict[str, Source], query: str, *, kind: str = "all") -> list[Section]:
    """Excerpts containing every query word; heading matches rank ahead of text matches."""
    terms = set(_TOKENS.findall(query.lower()))
    if not terms or len(query) > 160 or len(terms) > 12:
        raise ValueError("query must contain 1-12 words and at most 160 characters")
    if kind not in KINDS:
        raise ValueError(f"unknown document kind: {kind}")
    found: list[Section] = []
    for path, source in sorted(sources.items()):
        if kind != "all" and source.kind != kind:
            continue
        for row in sections(path, source):
            title_terms = set(_TOKENS.findall(row.heading.lower()))
            text_terms = set(_TOKENS.findall(row.text.lower()))
            if terms <= title_terms | text_terms:
                score = 10 * len(terms & title_terms) + len(terms & text_terms)
                found.append(
                    Section(
                        row.path,
                        row.heading,
                        row.start,
                        row.end,
                        row.text,
                        row.kind,
                        score,
                    )
                )
    return sorted(found, key=lambda row: (-row.score, row.path, row.start))


def search(
    root: Path, query: str, *, kind: str = "all", limit: int = 8, budget_bytes: int = 12_000
) -> dict[str, Any]:
    """The top ``limit`` excerpts within ``budget_bytes``; every other match is named, not shown."""
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer in [1, 20]")
    matches = search_sections(read_sources(root), query, kind=kind)
    shown: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    used = 0
    for row in matches:
        size = len(row.text.encode("utf-8"))
        # Stop at the first excerpt that does not fit, so what is shown keeps the ranking order.
        if not omitted and len(shown) < limit and used + size <= budget_bytes:
            shown.append({**row.location(), "score": row.score, "text": row.text})
            used += size
        else:
            omitted.append(row.location())
    return {
        "query": query,
        "kind": kind,
        "authority": "none",
        "matched": len(matches),
        "results": shown,
        "omitted": omitted,
    }


def render_text(payload: dict[str, Any], *, omitted_cap: int = 20) -> str:
    """Readable output: one header per excerpt, the source text verbatim, then what was left out."""
    results = payload["results"]
    lines = [
        f'{len(results)} of {payload["matched"]} matches for "{payload["query"]}" '
        f"(kind {payload['kind']}; a match is not proof of implementation)"
    ]
    for row in results:
        lines.extend(
            [
                "",
                f"== {row['path']}:{row['start']}-{row['end']} [{row['kind']}]",
                f"   {row['heading'] or '(no heading)'}",
                row["text"],
            ]
        )
    omitted = payload["omitted"]
    if omitted:
        lines.extend(["", f"Not shown ({len(omitted)}):"])
        lines.extend(
            f"- {row['path']}:{row['start']}-{row['end']} {row['heading']}"
            for row in omitted[:omitted_cap]
        )
        if len(omitted) > omitted_cap:
            lines.append(f"- ... and {len(omitted) - omitted_cap} more; narrow the query or --kind")
    return "\n".join(lines)
