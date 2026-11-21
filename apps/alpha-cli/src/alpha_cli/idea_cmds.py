"""`alpha idea`: write, read and list idea cards. Local files only; no network, no model."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from alpha_cli._cli_json import emit
from alpha_cli.spine import idea_card as cards
from alpha_cli.spine import idea_file
from alpha_cli.spine.errors import SpineError, fail
from alpha_cli.spine.idea_file_text import render
from alpha_core.config import AlphaSettings

idea_app = typer.Typer(help="Write an idea card before you test an idea.")
JSON = Annotated[bool, typer.Option("--json", help="Print the same facts as JSON.")]


def _text(label: str, value: str) -> str:
    return f"  {label}: {value or cards.NOT_STATED}"


def _show_text(identity: str, card: cards.IdeaCard, home: Path) -> str:
    lines = [f"Idea card {identity}"]
    lines += [_text(label, getattr(card, name)) for name, label in cards.LABELS.items()]
    missing = [cards.LABELS[name].lower() for name in card.not_stated()]
    if missing:
        lines.append("Not stated yet: " + "; ".join(missing) + ".")
    if card.supersedes:
        lines.append(f"Replaces card {card.supersedes}.")
    if card.source:
        lines.append(f"Source: {card.source}.")
    newer = cards.successors(home).get(identity)
    if newer:
        lines.append(f"Replaced by card {newer}.")
    status = "linked to a test" if identity in cards.tested_ids(home) else "no test yet"
    lines.append(f"The whole story on one page: alpha idea file {identity}")
    lines.append(f"Status: {status}. This card is a note. It is not a result and not advice.")
    return "\n".join(lines)


@idea_app.command("new")
def new(
    claim: str = typer.Option("", help="The idea, in your own words."),
    mechanism: str = typer.Option("", help="Why it could work."),
    other_side: str = typer.Option("", help="Who is on the other side of the trade."),
    disproved_by: str = typer.Option("", help="What result would disprove it."),
    baseline: str = typer.Option("", help="The simplest baseline it must beat."),
    signal_forms: str = typer.Option("", help="How long a signal takes to form."),
    held_for: str = typer.Option("", help="How long a trade is held."),
    how_often: str = typer.Option("", help="How often it happens."),
    edge_lasts: str = typer.Option("", help="How long the edge should last."),
    supersedes: str = typer.Option("", help="Id of the card this one replaces."),
    from_file: Annotated[Path | None, typer.Option("--from", help="A card file.")] = None,
    json_out: JSON = False,
) -> None:
    """Save a card. Any field may stay empty; it then reads "not stated"."""
    flags: dict[str, Any] = {
        "claim": claim,
        "mechanism": mechanism,
        "other_side": other_side,
        "disproved_by": disproved_by,
        "baseline": baseline,
        "signal_forms": signal_forms,
        "held_for": held_for,
        "how_often": how_often,
        "edge_lasts": edge_lasts,
        "supersedes": supersedes,
    }
    home = AlphaSettings().data_dir
    try:
        if from_file is not None:
            if any(flags.values()):
                raise SpineError(
                    "IDEA_CARD_MIXED",
                    "A card file and card flags cannot be used together.",
                    "Use `--from` alone, or the flags alone.",
                )
            card = cards.card_from_file(from_file)
        else:
            card = cards.IdeaCard(**flags)
        identity, created = cards.save(home, card)
    except SpineError as exc:
        fail(exc, json_out)
    path = home / "ideas" / f"{identity}.toml"
    word = "saved" if created else "already saved"
    emit(
        {"id": identity, "created": created, "path": str(path)},
        json_out=json_out,
        fallback=f"Idea card {identity} {word}.\nTo link a test to it, add idea_card = "
        f'"{identity}" to the spec.\nRead it again: alpha idea show {identity}',
    )


@idea_app.command("show")
def show(
    card_id: Annotated[str, typer.Argument(help="Card id (or its first characters).")],
    json_out: JSON = False,
) -> None:
    """Print one card, and name the fields that are not stated."""
    home = AlphaSettings().data_dir
    try:
        identity = cards.resolve(home, card_id)
        card = cards.load(home, identity)
    except SpineError as exc:
        fail(exc, json_out)
    facts = {
        "id": identity,
        **card.model_dump(),
        "not_stated": card.not_stated(),
        "tested": identity in cards.tested_ids(home),
    }
    emit(facts, json_out=json_out, fallback=_show_text(identity, card, home))


@idea_app.command("list")
def list_cards(json_out: JSON = False) -> None:
    """List every card with its idea and whether a test is linked to it."""
    home = AlphaSettings().data_dir
    tested = cards.tested_ids(home)
    rows: list[dict[str, Any]] = []
    for identity in cards.all_ids(home):
        try:
            card = cards.load(home, identity)
        except SpineError:
            continue
        rows.append(
            {
                "id": identity,
                "claim": card.claim,
                "tested": identity in tested,
                "not_stated": card.not_stated(),
                "tests_linked": cards.linked_tests(home, identity),
                "saved_at": cards.saved_at(home, identity),
            }
        )
    lines = [f"{len(rows)} idea card(s)"] if rows else ["No cards yet. Write one: alpha idea new."]
    lines += [
        f"  {r['id']}  {r['claim'] or cards.NOT_STATED}  "
        f"({'linked to a test' if r['tested'] else 'no test yet'}; "
        f"{len(r['not_stated'])} of {len(cards.LABELS)} fields not stated)"
        for r in rows
    ]
    emit({"cards": rows}, json_out=json_out, fallback="\n".join(lines))


@idea_app.command("file")
def file_cmd(
    card_id: Annotated[str, typer.Argument(help="Card id (or its first characters).")],
    json_out: JSON = False,
) -> None:
    """One page for one idea: the card, the map, every reading, the counts, the open points."""
    home = AlphaSettings().data_dir
    try:
        facts = idea_file.build(home, card_id)
    except SpineError as exc:
        fail(exc, json_out)
    emit(facts, json_out=json_out, fallback=render(facts))
