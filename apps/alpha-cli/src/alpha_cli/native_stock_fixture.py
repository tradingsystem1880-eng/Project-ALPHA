"""Bounded stock RDLoop diagnostic contracts; no execution or evidence authority."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from alpha_core import DataError

if TYPE_CHECKING:
    from alpha_cli.control_store import ControlStore
    from alpha_cli.native_supervisor import _Owner

SOURCE_SHA256 = "0266b2d63328f88fcaf6f239bf6d67f29c896b8161566f794ef69465b7788707"
STAGES = ["direct_exp_gen", "coding", "running", "feedback", "record"]
RESULT = {"synthetic_score": -0.125, "unit": "fixture_only"}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class StockFixtureRequest:
    job_id: str
    reservation_id: str
    owner_id: str
    spec_sha256: str
    manifest_sha256: str
    loop_steps: int
    model_calls: int
    tool_calls: int
    cpu_milliseconds: int
    mode: str = "resume"

    def __post_init__(self) -> None:
        if any(
            type(v) is not int or not 0 < v <= 60_000
            for v in (self.loop_steps, self.model_calls, self.tool_calls, self.cpu_milliseconds)
        ) or (self.loop_steps, self.model_calls, self.tool_calls) != (5, 2, 2):
            raise DataError(
                "stock fixture requires exactly five stages/two fake model/two fake tool attempts"
            )
        if self.mode not in {"resume", "cancel", "exhaust", "tamper"}:
            raise DataError("unsupported closed stock fixture mode")
        if any(
            type(v) is not str or not v or len(v) > 200
            for v in (self.job_id, self.reservation_id, self.owner_id)
        ):
            raise DataError("stock fixture identity is missing")
        if any(
            len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
            for v in (self.spec_sha256, self.manifest_sha256)
        ):
            raise DataError("stock fixture fingerprints are invalid")

    def payload(self) -> dict[str, object]:
        return {"schema": "StockRDLoopFixtureRequestV1", **asdict(self)}


def stock_fixture_manifest() -> str:
    worker = Path(__file__).resolve().parents[4] / "workers/rdagent"
    return digest(
        {
            name: hashlib.sha256((worker / name).read_bytes()).hexdigest()
            for name in ("stock_fixture.py", "stock_fixture_entry.py", "source_pin.py")
        }
    )


def request_from_owner(
    store: ControlStore, job_id: str, owner: _Owner, *, manifest_sha256: str, mode: str = "resume"
) -> StockFixtureRequest:
    """Read existing claim/reservation; this reference cannot launch or settle a job."""
    import time

    from alpha_cli._native_fixture_store import _events, _reservation
    from alpha_cli.native_supervisor import _Owner

    if manifest_sha256 != stock_fixture_manifest():
        raise DataError("stock fixture code identity changed")
    if type(owner) is not _Owner:
        raise DataError("stock diagnostic requires exact retained synthetic owner")
    owner.verify()
    if (
        owner.root != store._data_dir
        or owner.job_id != job_id
        or owner.fixture != "success"
        or owner.native is not None
        or owner.process is not None
        or owner.spawn_attempted
        or owner.stop_reason is not None
        or time.monotonic() >= owner.deadline
    ):
        raise DataError("stock fixture owner is not eligible")
    with store._transaction(write=False) as c:
        claim = _events(c, job_id).get("native_claim")
        reservation = _reservation(c, job_id)
        request = json.loads(store._require_job(c, job_id)["request_json"])
        spec = request["native_invocation_spec"]
        if (
            claim is None
            or any(claim.get(k) != v for k, v in owner.claim_fields().items())
            or store._active_job_cancellation(c, job_id)
        ):
            raise DataError("stock fixture claim/cancellation binding is invalid")
        if (
            spec["native_manifest_sha256"] != manifest_sha256
            or spec["implementation_fingerprints"]["evaluator"] != manifest_sha256
        ):
            raise DataError("stock fixture differs from approved manifest/evaluator")
        budget = json.loads(reservation["budget_reserved_json"])
        if any(
            type(budget.get(k)) is not int or budget[k] < v
            for k, v in {
                "rdagent_native_v1_loop_steps": 5,
                "rdagent_native_v1_model_calls": 2,
                "rdagent_native_v1_tool_calls": 2,
                "rdagent_native_v1_cpu_milliseconds": 1,
            }.items()
        ):
            raise DataError("canonical reservation is insufficient for closed stock fixture")
        return StockFixtureRequest(
            job_id,
            str(reservation["reservation_id"]),
            owner.owner_id,
            str(reservation["config_fingerprint"]),
            manifest_sha256,
            5,
            2,
            2,
            min(60_000, budget["rdagent_native_v1_cpu_milliseconds"]),
            mode,
        )


def _read(work: Path, name: str, cap: int) -> bytes:
    path = work / name
    if work.is_symlink() or path.is_symlink() or not path.is_file():
        raise DataError("stock fixture artifact is missing or unsafe")
    with path.open("rb") as stream:
        raw = stream.read(cap + 1)
    if len(raw) > cap:
        raise DataError("stock fixture artifact exceeds fixed bound")
    return raw


def validate_stock_artifacts(work: Path, request: StockFixtureRequest) -> dict[str, object]:
    """Read each bounded artifact once, then validate/hash those exact byte snapshots."""
    return validate_stock_snapshot(
        {name: _read(work, name, cap) for name, cap in ARTIFACT_LIMITS}, request
    )


ARTIFACT_LIMITS = (
    ("stock-receipt.json", 100_000),
    ("stock-trace.json", 8_192),
    ("stock-checkpoint.bin", 1_048_576),
)


def validate_stock_snapshot(
    artifacts: Mapping[str, bytes], request: StockFixtureRequest
) -> dict[str, object]:
    """Validate current immutable bytes only; not owner admission or resume authority."""
    artifacts = dict(artifacts)
    if set(artifacts) != {name for name, _ in ARTIFACT_LIMITS} or any(
        type(artifacts[name]) is not bytes or len(artifacts[name]) > cap
        for name, cap in ARTIFACT_LIMITS
    ):
        raise DataError("stock artifact snapshot fields/types/bounds are invalid")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for k, v in items:
            if k in result:
                raise DataError("duplicate stock artifact JSON key")
            result[k] = v
        return result

    raw = artifacts["stock-receipt.json"]
    try:
        receipt = json.loads(raw, object_pairs_hook=pairs)
        trace = json.loads(artifacts["stock-trace.json"], object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise DataError("invalid stock fixture JSON") from exc
    expected_trace = {
        "schema": "StockRDLoopTraceV1",
        "request_sha256": digest(request.payload()),
        "native_class": "rdagent.components.workflow.rd_loop.RDLoop",
        "stages": STAGES,
        "hist_count": 1,
        "dag_parent": [[]],
        "idx2loop_id": {"0": 0},
        "hypothesis": "fixed synthetic stock hypothesis",
        "result": RESULT,
        "decision": False,
        "acceptable": False,
        "scientific_acceptance": "not_admitted",
    }
    try:
        valid_trace = digest(trace) == digest(expected_trace)
    except (ValueError, TypeError, RecursionError) as exc:
        raise DataError("stock trace is not finite canonical JSON") from exc
    if not valid_trace or request.mode != "resume":
        raise DataError("stock trace is not the exact unaccepted synthetic result")
    expected = {
        "schema": "StockRDLoopReceiptV1",
        "request": request.payload(),
        "source_sha256": SOURCE_SHA256,
        "trace_sha256": hashlib.sha256(artifacts["stock-trace.json"]).hexdigest(),
        "checkpoint_sha256": hashlib.sha256(artifacts["stock-checkpoint.bin"]).hexdigest(),
        "charged_stages": STAGES,
        "fake_model_attempts": 2,
        "fake_tool_attempts": 2,
        "actual_model_calls": 0,
        "resumed_without_repeating": True,
        "checkpoint_unchanged": True,
        "replay_rejected": True,
        "routes_enabled": False,
        "scientific_acceptance": "not_admitted",
    }
    try:
        valid_receipt = digest(receipt) == digest(expected)
    except (ValueError, TypeError, RecursionError) as exc:
        raise DataError("stock receipt is not finite canonical JSON") from exc
    if not valid_receipt:
        raise DataError("stock receipt differs from exact request/artifact bindings")
    return {
        "schema": "StockRDLoopDiagnosticV1",
        "classification": "synthetic_only",
        "trace": trace,
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "scientific_acceptance": "not_admitted",
        "production_dispatch": False,
        "reservation": "retained_full; no settlement or refund",
    }
