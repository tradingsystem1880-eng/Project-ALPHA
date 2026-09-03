"""The stylesheet and the figure theme must not drift.

Option E (spec 2026-09-01 §4.6) puts light chrome around black canvases, so the seam has two
halves: the figure theme mirrors into generated ``--canvas-*`` tokens (``alpha figures
theme-css``), and the hand-written chrome palette in ``index.css`` is contrast-tested against
every chrome surface a glyph can land on. The canvas-side mirror for canvas-land is guarded by
``apps/alpha-web/frontend/src/util/theme.drift.test.ts``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alpha_cli.figures_cmds import CANVAS_ROLES, theme_css
from alpha_research.figures import load_theme, theme_document

_CSS = Path("apps/alpha-web/frontend/src/index.css")
_GENERATED = Path("apps/alpha-web/frontend/src/theme.generated.css")

#: Chrome text tokens × the chrome surfaces they can sit on (title bars are the darkest).
_CHROME_TEXT = ("ink", "ink-dim", "muted", "accent", "gold", "up", "down")
_CHROME_SURFACES = ("bg", "panel", "panel-2", "elevated", "title")


def _token(css: str, name: str) -> str:
    match = re.search(rf"--{name}:\s*(#[0-9a-fA-F]{{6}})", css)
    if match is None:
        raise AssertionError(f"--{name} is not defined")
    return match.group(1).lower()


def test_generated_css_is_current() -> None:
    """`alpha figures theme-css --check` made mechanical: the committed file is byte-exact."""
    assert _GENERATED.read_text(encoding="utf-8") == theme_css(theme_document(load_theme()))


@pytest.mark.parametrize("role", CANVAS_ROLES)
def test_canvas_tokens_mirror_the_figure_theme(role: str) -> None:
    css = _GENERATED.read_text(encoding="utf-8")
    assert _token(css, f"canvas-{role.replace('_', '-')}") == getattr(load_theme(), role)


def test_the_terminal_geometry_is_generated() -> None:
    css = _GENERATED.read_text(encoding="utf-8")
    assert "--r: 0;" in css and "--r-lg: 0;" in css and "--font-size: 11px;" in css
    assert "--canvas-font: 11px Verdana, Tahoma" in css


def _relative_luminance(colour: str) -> float:
    channels = [int(colour.lstrip("#")[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    first, second = _relative_luminance(foreground), _relative_luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


@pytest.mark.parametrize("surface", _CHROME_SURFACES)
@pytest.mark.parametrize("text", _CHROME_TEXT)
def test_chrome_text_clears_wcag_aa_on_every_chrome_surface(text: str, surface: str) -> None:
    """The mockup's label/up/down values failed this by design: spec §4.6 says they are a
    starting point, not exempt. Tested against the darkest chrome surface too (title bars)."""
    css = _CSS.read_text(encoding="utf-8")
    assert _contrast(_token(css, text), _token(css, surface)) >= 4.5


def test_selection_ink_clears_aa_on_the_selection_colour() -> None:
    css = _CSS.read_text(encoding="utf-8")
    assert _contrast(_token(css, "selection-ink"), _token(css, "selection")) >= 4.5


def test_bevels_are_visible_against_the_panel() -> None:
    css = _CSS.read_text(encoding="utf-8")
    assert _contrast(_token(css, "bevel-dark"), _token(css, "panel")) >= 3.0
    assert _token(css, "bevel-light") != _token(css, "panel")


def test_the_faint_token_never_colours_text() -> None:
    """``--faint`` is for hairlines; a glyph wearing it fails AA."""
    css = _CSS.read_text(encoding="utf-8")
    text_properties = re.findall(r"(color|fill)\s*:\s*var\(--faint\)", css)
    assert text_properties == [], "--faint may style rules and borders, never text"


def test_the_substrate_is_a_figure_only_token() -> None:
    """It exists so price can recede behind a finding; the chrome has no use for it."""
    theme = load_theme()
    css = _CSS.read_text(encoding="utf-8")
    assert theme.substrate not in {_token(css, name) for name in _CHROME_TEXT + _CHROME_SURFACES}
