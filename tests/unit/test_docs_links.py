"""Relative Markdown links in tracked documentation must resolve.

Scope: ``docs/**/*.md``, root ``*.md``, ``.claude/**/*.md``, ``.agents/**/*.md`` and the
READMEs under ``apps/``, ``packages/``, ``tools/`` and ``workers/``. A link target must exist;
a ``#fragment`` on a Markdown target must match a heading slug (GitHub rules) or an explicit
``<a id/name>`` anchor. External URLs, ``mailto:`` and fenced code blocks are skipped.
"""

from __future__ import annotations

import re
import subprocess
import unicodedata
from functools import cache
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).parents[2]

# Links that cannot be made to resolve without rewriting a dated record's meaning.
# Key: (source path, raw link target). Keep this list short and explain each entry.
ALLOWLIST: dict[tuple[str, str], str] = {}

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
# Inline links/images: [text](target "title") — target may be wrapped in <...>.
_INLINE_LINK = re.compile(
    r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+[\"'(][^)]*)?\)"
)
_REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_HTML_ANCHOR = re.compile(r"<a\s[^>]*(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _tracked(*patterns: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", *patterns],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    return sorted({p for p in out.split("\0") if p})


def documentation_files() -> list[str]:
    files = _tracked("docs/*.md", ".claude/*.md", ".agents/*.md")
    files += [p for p in _tracked("*.md") if "/" not in p]
    for top in ("apps", "packages", "tools", "workers"):
        files += [p for p in _tracked(f"{top}/*README.md") if Path(p).name == "README.md"]
    return sorted(set(files))


def _prose_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), 1):
        match = _FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append((number, line))
    return lines


def github_slug(heading: str) -> str:
    text = re.sub(r"<[^>]+>", "", heading)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # keep link text only
    text = text.replace("`", "").lower()
    kept = []
    for char in text:
        if char in " -_" or unicodedata.category(char)[0] in "LNM":
            kept.append(char)
    return "".join(kept).replace(" ", "-")


@cache
def anchors(path: Path) -> frozenset[str]:
    seen: dict[str, int] = {}
    found: set[str] = set()
    for _, line in _prose_lines(path.read_text(encoding="utf-8")):
        found.update(a.lower() for a in _HTML_ANCHOR.findall(line))
        match = _HEADING.match(line)
        if not match:
            continue
        slug = github_slug(match.group(2))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        found.add(slug if count == 0 else f"{slug}-{count}")
    return frozenset(found)


def links(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in _prose_lines(text):
        prose = _INLINE_CODE.sub("", line)
        targets = [m.group(1) for m in _INLINE_LINK.finditer(prose)]
        ref = _REF_DEF.match(prose)
        if ref:
            targets.append(ref.group(1))
        found.extend((number, target.strip("<>")) for target in targets)
    return found


def broken_links(rel: str) -> list[str]:
    source = ROOT / rel
    problems: list[str] = []
    for number, target in links(source.read_text(encoding="utf-8")):
        if _SCHEME.match(target) or target.startswith("//"):
            continue
        if (rel, target) in ALLOWLIST:
            continue
        path_part, _, fragment = target.partition("#")
        path_part = unquote(path_part.split("?", 1)[0])
        if not path_part:
            dest = source
        elif path_part.startswith("/"):
            dest = ROOT / path_part.lstrip("/")
        else:
            dest = source.parent / path_part
        if not dest.exists():
            problems.append(f"{rel}:{number}: missing target {target}")
            continue
        is_markdown = dest.is_file() and dest.suffix == ".md"
        if fragment and is_markdown and unquote(fragment).lower() not in anchors(dest.resolve()):
            problems.append(f"{rel}:{number}: missing anchor {target}")
    return problems


def test_github_slug_rules() -> None:
    assert github_slug("2026-10-18 — foundation status") == "2026-10-18--foundation-status"
    assert github_slug("Native upstream first — 2026-11-06") == "native-upstream-first--2026-11-06"
    assert github_slug("`gate.py` & *Friends*!") == "gatepy--friends"


def test_allowlist_entries_are_still_needed() -> None:
    for (rel, target), reason in ALLOWLIST.items():
        assert reason.strip()
        assert (ROOT / rel).is_file(), rel
        assert any(t == target for _, t in links((ROOT / rel).read_text(encoding="utf-8")))


def test_relative_markdown_links_resolve() -> None:
    files = documentation_files()
    assert "docs/BUILD-STATUS.md" in files and "README.md" in files
    problems = [problem for rel in files for problem in broken_links(rel)]
    assert not problems, f"{len(problems)} broken links:\n" + "\n".join(problems)
