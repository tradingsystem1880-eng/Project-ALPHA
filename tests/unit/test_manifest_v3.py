"""Manifest-v3 artifact contracts and immutable publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl
import pytest

from alpha_cli import _artifacts
from alpha_core import DataError


def _identity() -> dict[str, object]:
    return {
        "run_identity_version": 3,
        "execution_fingerprint": "a" * 64,
        "strategy_fingerprint": "b" * 64,
        "source_fingerprint": "c" * 64,
    }


def _write_equity(path: Path, values: list[float]) -> None:
    frame = pl.DataFrame({"step": list(range(len(values))), "equity": values})
    _artifacts.publish_artifact(path, frame.write_parquet)


def test_v3_manifest_pins_schema_hash_size_and_rows(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    artifact = rdir / "equity_curve.parquet"
    _write_equity(artifact, [1.0, 1.1, 1.2])

    _artifacts.write_manifest(
        rdir,
        {
            "run_id": rdir.name,
            "command": "test_fixture",
            **_identity(),
        },
    )

    manifest = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert manifest["run_identity_version"] == 3
    assert manifest["artifact_contract_version"] == 3
    assert set(manifest["artifacts"]) == {"equity_curve.parquet"}
    entry = manifest["artifacts"]["equity_curve.parquet"]
    assert entry["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert entry["size_bytes"] == artifact.stat().st_size
    assert entry["rows"] == 3
    assert entry["schema"] == [
        {"name": "step", "dtype": "Int64"},
        {"name": "equity", "dtype": "Float64"},
    ]
    assert _artifacts.read_manifest(rdir) == manifest


def test_v3_reader_detects_artifact_tampering(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    artifact = rdir / "equity_curve.parquet"
    _write_equity(artifact, [1.0, 1.1])
    _artifacts.write_manifest(
        rdir,
        {"run_id": rdir.name, "command": "test_fixture", **_identity()},
    )
    artifact.write_bytes(artifact.read_bytes() + b"tampered")

    with pytest.raises(DataError, match="artifact .* (hash|size) mismatch"):
        _artifacts.read_manifest(rdir)


def test_published_artifact_is_idempotent_but_never_replaced(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    artifact = rdir / "equity_curve.parquet"
    _write_equity(artifact, [1.0, 1.1])
    _artifacts.write_manifest(
        rdir,
        {"run_id": rdir.name, "command": "test_fixture", **_identity()},
    )
    original_artifact = artifact.read_bytes()
    original_manifest = (rdir / "manifest.json").read_bytes()

    _write_equity(artifact, [1.0, 1.1])
    _artifacts.write_manifest(
        rdir,
        {"run_id": rdir.name, "command": "test_fixture", **_identity()},
    )
    assert artifact.read_bytes() == original_artifact
    assert (rdir / "manifest.json").read_bytes() == original_manifest

    with pytest.raises(DataError, match="immutable artifact"):
        _write_equity(artifact, [1.0, 9.9])
    assert artifact.read_bytes() == original_artifact


@pytest.mark.parametrize("schema_version", [1, 2])
def test_v1_v2_manifests_remain_readable(tmp_path: Path, schema_version: int) -> None:
    rdir = tmp_path / "runs" / f"{schema_version:016x}"
    rdir.mkdir(parents=True)
    legacy = {"schema_version": schema_version, "run_id": rdir.name, "command": "legacy"}
    (rdir / "manifest.json").write_text(json.dumps(legacy), encoding="utf-8")
    assert _artifacts.read_manifest(rdir) == legacy


def test_v3_manifest_requires_identity_fields(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    with pytest.raises(DataError, match="run_identity_version"):
        _artifacts.write_manifest(rdir, {"run_id": rdir.name, "command": "test_fixture"})
