"""The stylesheet and the figure theme must not drift.

Python draws figures from ``alpha_dark.json``; the SPA styles the page from CSS custom
properties. If the two disagree, a figure stops matching the panel it sits in -- which is
exactly the seam this program set out to close. The canvas-side mirror is guarded by
``apps/alpha-web/frontend/src/util/theme.drift.test.ts``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alpha_research.figures import load_theme

_CSS = Path("apps/alpha-web/frontend/src/index.css")

#: Names both sides define. The theme also carries figure-only tokens (the substrate and
#: the categorical ramp) that the stylesheet has no reason to know about.
_SHARED = ("bg", "panel", "line", "grid", "ink", "muted", "accent", "up", "down", "gold")


def _css_token(name: str) -> str:
    match = re.search(rf"--{name}:\s*(#[0-9a-fA-F]{{6}})", _CSS.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError(f"--{name} is not defined in index.css")
    return match.group(1).lower()


@pytest.mark.parametrize("name", _SHARED)
def test_the_stylesheet_matches_the_figure_theme(name: str) -> None:
    assert _css_token(name) == getattr(load_theme(), name)


def test_ink_dim_is_defined_on_both_sides() -> None:
    assert _css_token("ink-dim") == load_theme().ink_dim


def test_the_substrate_is_a_figure_only_token() -> None:
    """It exists so price can recede behind a finding; the page has no use for it."""
    theme = load_theme()
    assert theme.substrate not in {getattr(theme, name) for name in _SHARED}
