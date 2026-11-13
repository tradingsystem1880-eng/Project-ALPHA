"""The file system's contract: small routing files, exact read lists, one home per fact.

The file system (ADR-0040) follows the Interpretable Context Methodology adapted to a codebase:

* Layer 1: the root ``CONTEXT.md`` routes every kind of task to a workspace.
* Layer 2: every workspace (each project under ``packages/``, ``apps/``, ``workers/``, ``tools/``,
  plus ``scripts/``, ``tests/`` and ``docs/``) has a ``CONTEXT.md`` with the sections Purpose,
  Read first, How to change it, Outputs. Its Read first table names exact files and sections.
* Layer 3: reference documents under ``docs/reference/``.

Every routing and reference document declares who owns it, which files it describes and the
commit it was verified against (``scripts/fs.py stale`` uses these). The "always read" set of a
workspace must stay within 32 KB. Failure messages say what to change.
"""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import fs_stale
import pytest

from tests.unit.test_docs_links import _FENCE, _HEADING, anchors, broken_links, github_slug

ROOT = Path(__file__).parents[2]
CONTEXT = "CONTEXT.md"
WORKSPACE_PARENTS = ("packages", "apps", "workers", "tools")
EXTRA_WORKSPACES = ("scripts", "tests", "docs")
REFERENCE_DIR = "docs/reference"
REQUIRED_SECTIONS = ("Purpose", "Read first", "How to change it", "Outputs")
CONTEXT_MAX_LINES = 80
REFERENCE_MAX_LINES = 200
MAX_LINE_CHARS = 160
ALWAYS_BUDGET_BYTES = 32_768
LIVING_KEYS = {"owner", "sources", "verified"}
GENERATED_KEYS = {"generated_by", "sources"}
_OWNER = re.compile(r"^[a-z][a-z0-9 ,/&()-]{2,40}$")
_LINK = re.compile(r"^\[[^\]]+\]\(([^)\s]+)\)$")
_COMING = "(coming)"
NONE_MARK = "—"


@dataclass(frozen=True)
class ReadRow:
    read: str
    target: str | None
    section: str
    when: str


def workspaces() -> list[str]:
    """Workspace directories, discovered from the tree (a project has a pyproject.toml)."""
    found = [
        path.relative_to(ROOT).as_posix()
        for parent in WORKSPACE_PARENTS
        for path in sorted((ROOT / parent).iterdir())
        if path.is_dir() and (path / "pyproject.toml").is_file()
    ]
    return [*found, *EXTRA_WORKSPACES]


def context_files() -> list[str]:
    return [CONTEXT, *(f"{ws}/{CONTEXT}" for ws in workspaces())]


@cache
def tracked_markdown(prefix: str) -> tuple[str, ...]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", f"{prefix}/*.md"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    untracked = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            f"{prefix}/*.md",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return tuple(sorted(set((out + untracked).split())))


def reference_files() -> list[str]:
    return list(tracked_markdown(REFERENCE_DIR))


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _body_lines(text: str) -> list[tuple[int, str]]:
    """(line index, line) outside fenced code blocks."""
    lines: list[tuple[int, str]] = []
    fence: str | None = None
    for index, line in enumerate(text.splitlines()):
        match = _FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append((index, line))
    return lines


def headings(text: str) -> list[tuple[int, int, str]]:
    """(line index, level, title) for every Markdown heading outside code fences."""
    found = []
    for index, line in _body_lines(text):
        match = _HEADING.match(line)
        if match:
            found.append((index, len(match.group(1)), match.group(2)))
    return found


def section_bytes(path: Path, section: str) -> int | None:
    """Bytes from the named heading to the next heading of the same or higher level."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    found = headings(text)
    wanted = github_slug(section)
    for position, (index, level, title) in enumerate(found):
        if github_slug(title) != wanted:
            continue
        end = next((i for i, lvl, _ in found[position + 1 :] if lvl <= level), len(lines))
        return len("".join(lines[index:end]).encode("utf-8"))
    return None


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def read_first_rows(rel: str) -> list[ReadRow]:
    """Rows of the table under ``## Read first`` (columns Read | Section | When)."""
    text = _text(rel)
    lines = text.splitlines()
    found = headings(text)
    start = next(i for i, level, title in found if level == 2 and title == "Read first")
    end = next((i for i, level, _ in found if i > start and level <= 2), len(lines))
    table = [line for line in lines[start + 1 : end] if line.strip().startswith("|")]
    assert table, f"{rel}: '## Read first' must contain a table with columns Read | Section | When"
    assert _cells(table[0]) == ["Read", "Section", "When"], (
        f"{rel}: the Read first table header must be exactly '| Read | Section | When |', "
        f"found {table[0]!r}"
    )
    rows = []
    for line in table[2:]:
        cells = _cells(line)
        assert len(cells) == 3, f"{rel}: Read first row needs exactly 3 cells: {line!r}"
        link = _LINK.match(cells[0])
        target = None
        if link:
            target = (
                (ROOT / rel).parent.joinpath(link.group(1)).resolve().relative_to(ROOT).as_posix()
            )
        rows.append(ReadRow(cells[0], target, cells[1], cells[2]))
    return rows


# ---------------------------------------------------------------------------------------------
# Every workspace has a routing file


def test_every_workspace_has_a_context_file() -> None:
    missing = [rel for rel in context_files() if not (ROOT / rel).is_file()]
    assert not missing, (
        "These code areas have no CONTEXT.md routing file; copy the shape of an existing one "
        "(for example packages/alpha-core/CONTEXT.md):\n" + "\n".join(missing)
    )


# ---------------------------------------------------------------------------------------------
# Size and shape


def _shape_problems(rel: str, max_lines: int | None) -> list[str]:
    lines = _text(rel).splitlines()
    problems = []
    if max_lines is not None and len(lines) > max_lines:
        problems.append(
            f"{rel}: {len(lines)} lines; the limit is {max_lines}. Move detail to a "
            "reference file and link to its section."
        )
    for number, line in enumerate(lines, 1):
        if len(line) > MAX_LINE_CHARS:
            problems.append(
                f"{rel}:{number}: line is {len(line)} characters; wrap it at {MAX_LINE_CHARS}."
            )
    return problems


def _front_matter_problems(rel: str, *, allow_generated: bool) -> list[str]:
    try:
        meta = fs_stale.front_matter(_text(rel))
    except fs_stale.FrontMatterError as exc:
        return [f"{rel}: front matter is malformed ({exc})"]
    if meta is None:
        return [f"{rel}: must start with front matter (--- owner / sources / verified ---)"]
    keys = set(meta)
    problems = []
    if allow_generated and "generated_by" in keys:
        if keys != GENERATED_KEYS:
            problems.append(
                f"{rel}: a generated file declares exactly generated_by and sources, "
                f"found {sorted(keys)}"
            )
    elif keys != LIVING_KEYS:
        problems.append(
            f"{rel}: front matter keys must be exactly owner, sources, verified; "
            f"found {sorted(keys)}"
        )
    owner = meta.get("owner")
    if owner is not None and not (isinstance(owner, str) and _OWNER.match(owner)):
        problems.append(
            f"{rel}: owner must be a short lowercase role phrase such as "
            f"'data layer', not a person; found {owner!r}"
        )
    sources = meta.get("sources")
    if not isinstance(sources, list) or not sources:
        problems.append(f"{rel}: sources must be a non-empty list of globs")
    else:
        problems += [
            f"{rel}: source glob {pattern!r} matches no tracked file; fix or remove it"
            for pattern in sources
            if not fs_stale.tracked_matches(ROOT, pattern)
        ]
    verified = meta.get("verified")
    if "verified" in keys and not (
        isinstance(verified, str) and fs_stale.known_commit(ROOT, verified)
    ):
        problems.append(
            f"{rel}: verified {verified!r} is not a commit in this repository; set it "
            "to the commit you checked the document against"
        )
    return problems


def test_context_files_are_small_and_declare_owner_sources_verified() -> None:
    problems = []
    for rel in context_files():
        if (ROOT / rel).is_file():
            problems += _shape_problems(rel, CONTEXT_MAX_LINES)
            problems += _front_matter_problems(rel, allow_generated=False)
    assert not problems, "\n".join(problems)


def test_reference_files_are_small_and_declare_owner_sources_verified() -> None:
    files = reference_files()
    assert files, "docs/reference/ has no Markdown files"
    problems = []
    for rel in files:
        generated = "generated_by" in (fs_stale.front_matter(_text(rel)) or {})
        problems += _shape_problems(rel, None if generated else REFERENCE_MAX_LINES)
        problems += _front_matter_problems(rel, allow_generated=True)
    assert not problems, "\n".join(problems)


def test_context_sections_appear_in_order() -> None:
    problems = []
    for rel in context_files():
        if not (ROOT / rel).is_file():
            continue
        titles = [title for _, level, title in headings(_text(rel)) if level == 2]
        present = [title for title in titles if title in REQUIRED_SECTIONS]
        if present != list(REQUIRED_SECTIONS):
            problems.append(
                f"{rel}: needs the sections {', '.join(REQUIRED_SECTIONS)} once each, "
                f"in that order; found {titles}"
            )
    assert not problems, "\n".join(problems)


# ---------------------------------------------------------------------------------------------
# Read first tables resolve to real files and headings


def test_read_first_rows_resolve_to_existing_files_and_sections() -> None:
    problems = []
    for rel in context_files():
        if not (ROOT / rel).is_file():
            continue
        for row in read_first_rows(rel):
            if row.target is None:
                if rel == CONTEXT and _COMING in row.read and "](" not in row.read:
                    continue
                problems.append(
                    f"{rel}: Read cell must be a relative Markdown link: {row.read!r} "
                    f"(only the root file may list '{_COMING}' rows without a link)"
                )
                continue
            if not (ROOT / row.target).is_file():
                problems.append(f"{rel}: {row.target} does not exist")
                continue
            if row.section != NONE_MARK and github_slug(row.section) not in anchors(
                (ROOT / row.target).resolve()
            ):
                problems.append(
                    f"{rel}: {row.target} has no heading {row.section!r}; use an "
                    f"exact heading from that file or '{NONE_MARK}' for the whole file"
                )
            if not row.when or len(row.when) > 120:
                problems.append(f"{rel}: When must be 'always' or a short condition: {row.when!r}")
        problems += broken_links(rel)
    assert not problems, "\n".join(problems)


def _always_bytes(rel: str) -> tuple[int, list[str]]:
    total, problems = 0, []
    for row in read_first_rows(rel):
        if row.when != "always" or row.target is None:
            continue
        path = ROOT / row.target
        if row.section == NONE_MARK:
            total += path.stat().st_size
            continue
        size = section_bytes(path, row.section)
        if size is None:
            problems.append(f"{rel}: always row names a missing section {row.section!r}")
        else:
            total += size
    return total, problems


def test_always_read_budget_per_workspace() -> None:
    root_bytes = (ROOT / CONTEXT).stat().st_size
    root_always, problems = _always_bytes(CONTEXT)
    report = []
    over = []
    for ws in workspaces():
        rel = f"{ws}/{CONTEXT}"
        if not (ROOT / rel).is_file():
            continue
        own, own_problems = _always_bytes(rel)
        problems += own_problems
        total = root_bytes + root_always + (ROOT / rel).stat().st_size + own
        report.append(f"{ws}: {total:,} bytes")
        if total > ALWAYS_BUDGET_BYTES:
            over.append(ws)
    assert not problems, "\n".join(problems)
    assert not over, (
        f"The always-read set (root CONTEXT.md + workspace CONTEXT.md + every 'always' row) is "
        f"over "
        f"{ALWAYS_BUDGET_BYTES:,} bytes for {', '.join(over)}. Point 'always' rows at smaller "
        "sections or make them conditional.\n" + "\n".join(report)
    )


# ---------------------------------------------------------------------------------------------
# The root routes to every workspace


def test_root_routes_to_every_workspace() -> None:
    targets = {row.target for row in read_first_rows(CONTEXT)}
    missing = [ws for ws in workspaces() if f"{ws}/{CONTEXT}" not in targets]
    assert not missing, (
        "The root CONTEXT.md routing table (## Read first) has no row linking to these "
        "workspaces' CONTEXT.md:\n" + "\n".join(missing)
    )


# ---------------------------------------------------------------------------------------------
# One home per fact


def _paragraphs(text: str) -> list[str]:
    body = text
    if text.startswith("---\n"):
        body = text.split("\n---\n", 1)[1] if "\n---\n" in text else ""
    blocks, current = [], []
    for line in body.splitlines():
        if line.strip():
            current.append(" ".join(line.split()))
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return ["\n".join(block) for block in blocks if len(block) >= 3]


def test_no_paragraph_is_repeated_across_files() -> None:
    seen: dict[str, list[str]] = defaultdict(list)
    for rel in [*context_files(), *reference_files()]:
        if (ROOT / rel).is_file():
            for paragraph in set(_paragraphs(_text(rel))):
                seen[paragraph].append(rel)
    repeated = [
        f"{', '.join(files)}:\n  {paragraph.splitlines()[0][:100]}..."
        for paragraph, files in seen.items()
        if len(files) > 1
    ]
    assert not repeated, (
        "A paragraph of three or more lines appears in more than one file. Keep it in one home "
        "and link to it from the others:\n" + "\n".join(repeated)
    )


# ---------------------------------------------------------------------------------------------
# The checker itself


def test_section_bytes_stops_at_the_next_heading_of_same_or_higher_level(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "# T\n## A\nx\n### A1\ny\n```\n## not a heading\n```\n## B\nz\n", encoding="utf-8"
    )
    assert section_bytes(doc, "A") == len("## A\nx\n### A1\ny\n```\n## not a heading\n```\n")
    assert section_bytes(doc, "B") == len("## B\nz\n")
    assert section_bytes(doc, "Missing") is None


@pytest.mark.parametrize(
    ("owner", "ok"),
    [("data layer", True), ("command line research", True), ("Jane Smith", False), ("x", False)],
)
def test_owner_is_a_role_phrase(owner: str, ok: bool) -> None:
    assert bool(_OWNER.match(owner)) is ok
