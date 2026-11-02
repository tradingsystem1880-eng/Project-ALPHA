"""Inert metadata fixtures only: no panels, fitted models or authoritative stores."""

from __future__ import annotations

import dataclasses
import hashlib
import os
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

import pytest

from alpha_cli.ml_contract import MLContractError
from alpha_cli.ml_native_plan import (
    W09ProtocolV1,
    build_manifest,
    fingerprint_worker,
    readiness,
    validate_manifest,
)
from alpha_cli.ml_refit import _file_snapshot


def _worker(root: Path) -> Path:
    package = root / "src/alpha_qlib_worker"
    for name in (
        "__init__.py",
        "__main__.py",
        "real.py",
        "contract.py",
        "features.py",
        "rank_ensemble.py",
        "schemas/request.schema.json",
        "schemas/request-v2.schema.json",
        "schemas/result.schema.json",
        "schemas/result-v2.schema.json",
        "schemas/panel.parquet.schema.json",
        "schemas/predictions.parquet.schema.json",
        "schemas/ensemble-diagnostics.parquet.schema.json",
    ):
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic source metadata only\n")
    (root / "pyproject.toml").write_text("synthetic project\n")
    (root / "uv.lock").write_text("synthetic lock\n")
    return root


def _protocol(worker: Path, schema: int = 2) -> W09ProtocolV1:
    return W09ProtocolV1(
        project_id="00000000-0000-4000-8000-000000000001",
        experiment_id="00000000-0000-4000-8000-000000000002",
        contract_id="rc_" + "a" * 64,
        request_schema_version=schema,
        recipe="lightgbm" if schema == 1 else "rank_ensemble_v1",
        request_sha256="b" * 64,
        panel_sha256="c" * 64,
        snapshot_sha256="d" * 64,
        dependency_sha256=fingerprint_worker(worker).sha256,
        folds=(0, 1),
    )


@pytest.mark.parametrize("schema,learned,assembly", [(1, 4, 0), (2, 6, 2)])
def test_recipe_graph_separates_learning_from_fixed_assembly(
    tmp_path: Path, schema: int, learned: int, assembly: int
) -> None:
    protocol = _protocol(_worker(tmp_path), schema)
    manifest = build_manifest(protocol)
    validate_manifest(manifest)
    assert sum(node.operation == "fit" for node in manifest.components) == learned
    assert sum(node.operation == "assemble" for node in manifest.components) == assembly
    assert sum(node.operation == "transform" for node in manifest.components) == 4
    nodes = {node.name: node for node in manifest.components if node.fold == 0}
    if schema == 2:
        assert nodes["label.validation"].component_id not in nodes["ridge"].parents
        assert nodes["rank_ensemble"].parents == (
            nodes["lightgbm"].component_id,
            nodes["ridge"].component_id,
        )


def test_rename_preserves_identity_but_changed_request_or_record_does_not(tmp_path: Path) -> None:
    worker = _worker(tmp_path / "first")
    first = _protocol(worker)
    worker.rename(tmp_path / "renamed")
    second = _protocol(tmp_path / "renamed")
    assert first == second
    assert build_manifest(first).manifest_id == build_manifest(second).manifest_id
    for changed in (
        dataclasses.replace(first, request_sha256="e" * 64),
        dataclasses.replace(first, panel_sha256="e" * 64),
        dataclasses.replace(first, experiment_id="00000000-0000-4000-8000-000000000003"),
    ):
        assert changed.protocol_id != first.protocol_id
        assert (
            build_manifest(changed).components[0].component_id
            != build_manifest(first).components[0].component_id
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"request_schema_version": True},
        {"request_schema_version": 3},
        {"recipe": "double_ensemble"},
        {"recipe": "lightgbm"},
        {"recipe": []},
        {"folds": ()},
        {"folds": (0, 2)},
        {"folds": (False, 1)},
        {"folds": tuple(range(65))},
        {"request_sha256": "not-a-hash"},
        {"contract_id": "unbound"},
        {"project_id": "not-a-record-id"},
    ],
)
def test_unsupported_protocol_metadata_is_rejected(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    protocol = _protocol(_worker(tmp_path))
    raw = dataclasses.asdict(protocol)
    raw.update(changes)
    with pytest.raises(MLContractError):
        W09ProtocolV1(**raw)


@pytest.mark.parametrize(
    "corruption",
    [
        "missing",
        "duplicate",
        "cycle",
        "assembly_fit",
        "cross_fold",
        "boolean_fold",
        "unknown_operation",
    ],
)
def test_only_the_exact_recipe_dag_is_accepted(tmp_path: Path, corruption: str) -> None:
    manifest = build_manifest(_protocol(_worker(tmp_path)))
    nodes = list(manifest.components)
    if corruption == "missing":
        nodes.pop()
    elif corruption == "duplicate":
        nodes.append(nodes[0])
    elif corruption == "cycle":
        nodes[0] = dataclasses.replace(nodes[0], parents=(nodes[-1].component_id,))
    elif corruption == "assembly_fit":
        nodes[5] = dataclasses.replace(nodes[5], operation="fit")
    elif corruption == "boolean_fold":
        nodes[0] = dataclasses.replace(nodes[0], fold=False)
    elif corruption == "unknown_operation":
        nodes[0] = dataclasses.replace(nodes[0], operation="reuse")
    else:
        nodes[-1] = dataclasses.replace(nodes[-1], parents=(nodes[0].component_id,))
    with pytest.raises(MLContractError, match="manifest"):
        validate_manifest(dataclasses.replace(manifest, components=tuple(nodes)))


@pytest.mark.parametrize(
    "dependency",
    [
        "uv.lock",
        "pyproject.toml",
        "src/alpha_qlib_worker/rank_ensemble.py",
        "src/alpha_qlib_worker/__main__.py",
        "src/alpha_qlib_worker/schemas/request-v2.schema.json",
        "src/alpha_qlib_worker/new_dependency.py",
    ],
)
def test_dependency_changes_block_the_frozen_manifest(tmp_path: Path, dependency: str) -> None:
    worker = _worker(tmp_path)
    manifest = build_manifest(_protocol(worker))
    (worker / dependency).write_text("changed synthetic source\n")
    report = readiness(manifest, worker)
    assert report["source_status"] == "CHANGED"
    assert "DEPENDENCY_CHANGED" in report["blockers"]
    assert report["execution_authorized"] is False


def test_matching_sources_cannot_authorize_or_claim_observed_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = _worker(tmp_path)
    manifest = build_manifest(_protocol(worker))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("dispatch forbidden"))
    report = readiness(manifest, worker)
    assert report["source_status"] == "MATCHED"
    assert report["status"] == "BLOCKED"
    assert report["execution_authorized"] is False
    assert report["reuse_authorized"] is False
    assert report["promotion_eligible"] is False
    assert report["counterfactual_refit"] is False
    assert report["observed_operations"] is None
    assert report["fitted_state_verified"] is False
    assert report["approved_resource_units"] is None
    assert report["blockers"]
    assert not list(worker.rglob("*.sqlite3"))


def test_missing_or_symlinked_dependencies_are_not_followed(tmp_path: Path) -> None:
    worker = _worker(tmp_path / "worker")
    target = worker / "src/alpha_qlib_worker/rank_ensemble.py"
    target.unlink()
    with pytest.raises(MLContractError):
        fingerprint_worker(worker)
    outside = tmp_path / "outside.py"
    outside.write_text("must not be followed\n")
    target.symlink_to(outside)
    with pytest.raises(MLContractError):
        fingerprint_worker(worker)


def test_missing_worker_is_reported_unavailable_without_creating_it(tmp_path: Path) -> None:
    worker = _worker(tmp_path / "worker")
    manifest = build_manifest(_protocol(worker))
    missing = tmp_path / "missing"
    report = readiness(manifest, missing)
    assert report["source_status"] == "UNAVAILABLE"
    assert report["current_dependency_sha256"] is None
    assert "DEPENDENCY_UNAVAILABLE" in report["blockers"]
    assert not missing.exists()


def test_dependencies_changed_during_fingerprinting_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import ml_native_plan
    from alpha_cli.ml_refit import _file_snapshot

    worker = _worker(tmp_path)
    original = _file_snapshot
    changed = False

    def mutate(path: Path, *, max_bytes: int | None = None) -> tuple[str, tuple[int, ...]]:
        nonlocal changed
        snapshot = original(path, max_bytes=max_bytes)
        if path.name == "uv.lock" and not changed:
            changed = True
            (worker / "src/alpha_qlib_worker/features.py").write_text("changed during read\n")
        return snapshot

    monkeypatch.setattr(ml_native_plan, "_file_snapshot", mutate)
    with pytest.raises(MLContractError, match="changed during"):
        fingerprint_worker(worker)


@pytest.mark.parametrize("name", ["evaluation", "tests", "result.parquet"])
def test_protected_or_unsupported_package_resources_are_rejected_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    from alpha_cli import ml_native_plan

    worker = _worker(tmp_path)
    resource = worker / "src/alpha_qlib_worker" / name
    resource.write_text("synthetic forbidden fixture; do not read\n")
    monkeypatch.setattr(
        ml_native_plan, "_file_snapshot", lambda p: pytest.fail("must reject before reading")
    )
    with pytest.raises(MLContractError):
        fingerprint_worker(worker)


class _ReadSpy:
    def __init__(self, handle: IO[bytes], after_read: Callable[[], None]) -> None:
        self.handle = handle
        self.after_read = after_read
        self.read_sizes: list[int] = []
        self.bytes_read = 0

    def fileno(self) -> int:
        return self.handle.fileno()

    def read(self, size: int) -> bytes:
        assert size >= 0, "bounded snapshots must not request an unbounded read"
        self.read_sizes.append(size)
        block = self.handle.read(size)
        self.bytes_read += len(block)
        self.after_read()
        return block


def _spy_reads(monkeypatch: pytest.MonkeyPatch, after_read: Callable[[], None]) -> list[_ReadSpy]:
    original = os.fdopen
    spies: list[_ReadSpy] = []

    @contextmanager
    def observed(descriptor: int, mode: str, buffering: int = -1) -> Iterator[_ReadSpy]:
        assert mode == "rb"
        assert buffering == 0, "bounded snapshots must disable read-ahead buffering"
        with original(descriptor, "rb", buffering=buffering) as handle:
            spy = _ReadSpy(handle, after_read)
            spies.append(spy)
            yield spy

    monkeypatch.setattr(os, "fdopen", observed)
    return spies


@pytest.mark.parametrize("content", [b"", b"exact-boundary"])
def test_bounded_snapshot_accepts_exact_boundary_with_unchanged_result(
    tmp_path: Path, content: bytes
) -> None:
    source = tmp_path / "source.py"
    source.write_bytes(content)
    expected = _file_snapshot(source)
    assert expected[0] == hashlib.sha256(content).hexdigest()
    assert _file_snapshot(source, max_bytes=len(content)) == expected


def test_bounded_snapshot_rejects_initial_oversize_without_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.py"
    source.write_bytes(b"too large")
    spies = _spy_reads(monkeypatch, lambda: None)
    with pytest.raises(MLContractError, match="exceeds byte bound"):
        _file_snapshot(source, max_bytes=4)
    assert len(spies) == 1
    assert spies[0].read_sizes == []


@pytest.mark.parametrize(
    "extra,limit,error", [(b"x" * 20, 8, "exceeds byte bound"), (b"xyz", 16, "changed during")]
)
def test_bounded_snapshot_growth_cannot_overread_or_escape_mutation_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: bytes, limit: int, error: str
) -> None:
    source = tmp_path / "source.py"
    source.write_bytes(b"base")
    grew = False

    def append_once() -> None:
        nonlocal grew
        if not grew:
            grew = True
            with source.open("ab") as writer:
                writer.write(extra)

    spies = _spy_reads(monkeypatch, append_once)
    with pytest.raises(MLContractError, match=error):
        _file_snapshot(source, max_bytes=limit)
    assert len(spies) == 1
    assert spies[0].bytes_read <= limit
    assert spies[0].read_sizes


def test_worker_fingerprint_uses_bounded_unbuffered_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import ml_native_plan

    worker = _worker(tmp_path)
    spies = _spy_reads(monkeypatch, lambda: None)
    fingerprint_worker(worker)
    assert spies
    assert all(spy.bytes_read <= ml_native_plan._MAX_FILE_BYTES for spy in spies)


def test_planning_identity_cannot_be_presented_as_completed_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import ml_native_plan

    worker = _worker(tmp_path)
    manifest = build_manifest(_protocol(worker))
    completed = dataclasses.replace(manifest.components[0], operation="completed")
    claimed = dataclasses.replace(manifest, components=(completed, *manifest.components[1:]))
    monkeypatch.setattr(
        ml_native_plan,
        "fingerprint_worker",
        lambda p: pytest.fail("must reject the evidence claim first"),
    )
    with pytest.raises(MLContractError, match="manifest"):
        readiness(claimed, worker)
