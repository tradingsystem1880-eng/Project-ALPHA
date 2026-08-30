"""Deterministic, non-authoritative strategy-project workspace projections."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from alpha_cli import project_workspace
from alpha_cli.control_store import ControlStore, parse_timestamp
from alpha_cli.main import app
from alpha_cli.project_workspace import (
    WORKSPACE_CATEGORIES,
    read_project_workspace,
    recover_project_workspace,
    sync_all_project_workspaces,
    sync_project_workspace,
)
from alpha_core import DataError
from tests.fixtures.control_store_fixtures import (
    mark_project_as_migrated_legacy,
    publish_decision_grade_run,
)

runner = CliRunner()


def _project(store: ControlStore, *, name: str = "BTC Carry / Core") -> str:
    row = store.create_project(
        name=name,
        hypothesis="BTC carry is measurable without conferring execution authority.",
        falsification_criterion="Reject when locked OOS evidence is non-positive.",
        at=parse_timestamp("2026-07-30T00:00:00Z"),
    )
    return str(row["project_id"])


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _manifest(projection: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], projection["workspace"])


def _rehash_revision(root: Path, revision: str, category: str) -> None:
    """Rehash a deliberately edited revision without changing its content address."""
    revision_root = root / "revisions" / revision
    index_path = revision_root / "indexes" / f"{category}.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["content_sha256"] = project_workspace._sha256(
        {key: value for key, value in index.items() if key != "content_sha256"}
    )
    index_path.write_bytes(project_workspace._json_bytes(index))
    manifest_path = revision_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    descriptor = next(row for row in manifest["indexes"] if row["category"] == category)
    descriptor["sha256"] = project_workspace._file_sha256(index_path)
    descriptor["reference_count"] = len(index["references"])
    manifest["content_sha256"] = project_workspace._sha256(
        {key: value for key, value in manifest.items() if key != "content_sha256"}
    )
    manifest_path.write_bytes(project_workspace._json_bytes(manifest))
    pointer_path = root / "current.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["manifest_sha256"] = project_workspace._file_sha256(manifest_path)
    pointer_path.write_bytes(project_workspace._json_bytes(pointer))


def test_workspace_sync_is_deterministic_idempotent_and_reference_only(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)

    first = sync_project_workspace(store, tmp_path, project_id)
    root = tmp_path / "strategy-workspaces" / f"btc-carry-core--{project_id}"
    before = _tree_bytes(root)
    second = sync_project_workspace(store, tmp_path, project_id)

    assert first["changed"] is True
    assert second["changed"] is False
    assert before == _tree_bytes(root)
    projection = read_project_workspace(store, tmp_path, project_id)
    assert projection["stale"] is False
    manifest = _manifest(projection)
    assert manifest["schema_name"] == "StrategyProjectWorkspaceV1"
    assert tuple(cast(list[str], manifest["categories"])) == WORKSPACE_CATEGORIES
    assert manifest["authority"] == "none"
    assert manifest["execution_authority"] is False
    assert all(path.suffix in {".json", ".md"} for path in root.rglob("*") if path.is_file())
    serialized = b"\n".join(before.values())
    assert b"BTC carry is measurable" not in serialized


def test_workspace_stale_revision_preserves_prior_revision(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    mark_project_as_migrated_legacy(store, project_id)
    first = sync_project_workspace(store, tmp_path, project_id)
    first_revision = str(_manifest(first)["revision_id"])

    store.create_strategy_version(
        project_id,
        strategy_name="btc_carry",
        source_fingerprint="git:abc1234",
        definition={"signal": "basis"},
        parameter_space={"window": [24]},
        at=parse_timestamp("2026-08-30T00:01:00Z"),
    )

    assert read_project_workspace(store, tmp_path, project_id)["stale"] is True
    updated = sync_project_workspace(store, tmp_path, project_id)
    assert _manifest(updated)["revision_id"] != first_revision
    assert (tmp_path / str(updated["workspace_root"]) / "revisions" / first_revision).is_dir()


def test_pointer_publication_failure_keeps_last_valid_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    original = sync_project_workspace(store, tmp_path, project_id)
    mark_project_as_migrated_legacy(store, project_id)
    store.create_strategy_version(
        project_id,
        strategy_name="btc_carry",
        source_fingerprint="git:def5678",
        definition={"signal": "funding"},
        parameter_space={"window": [8]},
    )

    def _fail(_path: Path, _payload: bytes) -> None:
        raise OSError("injected pointer failure")

    monkeypatch.setattr(project_workspace, "_replace_current_pointer", _fail)
    with pytest.raises(DataError, match="last valid workspace remains current"):
        sync_project_workspace(store, tmp_path, project_id)

    root = tmp_path / str(original["workspace_root"])
    current = json.loads((root / "current.json").read_text(encoding="utf-8"))
    assert current["revision_id"] == _manifest(original)["revision_id"]


def test_tamper_is_rejected_then_explicit_recovery_quarantines_generated_state(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    initial = sync_project_workspace(store, tmp_path, project_id)
    root = tmp_path / str(initial["workspace_root"])
    revision = str(_manifest(initial)["revision_id"])
    index = root / "revisions" / revision / "indexes" / "research.json"
    index.write_text("{}\n", encoding="utf-8")

    with pytest.raises(DataError, match="tampered generated workspace.*workspace recover"):
        sync_project_workspace(store, tmp_path, project_id)

    recovered = recover_project_workspace(store, tmp_path, project_id)
    assert recovered["recovered"] is True
    assert read_project_workspace(store, tmp_path, project_id)["stale"] is False
    assert any((root / "quarantine").iterdir())


def test_missing_run_reference_is_explicit_and_sync_all_backfills_two_projects(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    first_id = _project(store, name="BTC Core")
    second_id = _project(store, name="ETH Core")
    mark_project_as_migrated_legacy(store, first_id)
    version = store.create_strategy_version(
        first_id,
        strategy_name="btc_core",
        source_fingerprint="git:1234abc",
        definition={"signal": "basis"},
        parameter_space={"window": [24]},
    )
    experiment = store.create_experiment_spec(
        first_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="snapshot_missing",
        universe=["BTCUSDT"],
        split_policy={"kind": "walk_forward"},
        costs={"fee_bps": 5},
        seeds={"main": 7},
    )
    snapshot_manifest = tmp_path / "snapshots" / "snapshot_missing" / "manifest.json"
    snapshot_manifest.parent.mkdir(parents=True)
    snapshot_manifest.write_text(
        json.dumps({"snapshot_id": "snapshot_missing", "symbols": {}}, sort_keys=True),
        encoding="utf-8",
    )
    run_id = "0123456789abcdef"
    publish_decision_grade_run(tmp_path, run_id=run_id)
    store.link_stage_run(
        first_id,
        str(experiment["experiment_id"]),
        stage="baseline",
        state="running",
        run_id=run_id,
    )
    (tmp_path / "optim").mkdir()
    shutil.move(tmp_path / "runs" / run_id, tmp_path / "optim" / run_id)

    result = sync_all_project_workspaces(store, tmp_path)
    assert result["project_count"] == 2
    batch = cast(list[dict[str, object]], result["projects"])
    assert {item["project_id"] for item in batch} == {first_id, second_id}
    projection = read_project_workspace(store, tmp_path, first_id)
    revision_root = (
        tmp_path
        / str(projection["workspace_root"])
        / "revisions"
        / str(_manifest(projection)["revision_id"])
    )
    runs = json.loads((revision_root / "indexes" / "runs.json").read_text(encoding="utf-8"))
    assert any(
        ref["reference_id"] == run_id and ref["availability"] == "present"
        for ref in runs["references"]
    )
    datasets = json.loads((revision_root / "indexes" / "datasets.json").read_text(encoding="utf-8"))
    assert any(
        ref["reference_type"] == "dataset-snapshot"
        and ref["reference_id"] == "snapshot_missing"
        and ref["availability"] == "present"
        for ref in datasets["references"]
    )

    shutil.rmtree(tmp_path / "optim" / run_id)
    snapshot_manifest.unlink()
    sync_project_workspace(store, tmp_path, first_id)
    missing_projection = read_project_workspace(store, tmp_path, first_id)
    missing_root = (
        tmp_path
        / str(missing_projection["workspace_root"])
        / "revisions"
        / str(_manifest(missing_projection)["revision_id"])
    )
    missing_runs = json.loads((missing_root / "indexes" / "runs.json").read_text(encoding="utf-8"))
    missing_datasets = json.loads(
        (missing_root / "indexes" / "datasets.json").read_text(encoding="utf-8")
    )
    assert any(
        ref["reference_id"] == run_id and ref["availability"] == "missing"
        for ref in missing_runs["references"]
    )
    assert any(
        ref["reference_id"] == "snapshot_missing" and ref["availability"] == "missing"
        for ref in missing_datasets["references"]
    )


def test_project_create_materializes_workspace_and_cli_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    created = runner.invoke(
        app,
        [
            "project",
            "create",
            "BTC governed",
            "--hypothesis",
            "BTC has a bounded technical event effect.",
            "--falsification",
            "Reject on an inconclusive locked result.",
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    project_id = str(json.loads(created.output)["project_id"])
    shown = runner.invoke(app, ["project", "workspace", "show", project_id, "--json"])
    assert shown.exit_code == 0, shown.output
    projection = json.loads(shown.output)
    assert projection["project_id"] == project_id
    assert projection["stale"] is False
    synced = runner.invoke(app, ["project", "workspace", "sync", project_id, "--json"])
    assert synced.exit_code == 0, synced.output
    assert json.loads(synced.output)["changed"] is False


@pytest.mark.parametrize("error_type", [DataError, OSError])
def test_project_create_commits_authority_when_initial_workspace_projection_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))

    def _fail(_store: ControlStore, _data_dir: Path, _project_id: str) -> dict[str, object]:
        raise error_type("injected projection failure")

    monkeypatch.setattr(project_workspace, "sync_project_workspace", _fail)
    created = runner.invoke(
        app,
        [
            "project",
            "create",
            "ETH governed",
            "--hypothesis",
            "ETH crowding may be measurable.",
            "--falsification",
            "Reject on an inconclusive locked result.",
            "--json",
        ],
    )
    assert created.exit_code != 0
    assert "project authority committed" in created.output
    assert "workspace recover" in created.output
    rows = ControlStore(tmp_path).list_projects()
    assert len(rows) == 1


def test_workspace_rejects_invalid_ids_availability_and_reference_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(DataError, match="canonical project UUID"):
        project_workspace.workspace_root(tmp_path, {"project_id": "bad", "name": "bad"})
    with pytest.raises(DataError, match="availability"):
        project_workspace._reference("run", "id", {}, availability="unknown")
    monkeypatch.setattr(project_workspace, "_MAX_REFERENCES", 0)
    with pytest.raises(DataError, match="exceeds"):
        project_workspace._bounded([project_workspace._reference("run", "id", {})], "runs")


def test_unmaterialized_workspace_read_fails_with_sync_recovery(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    with pytest.raises(DataError, match="workspace sync"):
        read_project_workspace(store, tmp_path, project_id)


@pytest.mark.parametrize(
    "tamper",
    [
        "root-extra",
        "pointer-json",
        "pointer-list",
        "pointer-shape",
        "pointer-schema",
        "pointer-hash",
        "manifest",
        "descriptor",
        "index-shape",
        "reference",
        "readme",
    ],
)
def test_strict_workspace_validation_rejects_generated_state_tamper(
    tmp_path: Path, tamper: str
) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    projection = sync_project_workspace(store, tmp_path, project_id)
    root = tmp_path / str(projection["workspace_root"])
    revision = str(_manifest(projection)["revision_id"])
    revision_root = root / "revisions" / revision
    pointer_path = root / "current.json"
    manifest_path = revision_root / "manifest.json"
    research_path = revision_root / "indexes" / "research.json"

    if tamper == "root-extra":
        (root / "unexpected.txt").write_text("generated tamper", encoding="utf-8")
    elif tamper == "pointer-json":
        pointer_path.write_text("[", encoding="utf-8")
    elif tamper == "pointer-list":
        pointer_path.write_text("[]\n", encoding="utf-8")
    elif tamper == "pointer-shape":
        pointer_path.write_text("{}\n", encoding="utf-8")
    elif tamper == "pointer-schema":
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        pointer["schema_name"] = "Wrong"
        pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    elif tamper == "pointer-hash":
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        pointer["manifest_sha256"] = "0" * 64
        pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    elif tamper == "manifest":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["authority"] = "sqlite"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif tamper == "descriptor":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["indexes"][0] = {}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif tamper == "index-shape":
        index = json.loads(research_path.read_text(encoding="utf-8"))
        index["schema_name"] = "Wrong"
        research_path.write_text(json.dumps(index), encoding="utf-8")
    elif tamper == "reference":
        index = json.loads(research_path.read_text(encoding="utf-8"))
        index["references"][0]["availability"] = "unknown"
        index["content_sha256"] = project_workspace._sha256(
            {key: value for key, value in index.items() if key != "content_sha256"}
        )
        research_path.write_bytes(project_workspace._json_bytes(index))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["indexes"][0]["sha256"] = project_workspace._file_sha256(research_path)
        unsigned = {key: value for key, value in manifest.items() if key != "content_sha256"}
        manifest["content_sha256"] = project_workspace._sha256(unsigned)
        manifest_path.write_bytes(project_workspace._json_bytes(manifest))
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        pointer["manifest_sha256"] = project_workspace._file_sha256(manifest_path)
        pointer_path.write_bytes(project_workspace._json_bytes(pointer))
    else:
        (revision_root / "README.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(DataError, match="tampered generated workspace"):
        read_project_workspace(store, tmp_path, project_id)


def test_self_consistent_rehash_cannot_change_revision_content(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    projection = sync_project_workspace(store, tmp_path, project_id)
    root = tmp_path / str(projection["workspace_root"])
    revision = str(_manifest(projection)["revision_id"])
    research_path = root / "revisions" / revision / "indexes" / "research.json"
    research = json.loads(research_path.read_text(encoding="utf-8"))
    research["references"][0]["reference_id"] = str(uuid.uuid4())
    research_path.write_bytes(project_workspace._json_bytes(research))
    _rehash_revision(root, revision, "research")

    with pytest.raises(DataError, match="revision content address"):
        read_project_workspace(store, tmp_path, project_id)


def test_workspace_revision_cannot_be_copied_across_projects(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    first_id = _project(store, name="Shared name")
    second_id = _project(store, name="Shared name")
    first = sync_project_workspace(store, tmp_path, first_id)
    second = sync_project_workspace(store, tmp_path, second_id)
    first_root = tmp_path / str(first["workspace_root"])
    second_root = tmp_path / str(second["workspace_root"])
    shutil.rmtree(second_root / "revisions")
    shutil.copytree(first_root / "revisions", second_root / "revisions")
    shutil.copy2(first_root / "current.json", second_root / "current.json")

    with pytest.raises(DataError, match="tampered generated workspace manifest"):
        read_project_workspace(store, tmp_path, second_id)


def test_workspace_readme_symlink_is_rejected_without_touching_target(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    projection = sync_project_workspace(store, tmp_path, project_id)
    root = tmp_path / str(projection["workspace_root"])
    revision = str(_manifest(projection)["revision_id"])
    readme = root / "revisions" / revision / "README.md"
    expected = readme.read_bytes()
    outside = tmp_path / "owner-readme.md"
    outside.write_bytes(expected)
    readme.unlink()
    readme.symlink_to(outside)

    with pytest.raises(DataError, match="symlink"):
        read_project_workspace(store, tmp_path, project_id)
    assert outside.read_bytes() == expected


def test_project_record_paging_is_complete_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows: list[dict[str, object]] = [{"id": index} for index in range(501)]
    calls: list[tuple[int, int]] = []

    def _load(limit: int, offset: int) -> list[dict[str, object]]:
        calls.append((limit, offset))
        return rows[offset : offset + limit]

    assert len(project_workspace._all_project_records(_load, "records")) == 501
    assert calls == [(500, 0), (500, 500)]
    monkeypatch.setattr(project_workspace, "_MAX_REFERENCES", 500)
    with pytest.raises(DataError, match="exceeds"):
        project_workspace._all_project_records(_load, "records")


def test_referenced_authority_errors_are_not_silently_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    original_collect = project_workspace._collect_ids

    def _collect(value: object, *, suffixes: tuple[str, ...]) -> set[str]:
        result = original_collect(value, suffixes=suffixes)
        if suffixes == ("dataset_ref_id", "ref_id"):
            result.add("rd_" + "a" * 64)
        return result

    monkeypatch.setattr(project_workspace, "_collect_ids", _collect)
    monkeypatch.setattr(
        store,
        "get_research_dataset",
        lambda _ref_id: (_ for _ in ()).throw(DataError("corrupt referenced dataset")),
    )
    with pytest.raises(DataError, match="corrupt referenced dataset"):
        sync_project_workspace(store, tmp_path, project_id)


def test_promotion_errors_and_research_attempts_use_verified_packet_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    run_id = "0123456789abcdef"
    publish_decision_grade_run(tmp_path, run_id=run_id)
    summary = {"active_contract_id": "rc_case"}
    packet = {
        "contracts": [{"contract_id": "rc_case", "payload_hash": "a" * 64}],
        "attempts": [
            {
                "attempt_id": "ra_case",
                "contract_id": "rc_case",
                "phase": "pilot",
                "run_id": run_id,
            }
        ],
    }
    monkeypatch.setattr(project_workspace, "_research_projection", lambda *_args: summary)
    monkeypatch.setattr(project_workspace, "_research_packet", lambda *_args: packet)
    monkeypatch.setattr(store, "research_promotion_reference", lambda *_args: None)

    projection = sync_project_workspace(store, tmp_path, project_id)
    revision_root = (
        tmp_path
        / str(projection["workspace_root"])
        / "revisions"
        / str(_manifest(projection)["revision_id"])
    )
    research = json.loads((revision_root / "indexes" / "research.json").read_text(encoding="utf-8"))
    runs = json.loads((revision_root / "indexes" / "runs.json").read_text(encoding="utf-8"))
    assert any(ref["reference_type"] == "research-attempt" for ref in research["references"])
    assert any(ref["reference_type"] == "research-run" for ref in runs["references"])

    monkeypatch.setattr(
        store,
        "research_promotion_reference",
        lambda *_args: (_ for _ in ()).throw(DataError("corrupt promotion authority")),
    )
    with pytest.raises(DataError, match="corrupt promotion authority"):
        sync_project_workspace(store, tmp_path, project_id)


def test_failed_first_pointer_publish_requires_recovery_and_reuses_valid_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    original_replace = project_workspace._replace_current_pointer

    def _fail(_path: Path, _payload: bytes) -> None:
        raise OSError("injected first pointer failure")

    monkeypatch.setattr(project_workspace, "_replace_current_pointer", _fail)
    with pytest.raises(DataError, match="last valid workspace remains current"):
        sync_project_workspace(store, tmp_path, project_id)
    monkeypatch.setattr(project_workspace, "_replace_current_pointer", original_replace)

    with pytest.raises(DataError, match="no current pointer"):
        sync_project_workspace(store, tmp_path, project_id)
    recovered = recover_project_workspace(store, tmp_path, project_id)
    assert recovered["recovered"] is True


def test_revision_rename_failure_cleans_staging_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    project = store.get_project(project_id)
    manifest, indexes, readme = project_workspace._build_snapshot(store, tmp_path, project)
    root = project_workspace.workspace_root(tmp_path, project)
    original_replace = os.replace

    def _fail_revision(source: str | Path, destination: str | Path) -> None:
        if Path(source).name.startswith(".workspace-"):
            raise OSError("injected revision rename failure")
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", _fail_revision)
    with pytest.raises(DataError, match="atomically publish"):
        project_workspace._write_revision(root, manifest, indexes, readme)
    assert not list((root / "revisions").glob(".workspace-*.tmp"))


@pytest.mark.parametrize("reserved_name", ["revisions", "quarantine"])
def test_recovery_never_follows_reserved_container_symlinks(
    tmp_path: Path, reserved_name: str
) -> None:
    store = ControlStore(tmp_path)
    project_id = _project(store)
    projection = sync_project_workspace(store, tmp_path, project_id)
    root = tmp_path / str(projection["workspace_root"])
    outside = tmp_path / f"outside-{reserved_name}"
    outside.mkdir()
    sentinel = outside / "owner-file.txt"
    sentinel.write_bytes(b"owner bytes must remain outside and unchanged")
    before = {path.name: path.read_bytes() for path in outside.iterdir()}

    reserved = root / reserved_name
    if reserved.exists():
        shutil.rmtree(reserved)
    reserved.symlink_to(outside, target_is_directory=True)
    if reserved_name == "quarantine":
        (root / "current.json").write_text("{}\n", encoding="utf-8")

    recovered = recover_project_workspace(store, tmp_path, project_id)

    assert recovered["recovered"] is True
    assert not reserved.is_symlink()
    assert reserved.is_dir()
    assert {path.name: path.read_bytes() for path in outside.iterdir()} == before
    assert sentinel.read_bytes() == b"owner bytes must remain outside and unchanged"
    assert read_project_workspace(store, tmp_path, project_id)["stale"] is False
