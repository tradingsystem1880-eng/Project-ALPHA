"""Serving rendered figures without letting matplotlib into the web process.

The web layer does three things here: work out where a figure *would* live, read the
bytes if they are already there, and otherwise ask the CLI -- out of process -- to render
them. Same subprocess-plus-cache shape ``_candles`` uses, and it is what keeps "the web
never executes the engine" true for figures.

Computing the cache key needs the renderer's identity (its version, matplotlib's version,
the theme digest) and each figure's canvas size. The web is forbidden from importing
``alpha_research``, so rather than reaching for it, that *key environment* is published by
``alpha figures list --json`` and cached here for the process lifetime. A cache hit then
costs a stat rather than a process spawn -- which matters, because otherwise serving a
cached figure would be no cheaper than rendering one.

Concurrent requests for the same missing figure collapse into a single render. Without
that, opening a results page fires a dozen parallel CLI processes for one run and each
pays the full matplotlib import.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpha_cli.figure_cache import (
    CacheKeyInputs,
    figure_paths,
    input_digest,
    is_cached,
    validate_figure_id,
    validate_format,
    validate_run_id,
)
from alpha_cli.run_store import find_run_dir, read_manifest
from alpha_web._catalog import _run_json

#: A pack render of ~20 figures is the worst realistic case; well past it, but finite, so a
#: wedged child surfaces as a timeout instead of pinning a request thread forever.
RENDER_TIMEOUT_SECONDS = 180.0

_MEDIA_TYPES = {"svg": "image/svg+xml", "png": "image/png"}

_LOCK = threading.Lock()
_IN_FLIGHT: dict[str, threading.Event] = {}
_ENVIRONMENT: dict[str, Any] | None = None
_ENVIRONMENT_LOCK = threading.Lock()


class FigureError(RuntimeError):
    """A figure could not be produced; the router maps this to 4xx/5xx."""


class FigureNotFound(FigureError):
    """The run or the figure does not exist."""


@dataclass(frozen=True, slots=True)
class RenderedFigure:
    figure_id: str
    cache_key: str
    fmt: str
    media_type: str
    payload: bytes
    sidecar: dict[str, Any]


def media_type(fmt: str) -> str:
    return _MEDIA_TYPES[validate_format(fmt)]


def reset_environment_cache() -> None:
    """Drop the cached key environment (tests, and after a deliberate renderer change)."""
    global _ENVIRONMENT
    with _ENVIRONMENT_LOCK:
        _ENVIRONMENT = None


def key_environment(*, data_dir: Path) -> dict[str, Any]:
    """Renderer identity plus per-figure canvas geometry, cached per process.

    Static for the lifetime of the process: it describes the installed code, not the store.
    """
    global _ENVIRONMENT
    with _ENVIRONMENT_LOCK:
        if _ENVIRONMENT is not None:
            return _ENVIRONMENT
    payload = _run_json(["figures", "list", "--json"], data_dir=data_dir)
    if not isinstance(payload, dict) or not isinstance(payload.get("figures"), list):
        raise FigureError("invalid figure catalogue projection")
    with _ENVIRONMENT_LOCK:
        _ENVIRONMENT = payload
    return payload


def _definition(environment: dict[str, Any], figure_id: str) -> dict[str, Any]:
    for item in environment["figures"]:
        if item.get("figure_id") == figure_id:
            return dict(item)
    raise FigureNotFound(f"unknown figure {figure_id!r}")


def _resolve(run_id: str, data_dir: Path) -> tuple[Path, dict[str, Any]]:
    validate_run_id(run_id)
    rdir = find_run_dir(data_dir, run_id)
    if rdir is None:
        raise FigureNotFound(f"unknown run {run_id!r}")
    return rdir, read_manifest(rdir)


def catalogue(run_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Which figures apply to this run, and which of them can actually be drawn."""
    _resolve(run_id, data_dir)
    payload = _run_json(["figures", "list", "--run", run_id, "--json"], data_dir=data_dir)
    if not isinstance(payload, dict):
        raise FigureError("invalid figure catalogue projection")
    payload["renderer_version"] = key_environment(data_dir=data_dir)["renderer_version"]
    return payload


def _cache_entry(run_id: str, figure_id: str, fmt: str, data_dir: Path) -> tuple[Path, Path, str]:
    environment = key_environment(data_dir=data_dir)
    definition = _definition(environment, figure_id)
    rdir, manifest = _resolve(run_id, data_dir)
    artifacts = tuple(definition["required_artifacts"]) + tuple(
        definition.get("optional_artifacts") or ()
    )
    digest, kind = input_digest(manifest, rdir, artifacts)
    key = CacheKeyInputs(
        run_id=run_id,
        figure_id=figure_id,
        renderer_version=int(environment["renderer_version"]),
        matplotlib_version=str(environment["matplotlib_version"]),
        theme_id=str(environment["theme_id"]),
        theme_digest=str(environment["theme_digest"]),
        width_in=float(definition["width_in"]),
        height_in=float(definition["height_in"]),
        dpi=int(definition["dpi"]),
        fmt=validate_format(fmt),
        background="theme",
        artifact_contract_version=manifest.get("artifact_contract_version"),
        input_digest=digest,
        input_digest_kind=kind,
    ).key()
    image, sidecar = figure_paths(data_dir, run_id, figure_id, key, fmt)
    return image, sidecar, key


def _render(run_id: str, figure_id: str, fmt: str, data_dir: Path) -> None:
    _run_json(
        ["figures", "render", run_id, "--figure", figure_id, "--format", fmt, "--json"],
        data_dir=data_dir,
        timeout_seconds=RENDER_TIMEOUT_SECONDS,
    )


def _single_flight(token: str, work: Any) -> None:
    """Run ``work`` once per token; concurrent callers wait for the first to finish."""
    with _LOCK:
        pending = _IN_FLIGHT.get(token)
        leader = pending is None
        if leader:
            pending = threading.Event()
            _IN_FLIGHT[token] = pending
    assert pending is not None
    if not leader:
        if not pending.wait(timeout=RENDER_TIMEOUT_SECONDS):
            raise FigureError(f"timed out waiting for an in-flight render of {token}")
        return
    try:
        work()
    finally:
        with _LOCK:
            _IN_FLIGHT.pop(token, None)
        pending.set()


def figure(run_id: str, figure_id: str, *, fmt: str, data_dir: Path) -> RenderedFigure:
    """Fetch a figure, rendering it out of process only when the cache misses."""
    validate_run_id(run_id)
    validate_figure_id(figure_id)
    fmt = validate_format(fmt)

    image, sidecar, key = _cache_entry(run_id, figure_id, fmt, data_dir)
    if not is_cached(image, sidecar):
        token = f"{run_id}:{figure_id}:{fmt}"
        _single_flight(token, lambda: _render(run_id, figure_id, fmt, data_dir))
        image, sidecar, key = _cache_entry(run_id, figure_id, fmt, data_dir)
    if not is_cached(image, sidecar):
        raise FigureError(f"{figure_id} could not be rendered for run {run_id}")

    return RenderedFigure(
        figure_id=figure_id,
        cache_key=key,
        fmt=fmt,
        media_type=_MEDIA_TYPES[fmt],
        payload=image.read_bytes(),
        sidecar=json.loads(sidecar.read_text("utf-8")),
    )


def metadata(run_id: str, figure_id: str, *, fmt: str, data_dir: Path) -> dict[str, Any]:
    """A figure's text without its bytes.

    Separate from the image because the page needs alt text, caption and the teaching
    strings before -- or entirely without -- downloading a picture. That is also the
    accessibility mitigation for glyph-outlined SVG text, which no screen reader can read.
    """
    rendered = figure(run_id, figure_id, fmt=fmt, data_dir=data_dir)
    document = dict(rendered.sidecar)
    document["cache_key"] = rendered.cache_key
    document["image_url"] = (
        f"/api/runs/{run_id}/figures/{figure_id}/image?fmt={fmt}&key={rendered.cache_key}"
    )
    document["etag"] = rendered.cache_key
    return document
