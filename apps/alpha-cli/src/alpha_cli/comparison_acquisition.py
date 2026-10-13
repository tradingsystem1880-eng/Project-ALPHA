"""One retained, bounded provider acquisition batch per inspected parent investigation."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from alpha_cli.investigation_case import Case
from alpha_core import DataError


class AcquisitionSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)*$", max_length=40)
    asset_class: Literal["stock", "etf"]
    role: Literal["asset", "market", "sector", "other"]
    currency: Literal["USD"] = "USD"
    venue: Literal["US"] = "US"
    calendar: Literal["XNYS"] = "XNYS"


class AcquisitionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1] = 1
    case_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: Literal["tiingo"] = "tiingo"
    start: date
    end: date
    series: list[AcquisitionSeries] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def bounded(self) -> AcquisitionPlan:
        if not 0 <= (self.end - self.start).days <= 3660:
            raise ValueError("acquisition dates must be ordered and span at most 3660 days")
        if len({item.symbol for item in self.series}) != len(self.series):
            raise ValueError("acquisition symbols must be distinct")
        return self


def _parent(case: Case) -> tuple[dict[str, Any], date, date]:
    context = case.context()
    actions = {r["action"] for r in case.receipts() if r["status"] == "succeeded"}
    if not {"inspect_execution", "inspect_losses"} <= actions:
        raise DataError("inspect execution and losses successfully before acquisition")
    episodes = case.verify()["observations"]["drawdown_episodes"]
    if not episodes:
        raise DataError("no drawdown endpoints requiring comparison acquisition")
    return (
        context,
        min(date.fromisoformat(e["peak"][:10]) for e in episodes),
        max(date.fromisoformat(e["trough"][:10]) for e in episodes),
    )


def draft_acquisition(case: Case, series: list[AcquisitionSeries]) -> AcquisitionPlan:
    """A read-only request draft; does not reserve or dispatch a provider request."""
    context, start, end = _parent(case)
    return AcquisitionPlan(case_id=context["case_id"], start=start, end=end, series=series)


def _scope(case: Case, plan: AcquisitionPlan) -> dict[str, Any]:
    plan = AcquisitionPlan.model_validate_json(plan.model_dump_json())
    context, peak, trough = _parent(case)
    packet = case.verify()
    sessions = packet["observations"]["execution"]["sessions"]
    first = date.fromisoformat(sessions["first"][:10])
    last = date.fromisoformat(sessions["last"][:10])
    if (
        plan.case_id != context["case_id"]
        or not first <= plan.start <= peak
        or not trough <= plan.end <= min(last, date.fromisoformat(context["cutoff"]))
    ):
        raise DataError("acquisition plan must cover parent drawdowns within its run/cutoff")
    return {
        "plan": plan.model_dump(mode="json"),
        "parent_case_id": context["case_id"],
        "reserved_requests": len(plan.series),
        "max_response_bytes": 8 * 1024 * 1024,
        "worker_seconds": 90,
        "required_dates": sorted(
            {
                e[k][:10]
                for e in packet["observations"]["drawdown_episodes"]
                for k in ("peak", "trough")
            }
        ),
        "policy_sha256": _policy_hash(),
    }


def _encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def _hash(value: object) -> str:
    return hashlib.sha256(_encode(value)).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise DataError("acquisition record missing or symlinked")
    with path.open("rb") as source:
        raw = source.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise DataError("acquisition record exceeds 1 MiB")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise DataError("acquisition record must be an object")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    raw = _encode(value)
    if len(raw) > 1024 * 1024:
        raise DataError("acquisition record exceeds 1 MiB")
    with path.open("xb") as sink:
        sink.write(raw)
        sink.flush()
        os.fsync(sink.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _dispatch(root: Path, index: int) -> dict[str, Any]:
    """One closed worker command, bounded lifetime and no model/provider fallback."""
    import subprocess
    import sys

    from alpha_cli.durable_lease import terminate_and_reap

    home, temporary = root / "worker-home", root / "worker-tmp"
    home.mkdir(exist_ok=True)
    temporary.mkdir(exist_ok=True)
    if home.is_symlink() or temporary.is_symlink():
        raise DataError("acquisition worker directories cannot be symlinked")
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(home),
        "TMPDIR": str(temporary),
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "POLARS_MAX_THREADS": "2",
        "ALPHA_TIINGO_API_KEY": os.environ.get("ALPHA_TIINGO_API_KEY", ""),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "alpha_cli.comparison_acquisition_worker", str(root), str(index)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
        cwd=root,
        start_new_session=True,
    )
    try:
        process.wait(timeout=90)
    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "error_type": "TimeoutExpired",
            "message": "worker deadline exceeded",
        }
    finally:
        terminate_and_reap(process, process_group_id=process.pid)
    path = root / f"attempt-{index}.json"
    if process.returncode != 0 or not path.is_file():
        return {
            "status": "failed",
            "error_type": "WorkerFailed",
            "message": "worker did not publish a terminal receipt",
        }
    return _read(path)


def acquire_comparisons(case: Case, plan: AcquisitionPlan) -> dict[str, Any]:
    """Reserve one batch permanently, retain failures, and verify completed cached evidence."""
    from alpha_cli.comparison_acquisition_evidence import finish_batch, verify_batch

    scope = _scope(case, plan)
    root = case.path / "comparison-acquisition"
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise DataError("acquisition root cannot be symlinked")
    if root.exists():
        if _read(root / "request.json") != scope:
            raise DataError("acquisition request differs from reserved parent batch")
        if not (root / "result.json").is_file():
            raise DataError(
                "acquisition batch is incomplete or ambiguous; requests cannot be retried"
            )
        return verify_batch(root, scope)
    if not os.environ.get("ALPHA_TIINGO_API_KEY", "").strip():
        raise DataError("Tiingo requires process-injected ALPHA_TIINGO_API_KEY")
    try:
        root.mkdir()
    except FileExistsError as exc:
        raise DataError("acquisition batch already reserved by another process") from exc
    descriptor = os.open(root.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _write(root / "request.json", scope)
    attempts = []
    for index in range(len(plan.series)):
        try:
            attempt = _dispatch(root, index)
        except (DataError, OSError, ValueError) as exc:
            attempt = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "message": "acquisition worker failed",
            }
        if attempt.get("status") not in {"succeeded", "failed"}:
            raise DataError("invalid acquisition worker outcome")
        path = root / f"attempt-{index}.json"
        if path.exists():
            if _read(path) != attempt:
                raise DataError("acquisition worker receipt conflicts with controller")
        else:
            _write(path, attempt)
        attempts.append(attempt)
    return finish_batch(root, scope, attempts)


def _policy_hash() -> str:
    from alpha_cli import comparison_acquisition_evidence, comparison_acquisition_worker
    from alpha_data import pipeline, snapshot
    from alpha_data.adapters import tiingo_adapter

    return _hash(
        {
            module.__name__: hashlib.sha256(Path(str(module.__file__)).read_bytes()).hexdigest()
            for module in (
                comparison_acquisition_evidence,
                comparison_acquisition_worker,
                pipeline,
                snapshot,
                tiingo_adapter,
            )
        }
        | {__name__: hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    )
