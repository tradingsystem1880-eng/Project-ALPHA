"""Audit retained local references; optionally retire unusable, unreferenced discovery entries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alpha_cli.crypto_data_cmds import _bulk_store
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.crypto.contracts import canonical_bytes


def references(
    data_root: Path, manifest_root: Path, candidates: dict[str, str]
) -> dict[str, list[str]]:
    """Fail closed on unreadable local evidence; scan IDs and exact artifact keys."""
    found: dict[str, list[str]] = {ident: [] for ident in candidates}

    def inspect(value: str, source: str) -> None:
        identifiers = set(re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", value))
        for ident, key in candidates.items():
            if (ident in identifiers or key in value) and source not in found[ident]:
                found[ident].append(source)

    def walk_error(error: OSError) -> None:
        raise DataError("reference audit cannot read a local evidence directory") from error

    for directory, children, files in os.walk(data_root, followlinks=False, onerror=walk_error):
        if any((Path(directory) / name).is_symlink() for name in children):
            raise DataError("reference audit cannot silently exclude linked directories")
        children[:] = [
            name
            for name in children
            if not (Path(directory) / name).is_symlink()
            and (Path(directory) / name).resolve() != manifest_root.resolve()
        ]
        for name in files:
            path = Path(directory) / name
            if path.suffix not in {".json", ".db", ".sqlite", ".sqlite3"}:
                continue
            if path.suffix == ".json":
                value = json.loads(path.read_text(encoding="utf-8"))
                inspect(json.dumps(value), str(path.relative_to(data_root)))
            elif path.suffix in {".db", ".sqlite", ".sqlite3"}:
                with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
                    tables = db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                    for (table,) in tables:
                        quoted = '"' + table.replace('"', '""') + '"'
                        for row in db.execute(f"SELECT * FROM {quoted}"):
                            for value in row:
                                if isinstance(value, str):
                                    inspect(value, f"{path.relative_to(data_root)}:{table}")
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="append retirement receipts; never delete artifacts"
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    store = _bulk_store()
    store.verify_readable()
    with store.admission_lock():
        manifests = store.metadata_inventory(include_retired=True)
        candidates = {}
        for manifest in manifests:
            dataset, quality = manifest.get("dataset"), manifest.get("quality")
            if not isinstance(dataset, dict) or not isinstance(quality, dict):
                continue
            reason = None
            if quality.get("state") == "quarantined":
                reason = "inactive_quarantined"
            elif (
                dataset.get("provider") == "defillama"
                and dataset.get("family") == "stablecoin_supply"
                and dataset.get("units") == "usd_circulating_supply"
            ):
                reason = "revoked_units_error"
            ident = str(manifest["manifest_id"])
            if reason is not None and store.retirement(ident) is None:
                candidates[ident] = (manifest, reason)
        refs = references(
            AlphaSettings().data_dir.resolve(),
            store.manifest_root,
            {ident: str(manifest["artifact_key"]) for ident, (manifest, _) in candidates.items()},
        )
        for manifest in manifests:
            parents = manifest.get("input_manifest_ids", [])
            if not isinstance(parents, list) or any(
                not isinstance(parent, str) for parent in parents
            ):
                raise DataError("reference audit encountered invalid manifest lineage")
            for parent in parents:
                if parent in refs:
                    refs[parent].append(f"manifest:{manifest['manifest_id']}")
        entries = []
        for ident, (_, reason) in candidates.items():
            store.verify_manifest(ident)
            entries.append(
                {
                    "manifest_id": ident,
                    "reason": reason,
                    "references": sorted(set(refs[ident])),
                    "eligible": not refs[ident],
                }
            )
        report = {
            "schema_version": 1,
            "items": entries,
            "immutable_artifacts_removed": 0,
            "all_archive_bytes_verified": False,
        }
        payload = canonical_bytes(report)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        # Persist audit before writing any marker; markers bind its exact bytes.
        with args.report.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        digest = hashlib.sha256(payload).hexdigest()
        retired = []
        if args.apply:
            for entry in entries:
                if entry["eligible"]:
                    ident = str(entry["manifest_id"])
                    store.retire_manifest(
                        ident,
                        reason=str(entry["reason"]),
                        audit_sha256=digest,
                        retired_at=datetime.now(UTC),
                    )
                    store.verify_manifest(ident)
                    if store.retirement(ident) is None:
                        raise DataError("retirement receipt was not persisted")
                    retired.append(ident)
        print(
            json.dumps(
                {
                    "audit_sha256": digest,
                    "eligible": sum(bool(entry["eligible"]) for entry in entries),
                    "protected": sum(not entry["eligible"] for entry in entries),
                    "retired": retired,
                    "immutable_artifacts_removed": 0,
                }
            )
        )


if __name__ == "__main__":
    main()
