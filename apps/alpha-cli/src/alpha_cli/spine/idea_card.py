"""The idea card: a short written note made before a test, stored one small TOML file per card.

A card id is a short hash of the card's normalised text. A card never changes and is never
deleted: a changed card is a new card that names the old one. A test links to a card by id; the
link is kept out of every test identity. A run first stored with a link names the card in its
manifest; the line in `ideas/links.jsonl` is written only after a run stored its result.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from alpha_cli.spine.errors import SpineError

ID_LENGTH = 12
NOT_STATED = "not stated"
# (field, plain label) in the order the card is read. These nine fields make the card's identity.
LABELS: dict[str, str] = {
    "claim": "The idea, in the owner's words",
    "mechanism": "Why it could work",
    "other_side": "Who is on the other side of the trade",
    "disproved_by": "What would disprove it",
    "baseline": "The simplest baseline it must beat",
    "signal_forms": "How long a signal takes to form",
    "held_for": "How long a trade is held",
    "how_often": "How often it happens",
    "edge_lasts": "How long the edge should last",
}
LINKS_FILE = "links.jsonl"
# RD-Agent link rows are kept in the same file. They are not tests: no test count reads them.
RDAGENT_KINDS = frozenset({"rdagent_journey", "rdagent_unlink"})


class IdeaCard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim: str = ""
    mechanism: str = ""
    other_side: str = ""
    disproved_by: str = ""
    baseline: str = ""
    signal_forms: str = ""
    held_for: str = ""
    how_often: str = ""
    edge_lasts: str = ""
    supersedes: str = ""
    source: str = ""

    def normalised(self) -> IdeaCard:
        return self.model_copy(
            update={name: " ".join(getattr(self, name).split()) for name in type(self).model_fields}
        )

    def not_stated(self) -> list[str]:
        return [name for name in LABELS if not getattr(self, name)]


def card_id(card: IdeaCard) -> str:
    """Short content hash of the nine content fields. `supersedes` and `source` are not content."""
    text = card.normalised()
    payload = json.dumps({name: getattr(text, name) for name in LABELS}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:ID_LENGTH]


def _folder(home: Path) -> Path:
    return home / "ideas"


def _toml(card: IdeaCard) -> str:
    lines = [
        f"{name} = {json.dumps(value, ensure_ascii=False)}"
        for name, value in card
        if value or name != "source"
    ]
    return "\n".join(lines) + "\n"


def save(home: Path, card: IdeaCard) -> tuple[str, bool]:
    """Write a new card; an identical card already stored is left alone. Returns (id, created)."""
    text = card.normalised()
    if text.supersedes:
        old = resolve(home, text.supersedes)
        text = text.model_copy(update={"supersedes": old})
    identity = card_id(text)
    path = _folder(home) / f"{identity}.toml"
    if path.is_file():
        stored = load(home, identity)
        if stored.model_copy(update={"source": ""}) != text.model_copy(update={"source": ""}):
            raise SpineError(
                "IDEA_CARD_CLASH",
                f"A different idea card is already stored under the id {identity}.",
                "Nothing was written. Change a word of the card, or name the card it replaces "
                "with `--supersedes` only when the text is new.",
            )
        return identity, False
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(f".{os.getpid()}.part")
    staged.write_text(_toml(text), encoding="utf-8")
    os.replace(staged, path)
    return identity, True


def resolve(home: Path, wanted: str) -> str:
    """Accept a full id or a unique prefix of at least four characters."""
    wanted = wanted.strip().lower()
    if not re.fullmatch(f"[0-9a-f]{{4,{ID_LENGTH}}}", wanted):
        raise unknown(wanted)
    found = [p.stem for p in _folder(home).glob("*.toml") if p.stem.startswith(wanted)]
    if len(found) != 1:
        raise unknown(wanted, ambiguous=len(found) > 1)
    return found[0]


def unknown(wanted: str, *, ambiguous: bool = False) -> SpineError:
    if ambiguous:
        return SpineError(
            "IDEA_CARD_AMBIGUOUS",
            f"More than one idea card starts with {wanted!r}.",
            "Give more characters of the card id. `alpha idea list` shows all ids.",
        )
    return SpineError(
        "IDEA_CARD_UNKNOWN",
        f"There is no idea card with the id {wanted!r}.",
        "Run `alpha idea list` to see the cards, or `alpha idea new` to write one.",
    )


def load(home: Path, wanted: str) -> IdeaCard:
    identity = resolve(home, wanted)
    path = _folder(home) / f"{identity}.toml"
    try:
        card = IdeaCard.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise SpineError(
            "IDEA_CARD_UNREADABLE",
            f"The idea card {identity} cannot be read: {exc}",
            "Do not edit card files. Write a new card with `alpha idea new`.",
        ) from exc
    if card_id(card) != identity:
        raise SpineError(
            "IDEA_CARD_CHANGED",
            f"The file for idea card {identity} no longer matches its id.",
            "Do not edit card files. Write a new card with `alpha idea new --supersedes`.",
        )
    return card


def all_ids(home: Path) -> list[str]:
    return sorted(p.stem for p in _folder(home).glob("*.toml"))


def _links(home: Path) -> list[dict[str, str]]:
    try:
        lines = (_folder(home) / LINKS_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return [row for row in rows if isinstance(row, dict)]


def tested_ids(home: Path) -> set[str]:
    return {row.get("card", "") for row in _links(home) if row.get("kind") not in RDAGENT_KINDS}


def linked_tests(home: Path, card: str) -> int:
    """How many stored test links name this card (one line per linked run)."""
    return len(links_of(home, card))


def links_of(home: Path, card: str) -> list[dict[str, str]]:
    """The stored test link rows that name this card, in the order they were written."""
    return [row for row in link_rows(home, card) if row.get("kind") not in RDAGENT_KINDS]


def link_rows(home: Path, card: str) -> list[dict[str, str]]:
    """Every stored link row that names this card, tests and RD-Agent links alike."""
    return [row for row in _links(home) if row.get("card") == card]


def link_fields(home: Path, card: str) -> dict[str, Any]:
    """Check a spec's card id. Returns what the run's manifest stores about the card."""
    return {"idea_card": resolve(home, card)} if card else {}


def note_link(home: Path, card: str, kind: str, ref: str) -> None:
    """Write the link line. Call it only after the run has stored its result."""
    if not card:
        return
    row = {"card": resolve(home, card), "kind": kind, "ref": ref}
    if row not in _links(home):
        with (_folder(home) / LINKS_FILE).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


def require(home: Path, card: str) -> None:
    """Fail early, in plain words, when a spec names a card that does not exist."""
    if card:
        resolve(home, card)


def counts(home: Path) -> dict[str, int]:
    ids = all_ids(home)
    return {"cards": len(ids), "without_test": len(set(ids) - tested_ids(home))}


def successors(home: Path) -> dict[str, str]:
    """Map each card id to the card that replaces it, if any."""
    found: dict[str, str] = {}
    for identity in all_ids(home):
        old = _raw_supersedes(home / "ideas" / f"{identity}.toml")
        if old:
            found[old] = identity
    return found


def _raw_supersedes(path: Path) -> str:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8")).get("supersedes", "")
    except (OSError, ValueError):
        return ""
    return value if isinstance(value, str) else ""


def card_from_file(path: Path) -> IdeaCard:
    if not re.search(r"\.toml$|\.json$", path.name):
        raise SpineError("IDEA_CARD_FILE", f"{path} is not .toml or .json.", "Use a .toml file.")
    try:
        raw = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.suffix == ".json"
            else tomllib.loads(path.read_text(encoding="utf-8"))
        )
        return IdeaCard.model_validate(raw)
    except (OSError, ValueError) as exc:
        raise SpineError(
            "IDEA_CARD_FILE",
            f"The card file {path} cannot be read: {exc}",
            "Check it against research/examples/idea-card.example.toml.",
        ) from exc
