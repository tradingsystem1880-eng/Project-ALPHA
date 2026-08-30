"""Deterministic, non-authoritative workspaces for governed strategy projects."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import cast

from alpha_cli.control_store import ControlStore
from alpha_cli.run_store import find_run_dir, read_manifest
from alpha_core import DataError
from alpha_data.snapshot import resolve_snapshot_dir

WORKSPACE_CATEGORIES = (
    "research",
    "sources",
    "datasets",
    "study-state",
    "promotion",
    "strategy-versions",
    "experiments",
    "runs",
    "validation",
    "figures",
    "reports",
    "sandbox-eligibility",
)
_MAX_REFERENCES = 10_000
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_REVISION_RE = re.compile(r"spw_[0-9a-f]{64}")


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(name: object) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return (clean or "project")[:48].rstrip("-") or "project"


def workspace_root(data_dir: Path, project: Mapping[str, object]) -> Path:
    """Return the generated root without consulting or mutating authority."""
    project_id = str(project["project_id"])
    if re.fullmatch(r"[0-9a-f-]{36}", project_id) is None:
        raise DataError("strategy workspace requires a canonical project UUID")
    return data_dir / "strategy-workspaces" / f"{_slug(project['name'])}--{project_id}"


def _reference(
    reference_type: str,
    reference_id: object,
    authority_record: object,
    *,
    availability: str = "present",
) -> dict[str, object]:
    if availability not in {"present", "missing"}:
        raise DataError("workspace reference availability must be present or missing")
    return {
        "reference_type": reference_type,
        "reference_id": str(reference_id),
        "reference_sha256": _sha256(authority_record),
        "availability": availability,
    }


def _bounded(rows: Iterable[dict[str, object]], category: str) -> list[dict[str, object]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row["reference_type"]),
            str(row["reference_id"]),
            str(row["reference_sha256"]),
        ),
    )
    if len(ordered) > _MAX_REFERENCES:
        raise DataError(
            f"workspace category {category!r} exceeds the {_MAX_REFERENCES}-reference bound"
        )
    return ordered


def _collect_ids(value: object, *, suffixes: tuple[str, ...]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(child, str) and any(str(key).endswith(suffix) for suffix in suffixes):
                found.add(child)
            found.update(_collect_ids(child, suffixes=suffixes))
    elif isinstance(value, list):
        for child in value:
            found.update(_collect_ids(child, suffixes=suffixes))
    return found


def _research_projection(store: ControlStore, project_id: str) -> dict[str, object] | None:
    try:
        return store.research_case_summary(project_id)
    except DataError as exc:
        if not str(exc).endswith("has no research case"):
            raise
        return None


def _research_packet(
    store: ControlStore, project_id: str, research: Mapping[str, object] | None
) -> dict[str, object] | None:
    """Read the verified governed lineage only when a research case exists."""
    if research is None:
        return None
    return store.research_gate_packet_inputs(project_id)


def _all_project_records(
    loader: Callable[[int, int], list[dict[str, object]]], label: str
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    offset = 0
    while True:
        page = loader(500, offset)
        records.extend(page)
        if len(records) > _MAX_REFERENCES:
            raise DataError(f"workspace {label} exceeds the {_MAX_REFERENCES}-reference bound")
        if len(page) < 500:
            return records
        offset += len(page)


def _authority_indexes(
    store: ControlStore, data_dir: Path, project: Mapping[str, object]
) -> dict[str, list[dict[str, object]]]:
    project_id = str(project["project_id"])
    research = _research_projection(store, project_id)
    research_packet = _research_packet(store, project_id, research)
    sources = _all_project_records(
        lambda limit, offset: store.list_research_sources(project_id, limit=limit, offset=offset),
        "research sources",
    )
    packs = _all_project_records(
        lambda limit, offset: store.list_research_source_packs(
            project_id, limit=limit, offset=offset
        ),
        "research source packs",
    )
    semantic_events, semantic_head = store.read_semantic_state(project_id)

    project_identity = {
        "project_id": project_id,
        "name": project["name"],
        "status": project["status"],
        "current_version_id": project["current_version_id"],
        "current_experiment_id": project["current_experiment_id"],
        "research_gate_state": project["research_gate_state"],
    }
    indexes: dict[str, list[dict[str, object]]] = {
        category: [] for category in WORKSPACE_CATEGORIES
    }
    indexes["research"].append(_reference("strategy-project", project_id, project_identity))
    if research_packet is not None:
        for contract in cast(list[dict[str, object]], research_packet["contracts"]):
            indexes["research"].append(
                _reference("research-contract", contract["contract_id"], contract)
            )
        for attempt in cast(list[dict[str, object]], research_packet["attempts"]):
            indexes["research"].append(
                _reference("research-attempt", attempt["attempt_id"], attempt)
            )

    for source in sources:
        indexes["sources"].append(_reference("research-source", source["source_id"], source))
    for pack in packs:
        indexes["sources"].append(_reference("research-source-pack", pack["pack_id"], pack))

    dataset_ids = _collect_ids(
        {"project": project, "research": research}, suffixes=("dataset_ref_id", "ref_id")
    )
    dataset_ids = {ref_id for ref_id in dataset_ids if ref_id.startswith("rd_")}
    for experiment in cast(list[dict[str, object]], project["experiments"]):
        snapshot_id = experiment.get("snapshot_id")
        if isinstance(snapshot_id, str):
            snapshot_dir = resolve_snapshot_dir(data_dir / "snapshots", snapshot_id)
            snapshot_manifest = snapshot_dir / "manifest.json"
            snapshot_present = snapshot_manifest.is_file() and not snapshot_manifest.is_symlink()
            snapshot_authority: dict[str, object] = {"experiment": experiment}
            if snapshot_present:
                snapshot_authority["manifest_sha256"] = _file_sha256(snapshot_manifest)
            indexes["datasets"].append(
                _reference(
                    "dataset-snapshot",
                    snapshot_id,
                    snapshot_authority,
                    availability="present" if snapshot_present else "missing",
                )
            )
    for ref_id in sorted(dataset_ids):
        dataset = store.get_research_dataset(ref_id)
        indexes["datasets"].append(_reference("research-dataset", ref_id, dataset))

    indexes["study-state"].append(
        _reference(
            "semantic-event-head",
            semantic_head,
            {"head_sha256": semantic_head, "events": semantic_events},
        )
    )
    for event in semantic_events:
        indexes["study-state"].append(_reference("semantic-event", event["event_id"], event))

    if research is not None:
        for contract_id in sorted(_collect_ids(research, suffixes=("contract_id",))):
            promotion = store.research_promotion_reference(project_id, contract_id)
            if promotion is not None:
                indexes["promotion"].append(
                    _reference("promotion-dossier", promotion["packet_id"], promotion)
                )

    for version in cast(list[dict[str, object]], project["versions"]):
        indexes["strategy-versions"].append(
            _reference("strategy-version", version["version_id"], version)
        )
    for experiment in cast(list[dict[str, object]], project["experiments"]):
        indexes["experiments"].append(
            _reference("experiment", experiment["experiment_id"], experiment)
        )

    for link in cast(list[dict[str, object]], project["stage_run_links"]):
        run_id = str(link["run_id"])
        run_path = find_run_dir(data_dir, run_id)
        availability = "present" if run_path is not None else "missing"
        run_authority: dict[str, object] = {"link": link}
        if run_path is not None:
            manifest = read_manifest(run_path)
            if manifest.get("run_id") != run_id:
                raise DataError(f"immutable run manifest id does not match linked run {run_id!r}")
            run_authority["run_store"] = run_path.parent.name
            run_authority["manifest_sha256"] = _sha256(manifest)
        indexes["runs"].append(
            _reference("immutable-run", run_id, run_authority, availability=availability)
        )
        stage = str(link["stage"])
        if stage in {"oos", "robustness", "monte_carlo", "holdout", "decision"}:
            indexes["validation"].append(
                _reference("validation-run", run_id, link, availability=availability)
            )
        indexes["figures"].append(
            _reference(
                "run-figure-catalogue",
                run_id,
                {"run_id": run_id, "stage": stage, "kind": "figures"},
                availability=availability,
            )
        )
        indexes["reports"].append(
            _reference(
                "run-report-catalogue",
                run_id,
                {"run_id": run_id, "stage": stage, "kind": "reports"},
                availability=availability,
            )
        )

    if research_packet is not None:
        for attempt in cast(list[dict[str, object]], research_packet["attempts"]):
            research_run_id = attempt.get("run_id")
            if not isinstance(research_run_id, str):
                continue
            run_path = find_run_dir(data_dir, research_run_id)
            if run_path is None:  # The packet verifier already requires completed-run presence.
                raise DataError(f"verified research attempt run {research_run_id!r} disappeared")
            manifest = read_manifest(run_path)
            if manifest.get("run_id") != research_run_id:
                raise DataError(
                    "immutable research run manifest id does not match attempt run "
                    f"{research_run_id!r}"
                )
            authority = {
                "attempt": attempt,
                "run_store": run_path.parent.name,
                "manifest_sha256": _sha256(manifest),
            }
            indexes["runs"].append(_reference("research-run", research_run_id, authority))
            indexes["figures"].append(
                _reference(
                    "research-run-figure-catalogue",
                    research_run_id,
                    {
                        "run_id": research_run_id,
                        "phase": attempt.get("phase"),
                        "kind": "figures",
                    },
                )
            )
            indexes["reports"].append(
                _reference(
                    "research-run-report-catalogue",
                    research_run_id,
                    {
                        "run_id": research_run_id,
                        "phase": attempt.get("phase"),
                        "kind": "reports",
                    },
                )
            )

    eligibility = {
        "project_id": project_id,
        "classification": "non-transmitting-sandbox-only",
        "eligible": False,
        "broker_authority": False,
        "order_authority": False,
        "reason": "workspace projections never confer execution authority",
    }
    indexes["sandbox-eligibility"].append(
        _reference("sandbox-eligibility", project_id, eligibility)
    )
    return {category: _bounded(rows, category) for category, rows in indexes.items()}


def _build_snapshot(
    store: ControlStore, data_dir: Path, project: Mapping[str, object]
) -> tuple[dict[str, object], dict[str, dict[str, object]], str]:
    project_id = str(project["project_id"])
    reference_sets = _authority_indexes(store, data_dir, project)
    indexes: dict[str, dict[str, object]] = {}
    descriptors: list[dict[str, object]] = []
    for category in WORKSPACE_CATEGORIES:
        unsigned = {
            "schema_name": "StrategyProjectWorkspaceIndexV1",
            "schema_version": 1,
            "project_id": project_id,
            "category": category,
            "references": reference_sets[category],
        }
        index = {**unsigned, "content_sha256": _sha256(unsigned)}
        indexes[category] = index
        descriptors.append(
            {
                "category": category,
                "path": f"indexes/{category}.json",
                "sha256": hashlib.sha256(_json_bytes(index)).hexdigest(),
                "reference_count": len(reference_sets[category]),
            }
        )
    revision_input = {
        "schema_version": 1,
        "project_id": project_id,
        "project_name_sha256": _sha256(str(project["name"])),
        "indexes": descriptors,
        "authority": "none",
        "execution_authority": False,
    }
    revision_id = f"spw_{_sha256(revision_input)}"
    unsigned_manifest = {
        "schema_name": "StrategyProjectWorkspaceV1",
        "schema_version": 1,
        "revision_id": revision_id,
        "project_id": project_id,
        "project_name_sha256": revision_input["project_name_sha256"],
        "authority": "none",
        "execution_authority": False,
        "categories": list(WORKSPACE_CATEGORIES),
        "indexes": descriptors,
        "sandbox_classification": "non-transmitting-sandbox-only",
    }
    manifest = {**unsigned_manifest, "content_sha256": _sha256(unsigned_manifest)}
    readme = _readme(manifest)
    return manifest, indexes, readme


def _readme(manifest: Mapping[str, object]) -> str:
    project_id = str(manifest["project_id"])
    revision_id = str(manifest["revision_id"])
    categories = cast(list[str], manifest["categories"])
    lines = [
        "# Strategy Project Workspace",
        "",
        f"Project: `{project_id}`",
        f"Revision: `{revision_id}`",
        "",
        "This directory is a deterministic, non-authoritative reference projection.",
        "It stores identifiers and hashes only. SQLite and immutable run artifacts remain "
        "authority.",
        "It grants no broker, paper, order, promotion, or research-gate authority.",
        "",
        "## Reference indexes",
        "",
        *[f"- `{category}`" for category in categories],
        "",
    ]
    return "\n".join(lines)


def _reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise DataError(f"tampered generated workspace contains symlink {path.name!r}")


def _load_json(path: Path) -> dict[str, object]:
    _reject_symlink(path)
    if not path.is_file():
        raise DataError(f"tampered generated workspace file {path.name!r}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataError(f"tampered generated workspace file {path.name!r}") from exc
    if not isinstance(value, dict):
        raise DataError(f"tampered generated workspace file {path.name!r}")
    return cast(dict[str, object], value)


def _validate_revision(
    revision_dir: Path,
    *,
    expected_revision_id: str | None = None,
    expected_project_id: str | None = None,
) -> dict[str, object]:
    _reject_symlink(revision_dir)
    revision_id = revision_dir.name if expected_revision_id is None else expected_revision_id
    if (
        not revision_dir.is_dir()
        or _REVISION_RE.fullmatch(revision_id) is None
        or (expected_revision_id is None and _REVISION_RE.fullmatch(revision_dir.name) is None)
    ):
        raise DataError("tampered generated workspace revision")
    expected = {"manifest.json", "README.md", "indexes"}
    if {entry.name for entry in revision_dir.iterdir()} != expected:
        raise DataError("tampered generated workspace revision file set")
    indexes_dir = revision_dir / "indexes"
    _reject_symlink(indexes_dir)
    if not indexes_dir.is_dir():
        raise DataError("tampered generated workspace index directory")
    expected_indexes = {f"{category}.json" for category in WORKSPACE_CATEGORIES}
    if {entry.name for entry in indexes_dir.iterdir()} != expected_indexes:
        raise DataError("tampered generated workspace index file set")
    manifest = _load_json(revision_dir / "manifest.json")
    unsigned = dict(manifest)
    content_sha = unsigned.pop("content_sha256", None)
    required_manifest = {
        "schema_name",
        "schema_version",
        "revision_id",
        "project_id",
        "project_name_sha256",
        "authority",
        "execution_authority",
        "categories",
        "indexes",
        "sandbox_classification",
    }
    if (
        set(unsigned) != required_manifest
        or manifest.get("schema_name") != "StrategyProjectWorkspaceV1"
        or manifest.get("schema_version") != 1
        or manifest.get("revision_id") != revision_id
        or manifest.get("categories") != list(WORKSPACE_CATEGORIES)
        or manifest.get("authority") != "none"
        or manifest.get("execution_authority") is not False
        or manifest.get("sandbox_classification") != "non-transmitting-sandbox-only"
        or not isinstance(manifest.get("project_id"), str)
        or not isinstance(manifest.get("project_name_sha256"), str)
        or _SHA256_RE.fullmatch(str(manifest.get("project_name_sha256"))) is None
        or (expected_project_id is not None and manifest.get("project_id") != expected_project_id)
        or content_sha != _sha256(unsigned)
    ):
        raise DataError("tampered generated workspace manifest")
    descriptors = manifest.get("indexes")
    if not isinstance(descriptors, list) or len(descriptors) != len(WORKSPACE_CATEGORIES):
        raise DataError("tampered generated workspace index descriptors")
    for category, descriptor in zip(WORKSPACE_CATEGORIES, descriptors, strict=True):
        if not isinstance(descriptor, dict) or set(descriptor) != {
            "category",
            "path",
            "sha256",
            "reference_count",
        }:
            raise DataError("tampered generated workspace index descriptor")
        path = indexes_dir / f"{category}.json"
        index = _load_json(path)
        unsigned_index = dict(index)
        index_content_sha = unsigned_index.pop("content_sha256", None)
        references = index.get("references")
        if (
            descriptor["category"] != category
            or descriptor["path"] != f"indexes/{category}.json"
            or descriptor["sha256"] != _file_sha256(path)
            or not isinstance(references, list)
            or descriptor["reference_count"] != len(references)
            or index.get("schema_name") != "StrategyProjectWorkspaceIndexV1"
            or index.get("schema_version") != 1
            or index.get("project_id") != manifest["project_id"]
            or index.get("category") != category
            or set(unsigned_index)
            != {"schema_name", "schema_version", "project_id", "category", "references"}
            or index_content_sha != _sha256(unsigned_index)
        ):
            raise DataError(f"tampered generated workspace index {category!r}")
        for reference in references:
            if (
                not isinstance(reference, dict)
                or set(reference)
                != {"reference_type", "reference_id", "reference_sha256", "availability"}
                or not isinstance(reference["reference_type"], str)
                or not isinstance(reference["reference_id"], str)
                or not isinstance(reference["reference_sha256"], str)
                or _SHA256_RE.fullmatch(reference["reference_sha256"]) is None
                or reference["availability"] not in {"present", "missing"}
            ):
                raise DataError(f"tampered generated workspace reference in {category!r}")
    revision_input = {
        "schema_version": 1,
        "project_id": manifest["project_id"],
        "project_name_sha256": manifest["project_name_sha256"],
        "indexes": descriptors,
        "authority": "none",
        "execution_authority": False,
    }
    if revision_id != f"spw_{_sha256(revision_input)}":
        raise DataError("tampered generated workspace revision content address")
    readme_path = revision_dir / "README.md"
    _reject_symlink(readme_path)
    if not readme_path.is_file():
        raise DataError("tampered generated workspace README")
    try:
        readme = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DataError("tampered generated workspace README") from exc
    if readme != _readme(manifest):
        raise DataError("tampered generated workspace README")
    return manifest


def _current_manifest(
    root: Path, *, expected_project_id: str | None = None
) -> dict[str, object] | None:
    pointer_path = root / "current.json"
    if not pointer_path.exists():
        return None
    pointer = _load_json(pointer_path)
    if set(pointer) != {"schema_name", "schema_version", "revision_id", "manifest_sha256"}:
        raise DataError("tampered generated workspace current pointer")
    revision_id = pointer.get("revision_id")
    if (
        pointer.get("schema_name") != "StrategyProjectWorkspacePointerV1"
        or pointer.get("schema_version") != 1
        or not isinstance(revision_id, str)
        or _REVISION_RE.fullmatch(revision_id) is None
    ):
        raise DataError("tampered generated workspace current pointer")
    manifest_path = root / "revisions" / revision_id / "manifest.json"
    manifest = _validate_revision(manifest_path.parent, expected_project_id=expected_project_id)
    if pointer.get("manifest_sha256") != _file_sha256(manifest_path):
        raise DataError("tampered generated workspace current pointer hash")
    return manifest


def _validate_generated_root(
    root: Path, *, expected_project_id: str | None = None
) -> dict[str, object] | None:
    _reject_symlink(root)
    if not root.exists():
        return None
    if not root.is_dir():
        raise DataError("tampered generated workspace root")
    allowed = {"current.json", "revisions", "quarantine"}
    if not {entry.name for entry in root.iterdir()}.issubset(allowed):
        raise DataError("tampered generated workspace root file set")
    revisions = root / "revisions"
    if revisions.exists():
        _reject_symlink(revisions)
        if not revisions.is_dir():
            raise DataError("tampered generated workspace revisions directory")
        for revision in revisions.iterdir():
            if revision.name.startswith(".") and revision.name.endswith(".tmp"):
                raise DataError("incomplete generated workspace requires explicit recovery")
            _validate_revision(revision, expected_project_id=expected_project_id)
    quarantine = root / "quarantine"
    if quarantine.exists():
        _reject_symlink(quarantine)
        if not quarantine.is_dir():
            raise DataError("tampered generated workspace quarantine")
    current = _current_manifest(root, expected_project_id=expected_project_id)
    if current is None and revisions.exists() and any(revisions.iterdir()):
        raise DataError("generated workspace has no current pointer; run workspace recover")
    return current


def _write_revision(
    root: Path,
    manifest: Mapping[str, object],
    indexes: Mapping[str, Mapping[str, object]],
    readme: str,
) -> Path:
    revisions = root / "revisions"
    revisions.mkdir(parents=True, exist_ok=True)
    revision = revisions / str(manifest["revision_id"])
    if revision.exists():
        existing = _validate_revision(revision, expected_project_id=str(manifest["project_id"]))
        if existing != manifest:
            raise DataError("tampered generated workspace revision conflicts with authority")
        return revision
    temporary = Path(tempfile.mkdtemp(prefix=".workspace-", suffix=".tmp", dir=revisions))
    try:
        (temporary / "indexes").mkdir()
        _write_durable(temporary / "manifest.json", _json_bytes(manifest))
        _write_durable(temporary / "README.md", readme.encode("utf-8"))
        for category in WORKSPACE_CATEGORIES:
            _write_durable(
                temporary / "indexes" / f"{category}.json", _json_bytes(indexes[category])
            )
        _fsync_directory(temporary / "indexes")
        _fsync_directory(temporary)
        _validate_revision(
            temporary,
            expected_revision_id=str(manifest["revision_id"]),
            expected_project_id=str(manifest["project_id"]),
        )
        try:
            os.replace(temporary, revision)
            _fsync_directory(revisions)
        except OSError as exc:
            if (
                revision.exists()
                and _validate_revision(revision, expected_project_id=str(manifest["project_id"]))
                == manifest
            ):
                return revision
            raise DataError("failed to atomically publish strategy workspace revision") from exc
    finally:
        if temporary.exists():
            for path in sorted(temporary.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            temporary.rmdir()
    return revision


def _write_durable(path: Path, payload: bytes) -> None:
    with path.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _pointer_bytes(revision: Path) -> bytes:
    return _json_bytes(
        {
            "schema_name": "StrategyProjectWorkspacePointerV1",
            "schema_version": 1,
            "revision_id": revision.name,
            "manifest_sha256": _file_sha256(revision / "manifest.json"),
        }
    )


def _replace_current_pointer(path: Path, payload: bytes) -> None:
    descriptor, raw_temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _publish_snapshot(
    root: Path,
    manifest: dict[str, object],
    indexes: dict[str, dict[str, object]],
    readme: str,
) -> None:
    revision = _write_revision(root, manifest, indexes, readme)
    try:
        _replace_current_pointer(root / "current.json", _pointer_bytes(revision))
    except OSError as exc:
        raise DataError(
            "workspace pointer publication failed; last valid workspace remains current"
        ) from exc


def sync_project_workspace(
    store: ControlStore, data_dir: Path, project_id: str
) -> dict[str, object]:
    """Publish one deterministic workspace, refusing any generated-state tamper."""
    project = store.get_project(project_id)
    root = workspace_root(data_dir, project)
    try:
        current = _validate_generated_root(root, expected_project_id=project_id)
    except DataError as exc:
        raise DataError(f"{exc}; run `alpha project workspace recover {project_id}`") from exc
    manifest, indexes, readme = _build_snapshot(store, data_dir, project)
    changed = current is None or current["revision_id"] != manifest["revision_id"]
    if changed:
        root.mkdir(parents=True, exist_ok=True)
        _publish_snapshot(root, manifest, indexes, readme)
    return {
        "schema_name": "StrategyProjectWorkspaceProjectionV1",
        "schema_version": 1,
        "project_id": project_id,
        "workspace_root": str(root.relative_to(data_dir)),
        "changed": changed,
        "recovered": False,
        "stale": False,
        "workspace": manifest,
    }


def read_project_workspace(
    store: ControlStore, data_dir: Path, project_id: str
) -> dict[str, object]:
    """Verify and read the current projection, including authority-derived staleness."""
    project = store.get_project(project_id)
    root = workspace_root(data_dir, project)
    try:
        current = _validate_generated_root(root, expected_project_id=project_id)
    except DataError as exc:
        raise DataError(f"{exc}; run `alpha project workspace recover {project_id}`") from exc
    if current is None:
        raise DataError(
            "project workspace is not materialized; run "
            f"`alpha project workspace sync {project_id}`"
        )
    expected, _, _ = _build_snapshot(store, data_dir, project)
    return {
        "schema_name": "StrategyProjectWorkspaceProjectionV1",
        "schema_version": 1,
        "project_id": project_id,
        "workspace_root": str(root.relative_to(data_dir)),
        "changed": False,
        "recovered": False,
        "stale": current["revision_id"] != expected["revision_id"],
        "workspace": current,
    }


def _quarantine(path: Path, quarantine: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if quarantine.is_symlink() or not quarantine.is_dir():
        raise DataError("workspace recovery quarantine must be a real in-root directory")
    destination = quarantine / f"{path.name}--{uuid.uuid4().hex}"
    os.replace(path, destination)
    _fsync_directory(quarantine)


def _prepare_recovery_quarantine(root: Path) -> Path:
    quarantine = root / "quarantine"
    if quarantine.is_symlink() or (quarantine.exists() and not quarantine.is_dir()):
        holding = root / f".invalid-quarantine--{uuid.uuid4().hex}"
        os.replace(quarantine, holding)
        quarantine.mkdir()
        _quarantine(holding, quarantine)
        _fsync_directory(root)
    else:
        quarantine.mkdir(exist_ok=True)
    _reject_symlink(quarantine)
    if not quarantine.is_dir():  # pragma: no cover - guarded above, retained for fail-closed I/O.
        raise DataError("workspace recovery quarantine is not a directory")
    return quarantine


def _prepare_recovery_directory(path: Path, quarantine: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        _quarantine(path, quarantine)
    path.mkdir(exist_ok=True)
    _reject_symlink(path)
    if not path.is_dir():  # pragma: no cover - guarded above, retained for fail-closed I/O.
        raise DataError(f"workspace recovery could not create {path.name!r}")
    _fsync_directory(path.parent)


def recover_project_workspace(
    store: ControlStore, data_dir: Path, project_id: str
) -> dict[str, object]:
    """Quarantine invalid generated state and republish solely from SQLite authority."""
    project = store.get_project(project_id)
    root = workspace_root(data_dir, project)
    root.mkdir(parents=True, exist_ok=True)
    _reject_symlink(root)
    quarantine = _prepare_recovery_quarantine(root)
    for entry in list(root.iterdir()):
        if entry.name not in {"current.json", "revisions", "quarantine"}:
            _quarantine(entry, quarantine)
    revisions = root / "revisions"
    _prepare_recovery_directory(revisions, quarantine)
    pointer = root / "current.json"
    if pointer.exists() or pointer.is_symlink():
        try:
            _current_manifest(root, expected_project_id=project_id)
        except DataError:
            _quarantine(pointer, quarantine)
    for revision in list(revisions.iterdir()):
        try:
            _validate_revision(revision, expected_project_id=project_id)
        except DataError:
            _quarantine(revision, quarantine)
    manifest, indexes, readme = _build_snapshot(store, data_dir, project)
    revision = revisions / str(manifest["revision_id"])
    if revision.exists():
        try:
            existing = _validate_revision(revision, expected_project_id=project_id)
        except DataError:
            _quarantine(revision, quarantine)
        else:
            if existing != manifest:
                _quarantine(revision, quarantine)
    _publish_snapshot(root, manifest, indexes, readme)
    result = read_project_workspace(store, data_dir, project_id)
    result["changed"] = True
    result["recovered"] = True
    return result


def sync_all_project_workspaces(store: ControlStore, data_dir: Path) -> dict[str, object]:
    """Backfill all projects in deterministic project-id order."""
    projects: list[dict[str, object]] = []
    offset = 0
    while True:
        page = store.list_projects(limit=500, offset=offset)
        projects.extend(page)
        if len(page) < 500:
            break
        offset += len(page)
    results = [
        sync_project_workspace(store, data_dir, str(project["project_id"]))
        for project in sorted(projects, key=lambda row: str(row["project_id"]))
    ]
    return {
        "schema_name": "StrategyProjectWorkspaceBatchV1",
        "schema_version": 1,
        "project_count": len(results),
        "projects": results,
    }


__all__ = [
    "WORKSPACE_CATEGORIES",
    "read_project_workspace",
    "recover_project_workspace",
    "sync_all_project_workspaces",
    "sync_project_workspace",
    "workspace_root",
]
