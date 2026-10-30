"""On-demand context views over tracked public sources, never a second ledger.

Only the explicit source families below are read. Links are returned as source text,
never followed; owner stores, private suites and working receipts are not inputs.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

KINDS = ("all", "project", "feature", "task", "decision", "history", "reference")
_ROOT_FILES = {"AGENTS.md", "CLAUDE.md", "docs/ARCHITECTURE.md", "docs/BUILD-STATUS.md"}
_FAMILIES = {
    "docs/context": "project",
    "docs/adr": "decision",
    "docs/superpowers/plans": "task",
    "docs/superpowers/specs": "feature",
    "docs/governance": "reference",
    "docs/operations": "reference",
    ".claude/rules": "reference",
}
_TOKENS = re.compile(r"[a-z0-9]+")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True)
class Source:
    text: str
    sha256: str
    kind: str


@dataclass(frozen=True)
class Section:
    path: str
    heading: str
    start: int
    end: int
    text: str
    source_sha256: str
    kind: str
    score: int = 0


def _kind(rel: str) -> str | None:
    if rel in _ROOT_FILES:
        return "history" if rel == "docs/BUILD-STATUS.md" else "project"
    path = PurePosixPath(rel)
    if path.suffix not in {".md", ".txt", ".json"}:
        return None
    if path.name.startswith("feature-readiness-checklist-") and path.parent == PurePosixPath(
        "docs/context"
    ):
        return "feature"
    return _FAMILIES.get(path.parent.as_posix())


def read_sources(root: Path) -> dict[str, Source]:
    """Read current worktree bytes for Git-tracked, allowlisted regular files only."""
    root = root.resolve(strict=True)
    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached"],
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8")
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            "cannot enumerate tracked context sources; root must be a Git checkout"
        ) from exc
    sources: dict[str, Source] = {}
    total = 0
    for rel in sorted(set(listing.rstrip("\0").split("\0"))):
        kind = _kind(rel)
        if kind is None:
            continue
        path = root / rel
        if any(part.is_symlink() for part in (path, *path.parents) if part != root):
            raise ValueError(f"context source symlink is forbidden: {rel}")
        if not path.resolve(strict=True).is_relative_to(root):
            raise ValueError(f"context source escapes repository: {rel}")
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError(f"context source must be a regular file <= 2 MB: {rel}")
        raw = path.read_bytes()
        total += len(raw)
        if total > 32_000_000 or len(sources) >= 2_000:
            raise ValueError("context corpus exceeds 32 MB / 2000 files")
        sources[rel] = Source(raw.decode("utf-8"), hashlib.sha256(raw).hexdigest(), kind)
    if not sources:
        raise ValueError("no tracked context sources found")
    return sources


def _sections(path: str, source: Source) -> list[Section]:
    lines = source.text.splitlines()
    sections: list[Section] = []
    headings: list[tuple[int, str]] = []
    start = 0
    fence: str | None = None

    def emit(end: int) -> None:
        # Retain adjacent caveats and status text; bound each excerpt without losing lines.
        for first in range(start, end, 40):
            last = min(first + 40, end)
            text = "\n".join(lines[first:last])
            if text.strip():
                sections.append(
                    Section(
                        path,
                        " / ".join(h for _, h in headings),
                        first + 1,
                        last,
                        text,
                        source.sha256,
                        source.kind,
                    )
                )

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
    return sections


def search_sections(sources: dict[str, Source], query: str, *, kind: str) -> list[Section]:
    """All query tokens must match an excerpt or its heading; deterministic ranking."""
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    terms = set(_TOKENS.findall(query.lower()))
    if not terms or len(query) > 160 or len(terms) > 12:
        raise ValueError("query must contain 1-12 words and at most 160 characters")
    if kind not in KINDS:
        raise ValueError(f"unknown context kind: {kind}")
    found: list[Section] = []
    for path, source in sorted(sources.items()):
        if kind != "all" and source.kind != kind:
            continue
        for row in _sections(path, source):
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
                        row.source_sha256,
                        row.kind,
                        score,
                    )
                )
    return sorted(found, key=lambda row: (-row.score, row.path, row.start))
