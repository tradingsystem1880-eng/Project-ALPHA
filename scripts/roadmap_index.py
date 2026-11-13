"""Generate/check docs/roadmap/README.md: the index of live plans, backlog, refactors and archive.

Sources (read-only):

* ``docs/superpowers/plans/*.md`` — live plans plus pinned finished plans (flat folder);
* ``docs/superpowers/plans/archive/YYYY-MM/*.md`` — completed and superseded plans;
* ``docs/roadmap/backlog/*.md`` and ``docs/roadmap/refactors/*.md``.

Run ``uv run python scripts/roadmap_index.py`` after adding, moving or changing any of them;
``--check`` exits 1 when the committed index is stale (``tests/unit/test_roadmap_index.py``
runs the same comparison).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[1]
PLANS = Path("docs/superpowers/plans")
ROADMAP = Path("docs/roadmap")
INDEX = ROADMAP / "README.md"
COMMAND = "uv run python scripts/roadmap_index.py"

_STATE = re.compile(
    r"^\*\*Delivery state:\*\* "
    r"(?P<state>Completed|Implemented – qualification pending|In progress|Blocked|Planned"
    r"|Superseded by \S+)"
    r"(?=$|\s—|\s\(|\.|;|,|\s\d{4}-)"
)
_FINISHED = ("Completed", "Superseded")
_LIVE_ORDER = ("In progress", "Implemented – qualification pending", "Blocked", "Planned")
_FIELD = re.compile(r"^\*\*(?P<key>[^*]+):\*\* (?P<value>.+)$")
_JSON_BLOCK = re.compile(r"^```json[ \t]*\n(.*?)\n```", re.S | re.M)
_MONTH = re.compile(r"\d{4}-\d{2}")
_PINNED_ANCHOR = (
    "../superpowers/plans/archive/README.md#pinned-exceptions-finished-but-kept-in-the-flat-folder"
)
_BACKLOG_STATUS = ("Idea", "Scoped")
_SIZES = ("S", "M", "L", "XL")
_RISKS = ("L", "M", "H")


class RoadmapError(ValueError):
    """A source document does not follow its template."""


def _cell(text: str) -> str:
    return text.replace("|", "\\|").strip()


def _title(rel: Path, text: str) -> str:
    fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and line.startswith("# "):
            return line[2:].strip()
    match = _JSON_BLOCK.search(text)
    if match is not None:
        try:
            block = json.loads(match.group(1))
        except ValueError as exc:
            raise RoadmapError(f"{rel}: front block is not valid JSON") from exc
        if isinstance(block, dict) and isinstance(block.get("title"), str):
            return str(block["title"])
    raise RoadmapError(f"{rel}: no '# ' title and no front-block title")


def _plan_state(rel: Path, text: str) -> str:
    states = [line for line in text.splitlines()[:12] if line.startswith("**Delivery state:**")]
    if len(states) != 1:
        raise RoadmapError(f"{rel}: expected one '**Delivery state:**' line in lines 1-12")
    match = _STATE.match(states[0])
    if match is None:
        raise RoadmapError(f"{rel}: Delivery state outside the vocabulary: {states[0]!r}")
    state = match.group("state")
    return "Superseded" if state.startswith("Superseded by ") else state


def _fields(rel: Path, text: str, required: dict[str, tuple[str, ...]]) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines()[:8]:
        match = _FIELD.match(line.strip())
        if match is not None:
            found[match.group("key")] = match.group("value").strip()
    for key, allowed in required.items():
        if found.get(key) not in allowed:
            raise RoadmapError(f"{rel}: '**{key}:**' must be one of {', '.join(allowed)}")
    return found


def _read(root: Path, rel: Path) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _docs(root: Path, folder: Path) -> list[Path]:
    return sorted(
        p.relative_to(root) for p in (root / folder).glob("*.md") if p.name != "README.md"
    )


def render(root: Path = ROOT) -> str:
    """The full expected text of docs/roadmap/README.md."""
    live: list[tuple[int, str, str, str, str]] = []
    pinned: list[tuple[str, str, str]] = []
    for rel in _docs(root, PLANS):
        text = _read(root, rel)
        state = _plan_state(rel, text)
        link = f"[{rel.name}](../superpowers/plans/{rel.name})"
        title = _cell(_title(rel, text))
        if state.startswith(_FINISHED):
            pinned.append((link, title, state))
        else:
            live.append((_LIVE_ORDER.index(state), rel.name, link, title, state))
    months: Counter[str] = Counter()
    for month_dir in sorted((root / PLANS / "archive").iterdir()):
        if not month_dir.is_dir():
            continue
        if not _MONTH.fullmatch(month_dir.name):
            raise RoadmapError(f"{month_dir.relative_to(root)}: archive folders must be YYYY-MM")
        for rel in _docs(root, month_dir.relative_to(root)):
            if not _plan_state(rel, _read(root, rel)).startswith(_FINISHED):
                raise RoadmapError(f"{rel}: archived plan is not Completed or Superseded")
            months[month_dir.name] += 1
    backlog: list[tuple[str, str, str]] = []
    for rel in _docs(root, ROADMAP / "backlog"):
        text = _read(root, rel)
        fields = _fields(rel, text, {"Status": _BACKLOG_STATUS, "Rough size": _SIZES})
        link = f"[{_cell(_title(rel, text))}](backlog/{rel.name})"
        backlog.append((link, fields["Status"], fields["Rough size"]))
    refactors: list[tuple[str, str]] = []
    for rel in _docs(root, ROADMAP / "refactors"):
        text = _read(root, rel)
        fields = _fields(rel, text, {"Risk": _RISKS})
        refactors.append((f"[{_cell(_title(rel, text))}](refactors/{rel.name})", fields["Risk"]))

    out = [
        f"<!-- GENERATED by scripts/roadmap_index.py: do not edit; run: {COMMAND} -->",
        "",
        "# Roadmap",
        "",
        "Generated index of planned and unplanned work. Do not edit this file by hand; change the",
        f"source documents and run `{COMMAND}` (`--check` reports a stale index).",
        "",
        "Lifecycle: an unplanned feature starts as a [backlog item](backlog/); when planned it",
        "becomes a dated plan in [`docs/superpowers/plans/`](../superpowers/plans/) with a",
        "`**Delivery state:**` line; when it is Completed or Superseded the plan moves to",
        "[`archive/YYYY-MM/`](../superpowers/plans/archive/). Structural refactors are staged in",
        "[refactors/](refactors/). Scope for the W01-W19 work packages is owned by the",
        "[feature readiness checklist](../context/feature-readiness-checklist-2026-10-27.md).",
        "",
        "What works today is on [STATUS.md](../../STATUS.md), generated by",
        "`uv run python scripts/status.py` from the [capability map](capabilities.toml); open",
        "owner decisions are on the [triage sheet](triage-2026-11.md).",
        "Work in progress (plans `In progress` or `Implemented – qualification pending`) may not",
        "exceed the `ceiling` in [wip-limit.json](wip-limit.json), and the ceiling must be",
        "lowered each time work closes. Once it reaches the `limit` of 3, at most 3 pieces of",
        "work may be open.",
        "",
        f"## Live plans ({len(live)})",
        "",
        "| Plan | Title | Delivery state | Month |",
        "| --- | --- | --- | --- |",
    ]
    for _, name, link, title, state in sorted(live):
        out.append(f"| {link} | {title} | {state} | {name[:7]} |")
    out += [
        "",
        f"## Finished plans pinned in the flat folder ({len(pinned)})",
        "",
        "These are finished but referenced by path from files that cannot be rewritten; see the",
        f"[archive README]({_PINNED_ANCHOR}).",
        "",
        "| Plan | Title | Delivery state |",
        "| --- | --- | --- |",
    ]
    out += [f"| {link} | {title} | {state} |" for link, title, state in pinned]
    out += [
        "",
        f"## Backlog ({len(backlog)})",
        "",
        "| Item | Status | Rough size |",
        "| --- | --- | --- |",
    ]
    out += [f"| {link} | {status} | {size} |" for link, status, size in backlog]
    out += [
        "",
        f"## Staged refactors ({len(refactors)})",
        "",
        "| Refactor | Risk |",
        "| --- | --- |",
    ]
    out += [f"| {link} | {risk} |" for link, risk in refactors]
    out += [
        "",
        f"## Archived plans ({sum(months.values())})",
        "",
        "| Month | Plans |",
        "| --- | --- |",
    ]
    out += [
        f"| [{month}](../superpowers/plans/archive/{month}/) | {count} |"
        for month, count in sorted(months.items())
    ]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the index is stale")
    args = parser.parse_args(argv)
    try:
        expected = render(ROOT)
    except RoadmapError as exc:
        print(f"roadmap_index: {exc}", file=sys.stderr)
        return 1
    target = ROOT / INDEX
    if args.check:
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current != expected:
            print(f"roadmap_index: {INDEX} is stale; run: {COMMAND}", file=sys.stderr)
            return 1
        return 0
    target.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
