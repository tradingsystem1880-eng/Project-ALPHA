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


def _relative_luminance(colour: str) -> float:
    channels = [int(colour.lstrip("#")[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    first, second = _relative_luminance(foreground), _relative_luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


@pytest.mark.parametrize("surface", ["bg", "panel", "panel-2", "elevated"])
@pytest.mark.parametrize("text", ["ink", "ink-dim", "muted"])
def test_body_text_clears_wcag_aa_on_every_surface(text: str, surface: str) -> None:
    """Secondary text lands on whichever surface a panel happens to use.

    Tuning ``--muted`` against the page background alone is what let it ship at 4.48:1 on an
    expanded job row -- a real serious-impact axe failure, found only in the browser. This is
    the mechanical version of that check, so the next tweak cannot reintroduce it.
    """
    assert _contrast(_css_token(text), _css_token(surface)) >= 4.5


def test_the_faint_token_never_colours_text() -> None:
    """``--faint`` reads at 2.35:1. It is for hairlines; a glyph wearing it fails AA.

    It had spread to sequence numbers, feed timestamps and stage indices, each a serious
    axe violation waiting for whichever screen the accessibility gate happened to reach.
    """
    css = _CSS.read_text(encoding="utf-8")
    text_properties = re.findall(r"(color|fill)\s*:\s*var\(--faint\)", css)
    assert text_properties == [], "--faint may style rules and borders, never text"


def test_the_substrate_is_a_figure_only_token() -> None:
    """It exists so price can recede behind a finding; the page has no use for it."""
    theme = load_theme()
    assert theme.substrate not in {getattr(theme, name) for name in _SHARED}
