"""The one authority for figure colour, shared by Python figures and the Workstation SPA.

The committed JSON beside this module is the source of truth. Python loads it directly;
the frontend generates its CSS custom properties and canvas token mirror from the same
document, and CI fails on drift. Nothing here reads the stylesheet -- a Python-only
install with no frontend must still render correctly themed figures.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from functools import lru_cache
from importlib.resources import files
from typing import Final

from alpha_core import DataError
from alpha_research._canonical import canonical_sha256

#: How many distinct series a categorical figure may colour before it must aggregate.
#: Four is not a round number chosen for tidiness -- it is the largest set that clears
#: every separability check on this surface, including tritanopia, which the widely used
#: reference validators report but do not gate on (see tests/unit/test_figure_theme.py).
#: A fifth slot is reachable only by waiving tritan, and nothing in the catalogue needs
#: one: the widest genuine case is three baselines. Beyond the cap, fold the remainder
#: into "other" or facet into small multiples.
CATEGORICAL_SLOTS: Final = 4

_HEX = re.compile(r"#[0-9a-f]{6}")
_THEMES = files("alpha_research.figures") / "themes"


@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    """Resolved figure colours and type. Every field is a lowercase ``#rrggbb`` hex."""

    theme_id: str
    bg: str
    panel: str
    line: str
    grid: str
    ink: str
    ink_dim: str
    muted: str
    faint: str
    accent: str
    up: str
    down: str
    gold: str
    substrate: str
    categorical: tuple[str, ...]
    font_family: str
    font_mono: str
    base_font_pt: float

    def __post_init__(self) -> None:
        for field in fields(self):
            if field.name in {"theme_id", "font_family", "font_mono", "base_font_pt"}:
                continue
            value = getattr(self, field.name)
            colours = value if isinstance(value, tuple) else (value,)
            for colour in colours:
                if not isinstance(colour, str) or _HEX.fullmatch(colour) is None:
                    raise DataError(f"Theme.{field.name} must be lowercase #rrggbb, got {colour!r}")
        if len(self.categorical) != CATEGORICAL_SLOTS:
            raise DataError(
                f"Theme.categorical must hold exactly {CATEGORICAL_SLOTS} verified slots, "
                f"got {len(self.categorical)}"
            )
        if len(set(self.categorical)) != len(self.categorical):
            raise DataError("Theme.categorical must not repeat a colour")
        if self.base_font_pt <= 0:
            raise DataError("Theme.base_font_pt must be positive")

    def digest(self) -> str:
        """Content address of the resolved theme; part of every figure cache key."""
        return canonical_sha256(theme_document(self))

    def series_colour(self, index: int) -> str:
        """Colour for categorical slot ``index``.

        Fails loud rather than cycling: a recycled hue silently claims two unrelated
        series are the same thing. Callers past the cap must aggregate or facet.
        """
        if index < 0 or index >= CATEGORICAL_SLOTS:
            raise DataError(
                f"categorical slot {index} is outside the verified palette "
                f"(0..{CATEGORICAL_SLOTS - 1}); aggregate the tail into 'other' or facet"
            )
        return self.categorical[index]


def theme_document(theme: Theme) -> dict[str, object]:
    """The theme as a plain JSON-compatible mapping, matching the committed file."""
    return {
        "accent": theme.accent,
        "base_font_pt": theme.base_font_pt,
        "bg": theme.bg,
        "categorical": list(theme.categorical),
        "down": theme.down,
        "faint": theme.faint,
        "font_family": theme.font_family,
        "font_mono": theme.font_mono,
        "gold": theme.gold,
        "grid": theme.grid,
        "ink": theme.ink,
        "ink_dim": theme.ink_dim,
        "line": theme.line,
        "muted": theme.muted,
        "panel": theme.panel,
        "substrate": theme.substrate,
        "theme_id": theme.theme_id,
        "up": theme.up,
    }


@lru_cache(maxsize=4)
def load_theme(theme_id: str = "alpha-dark") -> Theme:
    """Load a committed theme document by id."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", theme_id):
        raise DataError(f"unsupported theme id {theme_id!r}")
    resource = _THEMES / f"{theme_id.replace('-', '_')}.json"
    if not resource.is_file():
        raise DataError(f"no committed theme document for {theme_id!r}")
    document = json.loads(resource.read_text("utf-8"))
    if document.get("theme_id") != theme_id:
        raise DataError(
            f"theme document declares {document.get('theme_id')!r}, expected {theme_id!r}"
        )
    return Theme(
        theme_id=document["theme_id"],
        bg=document["bg"],
        panel=document["panel"],
        line=document["line"],
        grid=document["grid"],
        ink=document["ink"],
        ink_dim=document["ink_dim"],
        muted=document["muted"],
        faint=document["faint"],
        accent=document["accent"],
        up=document["up"],
        down=document["down"],
        gold=document["gold"],
        substrate=document["substrate"],
        categorical=tuple(document["categorical"]),
        font_family=document["font_family"],
        font_mono=document["font_mono"],
        base_font_pt=float(document["base_font_pt"]),
    )
