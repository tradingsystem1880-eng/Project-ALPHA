"""Generate/check STATUS.md: one plain-English page saying what works, what is in progress, what
waits for the owner and what is next.

Sources (read-only, all tracked): ``docs/roadmap/capabilities.toml`` (via scripts/capabilities.py),
``docs/roadmap/wip-limit.json``, live and archived plans in ``docs/work/``, and
``docs/roadmap/backlog`` and ``docs/roadmap/refactors``. Nothing else: no git history, network or
clock, so the page is identical on every machine.

Run ``uv run python scripts/status.py`` after changing any source; ``--check`` exits 1 when the
committed page is stale (``tests/unit/test_status_page.py`` runs the same comparison).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import capabilities
import roadmap_index
from capabilities import Capability, CapabilityError, CapabilityMap

ROOT = Path(__file__).parents[1]
PAGE = Path("STATUS.md")
WIP_FILE = Path("docs/roadmap/wip-limit.json")
TRIAGE_SHEET = "docs/roadmap/triage-2026-11.md"
COMMAND = "uv run python scripts/status.py"
MERGED_PRS = "https://github.com/tradingsystem1880-eng/Project-ALPHA/pulls?q=is%3Apr+is%3Amerged"

# Plan states that count as work in progress against the limit.
WIP_STATES = ("In progress", "Implemented – qualification pending")
_PLAIN_PLAN_STATE = {
    "In progress": "being worked on",
    "Implemented – qualification pending": "built but not yet checked end to end",
    "Blocked": "blocked",
    "Planned": "planned, not started",
}
_SIZE = {"S": "small", "M": "medium", "L": "large", "XL": "very large"}
_GROUPS = (
    ("KEEP", "Keep (finish and check it)"),
    ("SHELVE", "Shelve (keep the code, put it aside)"),
    ("DELETE", "Delete"),
    ("YOUR CALL", "Your call"),
)


class StatusError(ValueError):
    """A source file the status page reads is missing or malformed."""


@dataclass(frozen=True)
class WipLimit:
    limit: int
    ceiling: int


@dataclass(frozen=True)
class BacklogItem:
    title: str
    size: str


def read_wip_limit(root: Path) -> WipLimit:
    try:
        raw = json.loads((root / WIP_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StatusError(f"{WIP_FILE}: cannot read: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != {"limit", "ceiling"}:
        raise StatusError(f"{WIP_FILE}: must be an object with exactly 'limit' and 'ceiling'")
    data = cast(dict[str, object], raw)
    limit, ceiling = data["limit"], data["ceiling"]
    if not (isinstance(limit, int) and isinstance(ceiling, int)) or isinstance(limit, bool):
        raise StatusError(f"{WIP_FILE}: 'limit' and 'ceiling' must be whole numbers")
    if limit < 0 or ceiling < limit:
        raise StatusError(f"{WIP_FILE}: need 0 <= limit <= ceiling")
    return WipLimit(limit, ceiling)


def wip_count(cmap: CapabilityMap) -> int:
    return sum(1 for plan in cmap.live_plans if plan.state in WIP_STATES)


def _backlog(root: Path) -> list[BacklogItem]:
    items: list[BacklogItem] = []
    for rel in roadmap_index._docs(root, roadmap_index.ROADMAP / "backlog"):
        text = (root / rel).read_text(encoding="utf-8")
        fields = roadmap_index._fields(
            rel, text, {"Status": roadmap_index._BACKLOG_STATUS, "Rough size": roadmap_index._SIZES}
        )
        items.append(BacklogItem(roadmap_index._title(rel, text), fields["Rough size"]))
    # No priority order is recorded in the backlog, so list alphabetically.
    return sorted(items, key=lambda item: item.title.casefold())


def _archived(root: Path) -> int:
    return len(roadmap_index.archived_plans(root))


def _card_order(card: str) -> tuple[int, int, str]:
    """Numbered cards first, in number order, then lettered cards alphabetically."""
    return (0, int(card), "") if card.isdigit() else (1, 0, card)


def _how_to_see(cap: Capability) -> str:
    return "nothing to see yet (internal only)" if cap.internal_only else cap.see_it[0]


def _bullets(caps: list[Capability], line: str) -> list[str]:
    return [line.format(c=c) for c in caps] if caps else ["- None."]


def render(root: Path = ROOT) -> str:
    """The full expected text of STATUS.md."""
    try:
        cmap = capabilities.load(root)
    except CapabilityError as exc:
        raise StatusError(str(exc)) from exc
    wip = read_wip_limit(root)
    by_state: dict[str, list[Capability]] = {state: [] for state in capabilities.STATES}
    for cap in cmap.capabilities:
        by_state[cap.state].append(cap)
    plan_states = Counter(plan.state for plan in cmap.live_plans)
    in_wip = wip_count(cmap)
    triage = cmap.triage_items()
    waiting = [(name, t) for name, t in triage if not t.decided]
    backlog = _backlog(root)

    out = [
        "# ALPHA status",
        "",
        f"_Generated — do not edit; run: `{COMMAND}`_",
        "",
        "## At a glance",
        "",
        f"- **Capabilities:** {len(by_state['Working'])} working, "
        f"{len(by_state['Partial'])} partly working, {len(by_state['Demo only'])} demo only, "
        f"{len(by_state['Shelved'])} shelved, {len(by_state['Not started'])} not started.",
        f"- **Work in progress:** {in_wip} in progress (limit {wip.limit}).",
    ]
    out += [f"  - {plan_states[s]} {_PLAIN_PLAN_STATE[s]}" for s in WIP_STATES if plan_states[s]]
    others = [
        f"{plan_states[s]} {_PLAIN_PLAN_STATE[s]}"
        for s in capabilities.LIVE_STATES
        if s not in WIP_STATES and plan_states[s]
    ]
    if others:
        out.append(f"  - Not counted: {', '.join(others)}.")
    if wip.ceiling > wip.limit:
        out.append(
            f"  - Allowed for now: {wip.ceiling}. This number only goes down, until it "
            f"reaches {wip.limit}."
        )
    out += [
        f"- **Decisions waiting for you:** {len(waiting)}.",
        "",
        '"Working" means a test runs it from start to finish on made-up (synthetic) data.',
        "Runs on real market data are still to be confirmed on the Mac, except where noted.",
        "",
        "## What works today",
        "",
    ]
    for cap in by_state["Working"]:
        real = "" if cap.real_data.startswith("not yet") else " (a real run is recorded)"
        out.append(f"- **{cap.label}** — {_how_to_see(cap)}{real}")
    if not by_state["Working"]:
        out.append("- None.")
    out += ["", "## Partly working", ""]
    for cap in by_state["Partial"]:
        needs = f" Needs: {'; '.join(cap.needs)}." if cap.needs else ""
        out.append(f"- **{cap.label}** — {cap.missing}.{needs}")
    if not by_state["Partial"]:
        out.append("- None.")
    out += ["", "## Demo only", ""]
    out += _bullets(by_state["Demo only"], "- **{c.label}** — {c.missing}.")
    out += ["", "## Shelved", ""]
    out += _bullets(by_state["Shelved"], "- **{c.label}** — {c.missing}.")
    out += ["", "## Not started", ""]
    out += _bullets(by_state["Not started"], "- **{c.label}** — {c.missing}.")

    out += ["", "## In progress now", ""]
    in_progress = [p for p in cmap.live_plans if p.state == "In progress"]
    for plan in in_progress:
        summary = cmap.plan_summaries[plan.name]
        out.append(f"- **{summary.title}** — {summary.line}")
    if not in_progress:
        out.append("- None.")

    out += [
        "",
        "## Waiting for your decision",
        "",
        f"The full triage sheet, with what each item does and why: [{TRIAGE_SHEET}]"
        f'({TRIAGE_SHEET}). Write your answer in its "Your decisions" table.',
    ]
    for key, heading in _GROUPS:
        group = sorted(
            ((name, t) for name, t in waiting if t.recommendation.startswith(key)),
            key=lambda item: _card_order(item[1].card),
        )
        if not group:
            continue
        out += ["", f"**Recommended: {heading}**", ""]
        for name, t in group:
            note = " (your call)" if t.recommendation == "SHELVE (your call)" else ""
            out.append(f"- Card {t.card}: {name}{note}")
    if not waiting:
        out += ["", "- None."]

    out += ["", "## Next up", "", "Ideas not yet planned (no order recorded, so alphabetical):", ""]
    out += [f"- {item.title} — {_SIZE[item.size]} ({item.size})" for item in backlog]
    if not backlog:
        out.append("- None.")

    refactors = roadmap_index._docs(root, roadmap_index.ROADMAP / "refactors")
    out += [
        "",
        "## Housekeeping",
        "",
        f"- Live plans: {len(cmap.live_plans)}",
        f"- Archived plans: {_archived(root)}",
        f"- Backlog items: {len(backlog)}",
        f"- Staged refactors: {len(refactors)}",
        "",
        "## Where things are",
        "",
        "- [Roadmap: every plan, idea and refactor](docs/roadmap/README.md)",
        "- [Capability map: the source of this page](docs/roadmap/capabilities.toml)",
        f"- [Triage sheet: decisions for you]({TRIAGE_SHEET})",
        "- [Glossary: what the codes mean](docs/reference/glossary.md)",
        "- [How work gets done](docs/operations/development-loop.md)",
        f"- [Recently merged pull requests]({MERGED_PRS})",
    ]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if STATUS.md is stale")
    args = parser.parse_args(argv)
    try:
        expected = render(ROOT)
    except (StatusError, roadmap_index.RoadmapError) as exc:
        print(f"status: {exc}", file=sys.stderr)
        return 1
    target = ROOT / PAGE
    if args.check:
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current != expected:
            print(f"status: {PAGE} is stale; run: {COMMAND}", file=sys.stderr)
            return 1
        return 0
    target.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
