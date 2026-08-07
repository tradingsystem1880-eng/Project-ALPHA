"""The figure theme is a data contract, and its palette is verified, never eyeballed.

The colour maths here mirrors the calibrated reference implementation the palette was
searched against: sRGB -> linear -> OKLab, WCAG relative luminance, and the Machado,
Oliveira & Fernandes (2009) colour-vision-deficiency transforms at severity 1.0 applied
in linear RGB. Distances are Euclidean in OKLab x100. Keep these constants in lockstep
with that reference; a drift here silently weakens every categorical figure.
"""

from __future__ import annotations

import json
import math
from importlib.resources import files
from itertools import combinations

import pytest

from alpha_research.figures import (
    CATEGORICAL_SLOTS,
    Theme,
    load_theme,
    theme_document,
)

# Thresholds. The CVD floor is the reference method's target, not its 6-8 relief band:
# ALPHA never ships a categorical pair that only survives with secondary encoding.
_CVD_MIN = 12.0
_NORMAL_MIN = 15.0
_CONTRAST_MIN = 3.0
_OKLCH_BAND = (0.48, 0.67)
_CHROMA_MIN = 0.10

_MACHADO: dict[str, tuple[tuple[float, float, float], ...]] = {
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritan": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}


def _linear(hex_colour: str) -> tuple[float, float, float]:
    raw = hex_colour.lstrip("#")
    channels = [int(raw[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return linear[0], linear[1], linear[2]


def _oklab(linear: tuple[float, float, float]) -> tuple[float, float, float]:
    red, green, blue = linear
    long_ = math.cbrt(0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue)
    medium = math.cbrt(0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue)
    short = math.cbrt(0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue)
    return (
        0.2104542553 * long_ + 0.7936177850 * medium - 0.0040720468 * short,
        1.9779984951 * long_ - 2.4285922050 * medium + 0.4505937099 * short,
        0.0259040371 * long_ + 0.7827717662 * medium - 0.8086757660 * short,
    )


def _relative_luminance(hex_colour: str) -> float:
    red, green, blue = _linear(hex_colour)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _simulate(hex_colour: str, kind: str) -> tuple[float, float, float]:
    linear = _linear(hex_colour)
    matrix = _MACHADO[kind]
    return tuple(  # type: ignore[return-value]
        min(1.0, max(0.0, sum(matrix[row][col] * linear[col] for col in range(3))))
        for row in range(3)
    )


def _delta_e(first: str, second: str, kind: str | None = None) -> float:
    left = _oklab(_simulate(first, kind) if kind else _linear(first))
    right = _oklab(_simulate(second, kind) if kind else _linear(second))
    return 100 * math.dist(left, right)


@pytest.fixture(scope="module")
def theme() -> Theme:
    return load_theme()


def test_theme_loads_with_every_declared_role(theme: Theme) -> None:
    assert theme.theme_id == "alpha-dark"
    assert theme.substrate and theme.substrate != theme.accent
    assert len(theme.categorical) == CATEGORICAL_SLOTS


def test_theme_digest_is_stable_and_content_addressed(theme: Theme) -> None:
    assert theme.digest() == load_theme().digest()
    assert len(theme.digest()) == 64


def test_theme_document_round_trips_through_json(theme: Theme) -> None:
    document = theme_document(theme)
    assert json.loads(json.dumps(document, sort_keys=True)) == document


def test_committed_theme_json_is_canonically_formatted() -> None:
    """The JSON is the authority the frontend generator reads; keep it diff-stable."""
    raw = (files("alpha_research.figures") / "themes" / "alpha_dark.json").read_text("utf-8")
    parsed = json.loads(raw)
    assert raw == json.dumps(parsed, indent=2, sort_keys=True) + "\n"


@pytest.mark.parametrize("slot", range(CATEGORICAL_SLOTS))
def test_every_categorical_slot_reads_as_a_mark_on_the_chart_surface(
    theme: Theme, slot: int
) -> None:
    colour = theme.categorical[slot]
    assert _contrast(colour, theme.bg) >= _CONTRAST_MIN, f"{colour} disappears into the surface"
    lightness, a_axis, b_axis = _oklab(_linear(colour))
    assert _OKLCH_BAND[0] <= lightness <= _OKLCH_BAND[1], f"{colour} L={lightness:.3f} out of band"
    assert math.hypot(a_axis, b_axis) >= _CHROMA_MIN, f"{colour} reads gray"


@pytest.mark.parametrize("kind", sorted(_MACHADO))
def test_categorical_pairs_stay_separable_under_colour_vision_deficiency(
    theme: Theme, kind: str
) -> None:
    """Every pair, not merely adjacent ones: a filter that drops a series must not
    collapse the survivors into each other."""
    worst = min(
        (_delta_e(left, right, kind), left, right)
        for left, right in combinations(theme.categorical, 2)
    )
    assert worst[0] >= _CVD_MIN, f"{kind}: {worst[1]} vs {worst[2]} only dE {worst[0]:.1f}"


def test_categorical_pairs_stay_separable_under_normal_vision(theme: Theme) -> None:
    worst = min(
        (_delta_e(left, right), left, right) for left, right in combinations(theme.categorical, 2)
    )
    assert worst[0] >= _NORMAL_MIN, f"{worst[1]} vs {worst[2]} only dE {worst[0]:.1f}"


def test_semantic_colours_are_never_reused_as_categorical_slots(theme: Theme) -> None:
    """Status colour is reserved. A 'series 4' that happens to be the loss red lies."""
    reserved = {theme.up, theme.down, theme.gold, theme.substrate}
    assert reserved.isdisjoint(set(theme.categorical))


def test_substrate_is_recessive_relative_to_every_subject_colour(theme: Theme) -> None:
    """The whole visual grammar depends on price sitting *behind* the finding."""
    substrate_contrast = _contrast(theme.substrate, theme.bg)
    for foreground in (theme.accent, theme.gold, theme.up, theme.down):
        assert _contrast(foreground, theme.bg) > substrate_contrast
