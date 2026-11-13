"""Closed synthetic stock RDLoop launch on the existing retained owner lifecycle."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from alpha_cli._native_loop_admission import SOURCE_SHA256, WORKER, NativeLaunch, _digest
from alpha_cli.native_stock_fixture import (
    StockFixtureRequest,
    stock_fixture_manifest,
    validate_stock_artifacts,
)
from alpha_core import DataError

EVENT = "native_invocation"
SCOPE = "stock_rdloop_fixture_only"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, kw_only=True)
class StockFixtureLaunch(NativeLaunch):
    """No caller argv/operators/provider; runtime selector is measured, not qualified."""

    stock_runtime: Path

    def __post_init__(self) -> None:
        if (
            self.study is not None
            or self.authority is not None
            or self.mode not in {"resume", "cancel", "exhaust", "tamper"}
        ):
            raise DataError("stock launch is a closed synthetic-only profile")
        for path in (self.source, self.stock_runtime):
            if path.is_symlink() or path != path.resolve() or not path.is_dir():
                raise DataError("stock launch requires canonical source/runtime directories")
        object.__setattr__(self, "fingerprint", self.measure())

    def implementation_fingerprints(self) -> dict[str, str | None]:
        app = Path(__file__).parent
        return {
            "code": _digest(
                {
                    name: _sha(app / name)
                    for name in (
                        "_native_stock_launch.py",
                        "native_stock_fixture.py",
                        "_native_fixture_store.py",
                        "native_supervisor.py",
                    )
                }
                | {"worker": stock_fixture_manifest()}
            ),
            "dependency_lock": _sha(self.stock_runtime / "dependencies.lock.txt"),
            "environment": _digest(
                {
                    "python": _sha(self.stock_runtime / "venv/bin/python"),
                    "pyvenv": _sha(self.stock_runtime / "venv/pyvenv.cfg"),
                    "selector": str(self.stock_runtime),
                }
            ),
            "evaluator": _sha(app / "native_stock_fixture.py"),
            "data": None,
        }

    def measure(self) -> str:
        files = {}
        for path in sorted((self.source / "rdagent").rglob("*")):
            if path.is_symlink():
                raise DataError("stock source symlink is unsupported")
            if path.is_file() and "__pycache__" not in path.parts:
                files[str(path.relative_to(self.source))] = _sha(path)
        if _digest(files) != SOURCE_SHA256:
            raise DataError("stock launch requires exact pinned upstream source")
        return _digest(
            {
                "schema": "StockFixtureLaunchV1",
                "scope": SCOPE,
                "source": SOURCE_SHA256,
                "mode": self.mode,
                "implementation": self.implementation_fingerprints(),
                "authority": "none",
            }
        )

    def request(self, admission: dict[str, object] | None) -> StockFixtureRequest:
        if (
            admission is None
            or self.measure() != self.fingerprint
            or admission.get("manifest_sha256") != self.fingerprint
            or admission.get("mode") != self.mode
        ):
            raise DataError("stock launch differs from durable admission")
        keys = {
            "schema",
            "job_id",
            "reservation_id",
            "owner_id",
            "spec_sha256",
            "manifest_sha256",
            "mode",
            "loop_steps",
            "cpu_milliseconds",
        }
        cpu = admission.get("cpu_milliseconds")
        if (
            set(admission) != keys
            or admission["schema"] != "SyntheticNativeAdmissionV1"
            or type(cpu) is not int
            or any(
                type(admission[k]) is not str
                for k in ("job_id", "reservation_id", "owner_id", "spec_sha256")
            )
        ):
            raise DataError("stock durable admission fields are invalid")
        return StockFixtureRequest(
            cast(str, admission["job_id"]),
            cast(str, admission["reservation_id"]),
            cast(str, admission["owner_id"]),
            cast(str, admission["spec_sha256"]),
            stock_fixture_manifest(),
            5,
            2,
            2,
            cpu,
            self.mode,
        )

    def command(self, admission: dict[str, object] | None) -> list[str]:
        payload = json.dumps(self.request(admission).payload(), sort_keys=True, allow_nan=False)
        if len(payload.encode()) > 8192:
            raise DataError("stock admission transport exceeds bound")
        return [
            str(self.stock_runtime / "venv/bin/python"),
            "-I",
            "-B",
            str(WORKER / "stock_fixture_entry.py"),
            str(self.source),
            "supervised",
            payload,
        ]

    def verify_result(self, work: Path, admission: dict[str, object] | None) -> bytes:
        diagnostic = validate_stock_artifacts(work, self.request(admission))
        with (work / "stock-receipt.json").open("rb") as stream:
            raw = stream.read(100_001)
        if len(raw) > 100_000 or hashlib.sha256(raw).hexdigest() != diagnostic["receipt_sha256"]:
            raise DataError("stock receipt exceeds bound")
        return raw


def consume_before_spawn(owner: object) -> None:
    """Atomic whole-invocation consumption; never usage, refund or a new ledger."""
    from alpha_cli._native_fixture_store import _append, _events, _reservation
    from alpha_cli.control_store import ControlStore
    from alpha_cli.native_supervisor import _Owner

    if type(owner) is not _Owner or type(owner.native) is not StockFixtureLaunch:
        raise DataError("stock consumption requires exact retained owner/launch")
    owner.verify()
    store = ControlStore(owner.root)
    if (
        owner.process is not None
        or owner.spawn_attempted
        or owner.native.measure() != owner.native.fingerprint
    ):
        raise DataError("stock invocation already attempted or profile changed")
    with store._transaction(write=True) as c:
        owner.verify()
        if (
            owner.poll_stop()
            or time.monotonic() >= owner.deadline
            or store._active_job_cancellation(c, owner.job_id)
        ):
            raise DataError("stopped owner cannot consume stock invocation")
        events = _events(c, owner.job_id)
        if set(events) != {"native_claim"}:
            raise DataError("stock invocation already consumed; reconnect only")
        claim = events["native_claim"]
        if (
            any(claim.get(k) != v for k, v in owner.claim_fields().items())
            or claim.get("stock_profile_sha256") != owner.native.fingerprint
        ):
            raise DataError("stock invocation owner/profile binding changed")
        reservation = _reservation(c, owner.job_id)
        budget = json.loads(str(reservation["budget_reserved_json"]))
        if any(
            type(budget.get(k)) is not int or budget[k] < v
            for k, v in {
                "rdagent_native_v1_loop_steps": 5,
                "rdagent_native_v1_model_calls": 2,
                "rdagent_native_v1_tool_calls": 2,
                "rdagent_native_v1_cpu_milliseconds": 1,
            }.items()
        ):
            raise DataError("stock invocation exceeds canonical reserved capacity")
        _append(
            c,
            owner.job_id,
            EVENT,
            {k: claim[k] for k in ("schema", "job_id", "reservation_id", "owner_id", "spec_sha256")}
            | {
                "scope": SCOPE,
                "profile_sha256": owner.native.fingerprint,
                "loop_steps": 5,
                "model_calls": 2,
                "tool_calls": 2,
            },
        )
        _events(c, owner.job_id)
