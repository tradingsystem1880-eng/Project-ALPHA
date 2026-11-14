"""Figure catalogue and metadata."""

from __future__ import annotations

from ._base import StrictModel


class FigureCatalogueItem(StrictModel):
    """One catalogue entry as it applies to a specific run."""

    figure_id: str
    title: str
    summary: str
    section: str
    panel_count: int
    available: bool
    unavailable_reason: str | None


class FigureCatalogue(StrictModel):
    run_id: str
    kind: str | None
    renderer_version: int
    items: list[FigureCatalogueItem]


class FigurePanelMeta(StrictModel):
    panel_id: str
    y_label: str
    y_unit: str
    note: str | None
    legend: list[str]


class FigureMetadata(StrictModel):
    """A figure's text and structure, served without its bytes.

    ``alt_text`` and the four teaching strings are the accessibility path for figures
    whose SVG text is embedded as glyph outlines and therefore invisible to a screen
    reader; the page renders them as real HTML beside the image.
    """

    figure_id: str
    title: str
    subtitle: str
    caption: str
    alt_text: str
    x_label: str
    question: str
    plain_language_answer: str
    uncertainty: str
    caveat: str
    truncation_note: str | None
    source_artifacts: list[str]
    panels: list[FigurePanelMeta]
    renderer_version: int
    cache_key: str
    format: str
    width_in: float
    height_in: float
    image_url: str
    etag: str
