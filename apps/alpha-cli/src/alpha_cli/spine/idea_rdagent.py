"""Link a stored RD-Agent journey to an idea card, and read it back for the idea file.

A link is one line in `ideas/links.jsonl`. An unlink is a later line: no line is edited or removed.
The link is outside the card's identity. The journey is read, never written.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from alpha_cli.spine import idea_card as cards
from alpha_cli.spine.errors import SpineError

LINK, UNLINK = "rdagent_journey", "rdagent_unlink"
SOURCE = "RD-Agent proposal"
STEP_NAME = "worked on by RD-Agent"
_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}")
_IDEA = re.compile(r"(0|[1-9][0-9]*)-([0-9a-f]{64})-([^/\\\x00]+)")
_META = re.compile(r"(?im)^\s*(?:declared_direction|primary_clock|direction_reason)\s*[:=].*$")
_NOT_RECORDED = "not recorded"


def _bad(ref: str) -> SpineError:
    return SpineError(
        "IDEA_RDAGENT_REF",
        f"{ref!r} is not a journey reference.",
        "Write it as <run>/<idea>, as the RD-Agent journey screen shows it.",
    )


def parse(ref: str) -> tuple[str, int, str, str]:
    """Split `<run>/<idea>` into (run, iteration, name, code hash). Fail loud on anything else."""
    run, sep, idea = ref.strip().partition("/")
    found = _IDEA.fullmatch(idea)
    if not sep or not _RUN.fullmatch(run) or found is None or found[3] in {".", ".."}:
        raise _bad(ref)
    return run, int(found[1]), found[3], found[2]


def _roots(home: Path) -> list[Path]:
    env = os.environ.get("ALPHA_RDAGENT_RUNS_DIR")
    return [Path(env)] if env else [home / "runs" / "rdagent", home.parent / "runs"]


def _missing(ref: str, why: str) -> SpineError:
    return SpineError(
        "IDEA_RDAGENT_JOURNEY_MISSING",
        f"There is no stored journey for {ref}: {why}.",
        "Build it first: alpha ledger journey --run-dir <run folder>.",
    )


def load_journey(home: Path, ref: str) -> dict[str, Any]:
    """Read the stored journey of one RD-Agent idea; the file must exist and name that idea."""
    run, iteration, name, digest = parse(ref)
    folder = f"{iteration}-{name}-{digest[:8]}"
    for root in _roots(home):
        path = root / run / "journey" / folder / "journey.json"
        if not path.is_file() or path.is_symlink():
            continue
        try:
            story = json.loads(path.read_bytes())
        except (OSError, ValueError) as exc:
            raise _missing(ref, f"the file cannot be read ({exc})") from exc
        if not isinstance(story, dict) or (
            story.get("iteration"),
            story.get("name"),
            story.get("code_sha256"),
        ) != (iteration, name, digest):
            raise _missing(ref, "the stored file belongs to another idea")
        return story
    raise _missing(ref, "no journey file was found")


def linked(home: Path, card: str) -> list[str]:
    """References linked now, in the order first linked. A later unlink line removes one."""
    refs: list[str] = []
    for row in cards.link_rows(home, card):
        ref = row.get("ref", "")
        if row.get("kind") == LINK and ref not in refs:
            refs.append(ref)
        elif row.get("kind") == UNLINK and ref in refs:
            refs.remove(ref)
    return refs


def _append(home: Path, card: str, kind: str, ref: str) -> None:
    folder = home / "ideas"
    folder.mkdir(parents=True, exist_ok=True)
    row = {"card": card, "kind": kind, "ref": ref}
    with (folder / cards.LINKS_FILE).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")


def link(home: Path, card: str, ref: str) -> tuple[str, bool]:
    """Link the journey after checking it exists. Returns (card id, newly linked)."""
    identity = cards.resolve(home, card)
    run, iteration, name, digest = parse(ref)
    ref = f"{run}/{iteration}-{digest}-{name}"
    load_journey(home, ref)
    if ref in linked(home, identity):
        return identity, False
    _append(home, identity, LINK, ref)
    return identity, True


def unlink(home: Path, card: str, ref: str) -> str:
    identity = cards.resolve(home, card)
    run, iteration, name, digest = parse(ref)
    ref = f"{run}/{iteration}-{digest}-{name}"
    if ref not in linked(home, identity):
        raise SpineError(
            "IDEA_RDAGENT_NOT_LINKED",
            f"The journey {ref} is not linked to idea card {identity}.",
            f"Run `alpha idea file {identity}` to see what is linked.",
        )
    _append(home, identity, UNLINK, ref)
    return identity


def card_from_journey(home: Path, ref: str) -> cards.IdeaCard:
    """A card in the agent's own words. Only the claim is stated; the other fields stay empty."""
    story = load_journey(home, ref)
    first = (story.get("steps") or [{}])[0]
    words = _META.sub("", str(first.get("own_words") or "")).strip()
    if not words or words == _NOT_RECORDED:
        raise _missing(ref, "the agent's own words for the idea were not recorded")
    return cards.IdeaCard(claim=words, source=SOURCE)


def _step(step: dict[str, Any]) -> dict[str, Any]:
    text = f"{step.get('text', '')} {step.get('what_this_means', '')}".lower()
    return {
        "title": step.get("title"),
        "who": step.get("who"),
        "text": step.get("text"),
        "numbers": [
            {k: n.get(k) for k in ("label", "value", "display", "gloss")}
            for n in step.get("numbers") or []
        ],
        "figure": step.get("figure"),
        "figure_reason": step.get("figure_reason"),
        "what_this_means": step.get("what_this_means"),
        "exploratory": "exploratory" in text,
    }


def _entry(home: Path, ref: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "ref": ref,
        "iteration": None,
        "name": None,
        "steps": [],
        "figures": [],
        "exploratory": False,
        "problem": None,
    }
    try:
        story = load_journey(home, ref)
    except SpineError as exc:
        entry["problem"] = f"the stored journey could not be read: {exc}"
        return entry
    steps = [_step(s) for s in story.get("steps") or []]
    figures = story.get("figures") or {}
    entry |= {
        "iteration": story["iteration"],
        "name": story["name"],
        "steps": steps,
        "figures": [
            {"id": key, "file": item.get("file"), "reason": item.get("reason")}
            for key, item in figures.items()
        ],
        "exploratory": any(s["exploratory"] for s in steps),
    }
    return entry


def entries(home: Path, card: str) -> list[dict[str, Any]]:
    return [_entry(home, ref) for ref in linked(home, card)]


def map_line(found: list[dict[str, Any]]) -> dict[str, Any]:
    refs = [e["ref"] for e in found if e["problem"] is None]
    return {
        "step": STEP_NAME,
        "state": "done" if refs else "not yet",
        "evidence": refs,
        "note": "a stored RD-Agent journey is linked to the card",
    }
