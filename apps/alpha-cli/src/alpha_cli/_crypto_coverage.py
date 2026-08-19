"""Immutable coverage-batch persistence for the crypto CLI."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from alpha_core import DataError
from alpha_data.crypto.profiles import (
    CoverageCadence,
    CryptoCoverageProfileV1,
    CryptoCoverageTaskV1,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def batch_digest(body: dict[str, object]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def batch_directory(root: Path, batch_id: str) -> Path:
    if _SHA256.fullmatch(batch_id) is None:
        raise DataError("crypto coverage-batch id is invalid")
    return root / batch_id


def write_batch_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def create_coverage_batch(
    root: Path,
    profile: CryptoCoverageProfileV1,
    *,
    cadence: CoverageCadence,
    offset: int,
    limit: int,
    run_at: datetime,
) -> tuple[str, dict[str, object]]:
    selected = tuple(task for task in profile.tasks if task.cadence == cadence)[
        offset : offset + limit
    ]
    if not selected:
        raise DataError("crypto coverage batch selection is empty")
    body: dict[str, object] = {
        "schema_version": 1,
        "profile_id": profile.profile_id,
        "cadence": cadence,
        "profile_offset": offset,
        "run_at": run_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "tasks": [task.to_dict() for task in selected],
        "execution_authority": False,
    }
    batch_id = batch_digest(body)
    batch_root = batch_directory(root, batch_id)
    plan = {**body, "batch_id": batch_id}
    plan_path = batch_root / "plan.json"
    if plan_path.exists():
        try:
            existing = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DataError("crypto coverage-batch plan is unreadable") from exc
        if existing != plan:
            raise DataError("crypto coverage-batch identity collision")
    else:
        write_batch_json(plan_path, plan)
    checkpoint_path = batch_root / "checkpoint.json"
    if not checkpoint_path.exists():
        write_batch_json(
            checkpoint_path,
            {
                "schema_version": 1,
                "batch_id": batch_id,
                "next_index": 0,
                "results": [],
                "results_sha256": batch_digest({"results": []}),
                "state": "running",
                "error": None,
                "updated_at": run_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "execution_authority": False,
            },
        )
    return batch_id, plan


def read_coverage_batch(root: Path, batch_id: str) -> tuple[dict[str, object], dict[str, object]]:
    batch_root = batch_directory(root, batch_id)
    try:
        plan = json.loads((batch_root / "plan.json").read_text(encoding="utf-8"))
        checkpoint = json.loads((batch_root / "checkpoint.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("crypto coverage batch is unavailable or corrupt") from exc
    if not isinstance(plan, dict) or plan.get("batch_id") != batch_id:
        raise DataError("crypto coverage-batch plan identity is invalid")
    body = {key: value for key, value in plan.items() if key != "batch_id"}
    if (
        set(body)
        != {
            "schema_version",
            "profile_id",
            "cadence",
            "profile_offset",
            "run_at",
            "tasks",
            "execution_authority",
        }
        or body.get("schema_version") != 1
        or body.get("execution_authority") is not False
        or batch_digest(body) != batch_id
        or not isinstance(body.get("tasks"), list)
    ):
        raise DataError("crypto coverage-batch plan integrity failure")
    tasks = tuple(
        CryptoCoverageTaskV1.from_dict(item) for item in cast(list[object], body["tasks"])
    )
    if not tasks or len(tasks) > 25:
        raise DataError("crypto coverage-batch task membership is invalid")
    if not isinstance(checkpoint, dict) or set(checkpoint) != {
        "schema_version",
        "batch_id",
        "next_index",
        "results",
        "results_sha256",
        "state",
        "error",
        "updated_at",
        "execution_authority",
    }:
        raise DataError("crypto coverage-batch checkpoint is invalid")
    results = checkpoint.get("results")
    next_index = checkpoint.get("next_index")
    if (
        checkpoint.get("schema_version") != 1
        or checkpoint.get("batch_id") != batch_id
        or checkpoint.get("execution_authority") is not False
        or checkpoint.get("state") not in {"running", "failed", "completed"}
        or not isinstance(results, list)
        or checkpoint.get("results_sha256") != batch_digest({"results": results})
        or not isinstance(next_index, int)
        or isinstance(next_index, bool)
        or next_index != len(results)
        or not 0 <= next_index <= len(tasks)
        or (checkpoint.get("state") == "completed") != (next_index == len(tasks))
        or (checkpoint.get("state") == "failed") != isinstance(checkpoint.get("error"), str)
        or any(
            not isinstance(result, dict)
            or result.get("task_id") != tasks[index].task_id
            or _SHA256.fullmatch(str(result.get("normalized_manifest_id"))) is None
            for index, result in enumerate(results)
        )
    ):
        raise DataError("crypto coverage-batch checkpoint integrity failure")
    return plan, checkpoint
