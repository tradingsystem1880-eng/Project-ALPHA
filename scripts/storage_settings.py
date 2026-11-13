"""Create or show the retained storage settings for one data root (ADR-0032, ADR-0043).

The owner runs this; it never decides anything itself. Every value about the decision
(who decided, when, the record) is a required argument with no default, so the code path
cannot fabricate an owner approval. Without ``--reserve-gb`` the ADR-0032 default
(the larger of 15% and 100 GB) stays in force.

    uv run python scripts/storage_settings.py show --data-dir /abs/data
    uv run python scripts/storage_settings.py write --data-dir /abs/data \
        --bulk-root /abs/data/bulk \
        --durable-hosting-reference "..." --reserve-gb 10 --advisory-gb 20 \
        --decided-by owner --decided-on 2026-11-14 --decision-record "ADR-0043"

``write`` is a dry run unless ``--apply`` is given. It creates
``<data-dir>/crypto/storage-config.json`` for the Linux ``cloud_root_identity`` backend from the
observed mount identity, or adds the reserve to an existing file that has none. It refuses to
change an existing identity or an existing reserve. Changing the file changes its hash, so a
daily study frozen against the old bytes refuses to start until it is re-drafted (fail loud).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from alpha_cli.crypto_bulk_store import (
    RESERVE_FLOOR_BYTES,
    OwnerStorageReserveV1,
    configured_crypto_bulk_store,
)
from alpha_core import DataError
from alpha_data.crypto.root_identity import inspect_cloud_root

_SCHEMA = "CryptoBulkStorageConfigV1"
_GB = 1_000_000_000


def _path(data_dir: Path) -> Path:
    return data_dir / "crypto" / "storage-config.json"


def _render(config: dict[str, object]) -> str:
    return json.dumps(config, sort_keys=True, indent=2) + "\n"


def _existing(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise DataError("storage settings path is unsafe")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DataError("existing storage settings are not an object")
    return value


def _reserve(args: argparse.Namespace) -> OwnerStorageReserveV1:
    for name in ("decided_by", "decided_on", "decision_record"):
        if getattr(args, name) is None:
            raise DataError(f"--{name.replace('_', '-')} is required with --reserve-gb")
    advisory = args.advisory_gb if args.advisory_gb is not None else args.reserve_gb
    return OwnerStorageReserveV1(
        minimum_free_bytes=round(args.reserve_gb * _GB),
        advisory_free_bytes=round(advisory * _GB),
        decided_by=args.decided_by,
        decided_on=args.decided_on,
        decision_record=args.decision_record,
    )


def _new_config(args: argparse.Namespace, data_dir: Path) -> dict[str, object]:
    if args.bulk_root is None or args.durable_hosting_reference is None:
        raise DataError(
            "a new storage settings file needs --bulk-root and --durable-hosting-reference"
        )
    bulk = Path(args.bulk_root)
    if not bulk.is_absolute():
        raise DataError("--bulk-root must be absolute")
    observed = inspect_cloud_root(bulk)
    return {
        "schema": _SCHEMA,
        "backend": "cloud_root_identity",
        "bulk_root": str(bulk),
        "control_root": str(data_dir),
        "mount_point": str(observed.mount_point),
        "device_id": observed.device_id,
        "owner_uid": observed.owner_uid,
        "filesystem_type": observed.filesystem_type,
        "mount_source": observed.mount_source,
        "durable_hosting_reference": args.durable_hosting_reference,
    }


def _publish(path: Path, rendered: str, *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".storage-config-", suffix=".tmp", dir=path.parent)
    staged = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(staged, path)
        else:
            os.link(staged, path)  # never overwrite a file that appeared meanwhile
    finally:
        staged.unlink(missing_ok=True)


def _show(data_dir: Path) -> int:
    store = configured_crypto_bulk_store(data_dir)
    capacity = store.verify_readable()
    reserve = store.reserve_bytes(capacity)
    print(f"storage settings: {_path(data_dir)}")
    print(f"free: {capacity.free_bytes / _GB:.1f} GB of {capacity.total_bytes / _GB:.1f} GB")
    print(f"reserve: {reserve / _GB:.1f} GB — {store.reserve_source()}")
    advisory = store.low_space_advisory(capacity)
    print(advisory or "advisory: free space is above the owner's low-space threshold (or none set)")
    return 0


def _write(args: argparse.Namespace, data_dir: Path) -> int:
    path = _path(data_dir)
    existing = _existing(path)
    config = dict(existing) if existing is not None else _new_config(args, data_dir)
    if existing is not None and (args.bulk_root or args.durable_hosting_reference):
        raise DataError("storage identity already exists; this tool never changes it")
    if args.reserve_gb is not None:
        if "free_space_reserve" in config:
            raise DataError(
                "a reserve is already recorded; edit it deliberately by hand with a new decision"
            )
        config["free_space_reserve"] = _reserve(args).to_dict()
    rendered = _render(config)
    print(rendered, end="")
    if not args.apply:
        print("# dry run: nothing written; add --apply to write", file=sys.stderr)
        return 0
    _publish(path, rendered, replace=existing is not None)
    _show(data_dir)  # re-reads through the production parser: fails loudly if invalid
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("show", help="print free space, reserve and advisory")
    show.add_argument("--data-dir", required=True)
    write = sub.add_parser("write", help="create settings or add an owner-set reserve")
    write.add_argument("--data-dir", required=True)
    write.add_argument("--bulk-root")
    write.add_argument("--durable-hosting-reference")
    write.add_argument("--reserve-gb", type=float, help=f"floor {RESERVE_FLOOR_BYTES / _GB:.0f}")
    write.add_argument("--advisory-gb", type=float)
    write.add_argument("--decided-by")
    write.add_argument("--decided-on", help="ISO date of the owner's decision")
    write.add_argument("--decision-record", help="where the decision is written down")
    write.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute() or not data_dir.is_dir():
        parser.error("--data-dir must be an existing absolute directory")
    data_dir = data_dir.resolve()
    try:
        return _show(data_dir) if args.command == "show" else _write(args, data_dir)
    except (DataError, OSError, ValueError) as error:
        print(f"storage-settings: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
