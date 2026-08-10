"""Figure catalogue, metadata and image bytes for a stored run."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Response

from alpha_core import DataError
from alpha_web._figures import (
    FigureError,
    FigureNotFound,
    catalogue,
    figure,
    metadata,
)
from alpha_web.api._common import data_dir
from alpha_web.api.models import FigureCatalogue, FigureMetadata

router = APIRouter(prefix="/api/runs", tags=["figures"])

_Format = Annotated[Literal["svg", "png"], Query(description="Image format.")]


def _fail(error: Exception) -> HTTPException:
    if isinstance(error, FigureNotFound):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, DataError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, TimeoutError):
        return HTTPException(status_code=504, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.get("/{run_id}/figures", response_model=FigureCatalogue)
def list_figures(run_id: str) -> FigureCatalogue:
    """Every figure applicable to this run, with a specific reason for any that cannot draw."""
    try:
        return FigureCatalogue.model_validate(catalogue(run_id, data_dir=data_dir()))
    except (FigureError, DataError, RuntimeError) as error:
        raise _fail(error) from error


@router.get("/{run_id}/figures/{figure_id}", response_model=FigureMetadata)
def figure_metadata(run_id: str, figure_id: str, fmt: _Format = "svg") -> FigureMetadata:
    """A figure's text, legend and provenance -- everything except its bytes.

    The page needs alt text and the teaching strings before the image arrives, and needs
    them at all for a screen reader, since the SVG's text is embedded as glyph outlines.
    """
    try:
        document = metadata(run_id, figure_id, fmt=fmt, data_dir=data_dir())
        return FigureMetadata.model_validate(document)
    except (FigureError, DataError, RuntimeError) as error:
        raise _fail(error) from error


@router.get("/{run_id}/figures/{figure_id}/image")
def figure_image(
    run_id: str,
    figure_id: str,
    fmt: _Format = "svg",
    key: Annotated[str | None, Query(description="Expected cache key.")] = None,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> Response:
    """The rendered image.

    The cache key is a content hash over the run's artifact digests plus renderer
    identity, so it doubles as a strong ETag: if the bytes could differ, the key differs.
    A caller that pins ``?key=`` gets an immutable response; one that does not must
    revalidate. A pinned key that no longer matches returns 409 with the current key, so a
    stale page refetches instead of silently receiving different content at one URL.
    """
    try:
        rendered = figure(run_id, figure_id, fmt=fmt, data_dir=data_dir())
    except (FigureError, DataError, RuntimeError) as error:
        raise _fail(error) from error

    etag = f'"{rendered.cache_key}"'
    if key is not None and key != rendered.cache_key:
        raise HTTPException(
            status_code=409,
            detail=f"figure has been re-rendered; current key is {rendered.cache_key}",
        )
    if if_none_match is not None and if_none_match.strip() in {etag, rendered.cache_key}:
        return Response(status_code=304, headers={"ETag": etag})

    cache_control = (
        "private, max-age=31536000, immutable"
        if key is not None
        else "private, max-age=0, must-revalidate"
    )
    return Response(
        content=rendered.payload,
        media_type=rendered.media_type,
        headers={"ETag": etag, "Cache-Control": cache_control},
    )
