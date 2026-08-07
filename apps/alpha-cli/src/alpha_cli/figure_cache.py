"""Content-addressed paths for rendered figures, outside any run directory.

This module is a deliberately thin public seam. The web process imports it to work out
where a figure *would* live and whether it is already there, and must be able to do that
without pulling in Polars, numpy, matplotlib, or the figure renderer -- so nothing heavy
may be imported here, and a test enforces that.

Figures are a **derived cache**, never run artifacts. Writing them into a run directory
would break the immutable v3 artifact contract (whose manifest declares an exact file
set) and would leave every historical run permanently figure-less. Keeping them at
``data_dir/figures/<run_id>/`` costs nothing and means a v1 run from months ago renders
just as well as one produced today.

The key is a hash over the run's own artifact digests plus renderer identity, so it is a
strong ETag by construction: if the bytes could differ, the key differs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from alpha_core import DataError

#: Cache layout version. Bump when the path shape or key composition changes -- not for
#: visual changes, which belong to the renderer version.
#:
#: Deliberately restated rather than imported from ``alpha_research.figures.version``:
#: importing it would execute that package and pull matplotlib into the web process. The
#: two copies are held equal by ``test_the_two_cache_versions_never_drift_apart``, so bump
#: both together.
FIGURES_CACHE_VERSION: Final = 1

FIGURE_ROOT: Final = "figures"
FIGURE_ID_RE: Final = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")
_RUN_ID_RE: Final = re.compile(r"[0-9a-f]{16}")
_KEY_RE: Final = re.compile(r"[0-9a-f]{16}")

FigureFormat = Literal["svg", "png"]
_FORMATS: Final = ("svg", "png")


@dataclass(frozen=True, slots=True, kw_only=True)
class CacheKeyInputs:
    """Everything that can change a figure's bytes, and nothing that cannot."""

    run_id: str
    figure_id: str
    renderer_version: int
    matplotlib_version: str
    theme_id: str
    theme_digest: str
    width_in: float
    height_in: float
    dpi: int
    fmt: FigureFormat
    background: str
    artifact_contract_version: int | None
    input_digest: str
    input_digest_kind: Literal["artifact_sha256", "mtime_fallback"]

    def document(self) -> dict[str, Any]:
        return {
            "artifact_contract_version": self.artifact_contract_version,
            "background": self.background,
            "dpi": self.dpi,
            "figure_id": self.figure_id,
            "figures_cache_version": FIGURES_CACHE_VERSION,
            "format": self.fmt,
            "height_in": self.height_in,
            "input_digest": self.input_digest,
            "input_digest_kind": self.input_digest_kind,
            "matplotlib_version": self.matplotlib_version,
            "renderer_version": self.renderer_version,
            "run_id": self.run_id,
            "theme_digest": self.theme_digest,
            "theme_id": self.theme_id,
            "width_in": self.width_in,
        }

    def key(self) -> str:
        payload = json.dumps(
            self.document(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]


def validate_figure_id(figure_id: str) -> str:
    if FIGURE_ID_RE.fullmatch(figure_id) is None:
        raise DataError(f"invalid figure id {figure_id!r}; expected lower_snake_case")
    return figure_id


def validate_run_id(run_id: str) -> str:
    if _RUN_ID_RE.fullmatch(run_id) is None:
        raise DataError(f"invalid run id {run_id!r}; expected 16 lowercase hex characters")
    return run_id


def validate_format(fmt: str) -> FigureFormat:
    if fmt not in _FORMATS:
        raise DataError(f"unsupported figure format {fmt!r}; expected one of {_FORMATS}")
    return fmt  # type: ignore[return-value]


def cache_root(data_dir: Path) -> Path:
    return data_dir / FIGURE_ROOT


def figure_paths(
    data_dir: Path, run_id: str, figure_id: str, key: str, fmt: str
) -> tuple[Path, Path]:
    """Image and sidecar paths for one cache entry.

    The key lives in the filename rather than an index: variants coexist, a stale entry is
    self-evidently stale, and readers never contend on a shared file.
    """
    validate_run_id(run_id)
    validate_figure_id(figure_id)
    validate_format(fmt)
    if _KEY_RE.fullmatch(key) is None:
        raise DataError(f"invalid cache key {key!r}")
    directory = cache_root(data_dir) / run_id
    stem = f"{figure_id}.{key}"
    image = directory / f"{stem}.{fmt}"
    sidecar = directory / f"{stem}.json"
    _assert_contained(image, data_dir)
    _assert_contained(sidecar, data_dir)
    return image, sidecar


def _assert_contained(path: Path, data_dir: Path) -> None:
    root = cache_root(data_dir).resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise DataError(f"refusing to address {path} outside the figure cache")


def input_digest(
    manifest: dict[str, Any], rdir: Path, artifacts: tuple[str, ...]
) -> tuple[str, Literal["artifact_sha256", "mtime_fallback"]]:
    """Digest of the inputs a figure reads.

    For a v3 run this is nearly free: the manifest already records a sha256 per declared
    artifact, so nothing is re-hashed. Legacy runs have no such block and fall back to
    (size, mtime), tagged so the two regimes can never collide in one key.
    """
    declared = manifest.get("artifacts")
    if isinstance(declared, dict):
        pairs = []
        for name in sorted(artifacts):
            entry = declared.get(name)
            if isinstance(entry, dict) and isinstance(entry.get("sha256"), str):
                pairs.append((name, entry["sha256"]))
        if pairs:
            payload = json.dumps(pairs, separators=(",", ":")).encode("utf-8")
            return hashlib.sha256(payload).hexdigest(), "artifact_sha256"
    stats = []
    for name in sorted(artifacts):
        path = rdir / name
        if path.is_file() and not path.is_symlink():
            info = path.stat()
            stats.append((name, info.st_size, info.st_mtime_ns))
    payload = json.dumps(stats, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), "mtime_fallback"


def is_cached(image: Path, sidecar: Path) -> bool:
    """A figure counts as cached only once its sidecar lands.

    The sidecar is written last, mirroring the manifest-last discipline the run store
    uses: a crash mid-render leaves an unreferenced image rather than a listed figure
    with truncated bytes.
    """
    return sidecar.is_file() and image.is_file()
