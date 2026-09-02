"""The terminal menu bar must have a home for every CLI command group (spec 2026-09-01 §4.2).

``menuModel.assignCommands`` throws at runtime on an unmapped group, so a new ``alpha`` command
group would blank the whole menu bar. This guard reads the frozen ``GROUP_MENU`` table out of the
TypeScript source and checks it against the served catalog before that can happen.
"""

from __future__ import annotations

import re
from pathlib import Path

from alpha_web.api.catalog import commands

_MENU_MODEL = (
    Path(__file__).resolve().parents[2]
    / "apps"
    / "alpha-web"
    / "frontend"
    / "src"
    / "shell"
    / "menuModel.ts"
)


def _mapped_groups() -> set[str]:
    source = _MENU_MODEL.read_text(encoding="utf-8")
    start = source.index("export const GROUP_MENU")
    end = source.index("})", start)
    table = source[start:end]
    return set(re.findall(r"^\s*'?([a-z][a-z-]*)'?:\s*'[A-Z][a-z]+',", table, flags=re.MULTILINE))


def test_every_catalog_command_group_has_a_menu() -> None:
    served = {str(entry["id"]).split(" ", 1)[0] for entry in commands()}
    mapped = _mapped_groups()
    assert served - mapped == set(), f"CLI groups with no menu: {sorted(served - mapped)}"
    assert mapped - served == set(), (
        f"menu groups the CLI no longer serves: {sorted(mapped - served)}"
    )
