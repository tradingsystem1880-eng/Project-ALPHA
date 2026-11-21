"""One entry point for both variants of a figure: plain or annotated, svg or png.

``explanation`` is the long text the Workstation shows beside a figure. It is built from
four fixed sentences per figure (``explanations_*``) plus sentences about this run, read
from the stored data by ``spec_facts``. The annotated image carries the same sentences in
its "How to read this chart" box.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from alpha_cli.figure_cache import validate_variant
from alpha_cli.figures import explanations_checks, explanations_models, explanations_runs
from alpha_cli.figures.plain_spec import draw_spec
from alpha_cli.figures.plain_style import to_bytes
from alpha_cli.figures.spec_facts import run_sentences
from alpha_core import DataError

if TYPE_CHECKING:
    from alpha_research.figures.spec import FigureSpec

_FIXED: Final = {
    **explanations_runs.TEXTS,
    **explanations_checks.TEXTS,
    **explanations_models.TEXTS,
}
_RUN_SENTENCES: Final = 3


def fixed_text(figure_id: str) -> tuple[str, str, str, str]:
    """The four fixed sentences; a figure with none is a defect, not a blank box."""
    text = _FIXED.get(figure_id)
    if text is None:
        raise DataError(f"no explanation written for figure {figure_id!r}")
    return (text[0], text[1], text[2], text[3])


def explanation(spec: FigureSpec, fixed: tuple[str, str, str, str] | None = None) -> list[str]:
    """Four to seven sentences: axes, marks, what to look for, this run, what it cannot tell."""
    axes, marks, look, limits = fixed or fixed_text(spec.figure_id)
    return [axes, marks, look, *run_sentences(spec)[:_RUN_SENTENCES], limits]


def render_variant(
    spec: FigureSpec,
    variant: str,
    fmt: str,
    fixed: tuple[str, str, str, str] | None = None,
) -> bytes:
    """Render ``spec`` as the plain notebook chart or the annotated, explained chart."""
    validate_variant(variant)
    return to_bytes(draw_spec(spec, variant, explanation(spec, fixed)), fmt)
