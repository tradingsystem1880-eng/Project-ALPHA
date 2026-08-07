"""The figure cache key, and the boundary that keeps figures out of run directories."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from alpha_cli.figure_cache import (
    CacheKeyInputs,
    cache_root,
    figure_paths,
    input_digest,
    is_cached,
    validate_figure_id,
    validate_format,
    validate_run_id,
)
from alpha_core import DataError


def _inputs(**overrides: object) -> CacheKeyInputs:
    base: dict[str, object] = {
        "run_id": "0123456789abcdef",
        "figure_id": "equity_underwater",
        "renderer_version": 1,
        "matplotlib_version": "3.11.0",
        "theme_id": "alpha-dark",
        "theme_digest": "a" * 64,
        "width_in": 11.0,
        "height_in": 5.0,
        "dpi": 144,
        "fmt": "svg",
        "background": "theme",
        "artifact_contract_version": 3,
        "input_digest": "b" * 64,
        "input_digest_kind": "artifact_sha256",
    }
    return CacheKeyInputs(**{**base, **overrides})  # type: ignore[arg-type]


class TestCacheKey:
    def test_the_key_is_stable_for_identical_inputs(self) -> None:
        assert _inputs().key() == _inputs().key()

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("run_id", "fedcba9876543210"),
            ("figure_id", "rolling_risk"),
            ("renderer_version", 2),
            ("matplotlib_version", "3.12.0"),
            ("theme_id", "alpha-light"),
            ("theme_digest", "c" * 64),
            ("width_in", 12.0),
            ("height_in", 6.0),
            ("dpi", 200),
            ("fmt", "png"),
            ("background", "transparent"),
            ("artifact_contract_version", 2),
            ("input_digest", "d" * 64),
            ("input_digest_kind", "mtime_fallback"),
        ],
    )
    def test_every_component_changes_the_key(self, field: str, value: object) -> None:
        """If a component could change the bytes, it must change the key -- and if it
        cannot, it has no business being in the key at all."""
        assert _inputs().key() != replace(_inputs(), **{field: value}).key()  # type: ignore[arg-type]

    def test_the_key_document_is_canonical_json(self) -> None:
        document = _inputs().document()
        assert json.loads(json.dumps(document, sort_keys=True)) == document

    def test_a_renderer_bump_invalidates_rather_than_mixes(self) -> None:
        """Old entries become unreachable instead of being served beside new ones."""
        assert _inputs(renderer_version=1).key() != _inputs(renderer_version=2).key()


class TestPaths:
    def test_the_key_lives_in_the_filename_so_variants_coexist(self, tmp_path: Path) -> None:
        svg, sidecar = figure_paths(
            tmp_path, "0123456789abcdef", "equity_underwater", "a" * 16, "svg"
        )
        png, _ = figure_paths(tmp_path, "0123456789abcdef", "equity_underwater", "b" * 16, "png")
        assert svg != png
        assert svg.parent == png.parent == sidecar.parent

    def test_figures_live_outside_every_run_directory(self, tmp_path: Path) -> None:
        image, _ = figure_paths(tmp_path, "0123456789abcdef", "rolling_risk", "a" * 16, "svg")
        assert cache_root(tmp_path) in image.parents
        assert "runs" not in image.parts

    @pytest.mark.parametrize("bad", ["../escape", "Equity", "a b", "", "trailing_"])
    def test_a_malformed_figure_id_is_refused(self, bad: str) -> None:
        with pytest.raises(DataError, match="invalid figure id"):
            validate_figure_id(bad)

    @pytest.mark.parametrize("bad", ["../../etc/passwd", "ABCDEF0123456789", "short"])
    def test_a_malformed_run_id_is_refused(self, bad: str) -> None:
        with pytest.raises(DataError, match="invalid run id"):
            validate_run_id(bad)

    def test_an_unsupported_format_is_refused(self) -> None:
        with pytest.raises(DataError, match="unsupported figure format"):
            validate_format("pdf")

    def test_a_forged_cache_key_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(DataError, match="invalid cache key"):
            figure_paths(tmp_path, "0123456789abcdef", "rolling_risk", "../../x", "svg")


class TestCompletion:
    def test_an_image_without_its_sidecar_does_not_count_as_cached(self, tmp_path: Path) -> None:
        """The sidecar is written last, so a crash mid-render leaves an unreferenced image
        rather than a listed figure with truncated bytes."""
        image, sidecar = figure_paths(tmp_path, "0123456789abcdef", "qq_normal", "a" * 16, "svg")
        image.parent.mkdir(parents=True)
        image.write_bytes(b"<svg/>")
        assert not is_cached(image, sidecar)
        sidecar.write_text("{}")
        assert is_cached(image, sidecar)


class TestInputDigest:
    def test_a_v3_manifest_digests_declared_artifact_hashes_without_rehashing(
        self, tmp_path: Path
    ) -> None:
        manifest = {"artifacts": {"equity_curve.parquet": {"sha256": "e" * 64}}}
        digest, kind = input_digest(manifest, tmp_path, ("equity_curve.parquet",))
        assert kind == "artifact_sha256"
        assert len(digest) == 64

    def test_a_changed_artifact_hash_changes_the_digest(self, tmp_path: Path) -> None:
        first, _ = input_digest(
            {"artifacts": {"equity_curve.parquet": {"sha256": "e" * 64}}},
            tmp_path,
            ("equity_curve.parquet",),
        )
        second, _ = input_digest(
            {"artifacts": {"equity_curve.parquet": {"sha256": "f" * 64}}},
            tmp_path,
            ("equity_curve.parquet",),
        )
        assert first != second

    def test_a_legacy_run_falls_back_to_size_and_mtime_and_says_so(self, tmp_path: Path) -> None:
        artifact = tmp_path / "equity_curve.parquet"
        artifact.write_bytes(b"legacy")
        digest, kind = input_digest({}, tmp_path, ("equity_curve.parquet",))
        assert kind == "mtime_fallback"
        assert len(digest) == 64

    def test_the_two_digest_regimes_can_never_collide_in_one_key(self, tmp_path: Path) -> None:
        """Tagging the kind is what stops a legacy mtime digest from being mistaken for a
        content hash and silently serving a stale image."""
        assert (
            _inputs(input_digest_kind="artifact_sha256").key()
            != _inputs(input_digest_kind="mtime_fallback").key()
        )


def test_the_two_cache_versions_never_drift_apart() -> None:
    """The constant is stated twice on purpose, so this test is what keeps it one value.

    ``alpha_cli.figure_cache`` cannot import it from ``alpha_research.figures``: doing so
    would execute that package and pull matplotlib into the web process, which the import
    guard below forbids. Bumping one copy and not the other would leave the renderer
    producing new output under a key that says nothing changed -- every reader would serve
    a stale cached figure forever. This mirrors the ``bands.ts``/``verdict.py`` guard.
    """
    from alpha_cli.figure_cache import FIGURES_CACHE_VERSION as cache_side
    from alpha_research.figures import FIGURES_CACHE_VERSION as renderer_side

    assert cache_side == renderer_side


def test_the_cache_seam_stays_free_of_heavy_imports() -> None:
    """The web process imports this module on every figure request.

    Pulling in Polars, numpy, matplotlib or the renderer here would put the whole
    numerical stack into a process the architecture says must never hold it.
    """
    import subprocess

    script = (
        "import sys; import alpha_cli.figure_cache; "
        "heavy = {'matplotlib', 'numpy', 'polars', 'alpha_research.figures'} & set(sys.modules); "
        "print(sorted(heavy))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
