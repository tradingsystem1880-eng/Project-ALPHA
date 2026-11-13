"""Generate/check docs/reference/commands.md: one line per `alpha` command, one section per group.

The content comes from the CLI itself: the same catalogue that ``alpha info commands --all
--json`` prints (command id, arguments, options) plus each command's and group's own help text
for the one-phrase description. Nothing is written by hand, so the page cannot drift from the code.

Run ``uv run python scripts/commands_reference.py`` after adding, renaming or changing a
command; ``--check`` exits 1 when the committed page is stale
(``tests/unit/test_commands_reference.py`` runs the same comparison).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
OUTPUT = Path("docs/reference/commands.md")
COMMAND = "uv run python scripts/commands_reference.py"
MAX_LINE = 160
_SENTENCE = re.compile(r"^(.+?[.!?])(\s|$)")
_HIDDEN_OPTIONS = {"--help"}


def first_phrase(text: str | None) -> str:
    """The first sentence of a help text, on one line, without Markdown backticks."""
    if not text:
        return "(no description)"
    paragraph = " ".join(text.strip().split("\n\n", 1)[0].split())
    paragraph = paragraph.replace("`", "'").replace("|", "/")
    match = _SENTENCE.match(paragraph)
    return (match.group(1) if match else paragraph).rstrip()


def _walk(group: Any, prefix: str) -> Iterator[tuple[str, Any]]:
    for name, command in sorted(group.commands.items()):
        path = f"{prefix} {name}".strip()
        yield path, command
        if hasattr(command, "commands"):
            yield from _walk(command, path)


def load_cli() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """The CLI catalogue and a description for every command and group path."""
    import typer

    from alpha_cli.info_cmds import _command_catalog
    from alpha_cli.main import app

    tree = typer.main.get_command(app)
    descriptions = {path: first_phrase(cmd.help or cmd.short_help) for path, cmd in _walk(tree, "")}
    return _command_catalog(include_all=True), descriptions


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def command_line(entry: dict[str, Any], description: str) -> str:
    """``- `alpha x y <ARG>` — description. Options: `--a`, `--b`, +N more`` within 160 chars."""
    args = " ".join(f"<{arg['name'].upper()}>" for arg in entry["args"])
    head = f"- `alpha {entry['id']}{' ' + args if args else ''}` — "
    flags = [
        str(option["flag"]) + ("" if not option["required"] else " (required)")
        for option in sorted(entry["options"], key=lambda option: not option["required"])
        if option["flag"] and option["flag"] not in _HIDDEN_OPTIONS
    ]
    room = MAX_LINE - len(head)
    text = _shorten(description, max(24, room - 40 if flags else room))
    if not flags:
        return head + _shorten(text, room)
    shown: list[str] = []
    for index, flag in enumerate(flags):
        rest = len(flags) - index - 1
        candidate = ", ".join([*shown, f"`{flag}`"]) + (f", +{rest} more" if rest else "")
        if len(head) + len(text) + len(" Options: ") + len(candidate) > MAX_LINE:
            break
        shown.append(f"`{flag}`")
    if not shown:
        return head + _shorten(text, room)
    rest = len(flags) - len(shown)
    return head + text + " Options: " + ", ".join(shown) + (f", +{rest} more" if rest else "")


def render(catalog: list[dict[str, Any]], descriptions: dict[str, str]) -> str:
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in catalog:
        groups.setdefault(entry["id"].split(" ", 1)[0], []).append(entry)
    out = [
        "---",
        f"generated_by: {COMMAND}",
        "sources:",
        "  - apps/alpha-cli/src/alpha_cli/main.py",
        "  - apps/alpha-cli/src/alpha_cli/*_cmds.py",
        "---",
        "",
        "# Command reference",
        "",
        "Every `alpha` command, generated from the CLI's own command tree (the catalogue behind",
        "`alpha info commands --all --json` plus each command's help text). Do not edit by hand;",
        f"run `{COMMAND}`. Full options: `alpha <group> <command> --help`.",
        "",
        f"{len(catalog)} commands in {len(groups)} groups. Options marked (required) are",
        "mandatory; `<ARG>` is a positional argument.",
    ]
    for group in sorted(groups):
        entries = sorted(groups[group], key=lambda entry: entry["id"])
        out += ["", f"## alpha {group}", ""]
        if not (len(entries) == 1 and entries[0]["id"] == group):
            out += [_shorten(descriptions.get(group, "(no description)"), MAX_LINE), ""]
        out += [
            command_line(entry, descriptions.get(entry["id"]) or "(no description)")
            for entry in entries
        ]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the page is stale")
    args = parser.parse_args(argv)
    expected = render(*load_cli())
    target = ROOT / OUTPUT
    if args.check:
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current != expected:
            print(f"commands_reference: {OUTPUT} is stale; run: {COMMAND}", file=sys.stderr)
            return 1
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
