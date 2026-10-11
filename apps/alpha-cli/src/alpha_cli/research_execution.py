"""Two-operation discovery controller. No agent, candidate search or admission authority."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from types import FrameType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from alpha_cli import _artifacts, _identity, _runner
from alpha_cli.artifact_contract import sha256_file
from alpha_cli.durable_lease import DurableLeaseError, terminate_and_reap
from alpha_cli.research_execution_digest import execution_digest
from alpha_core import DataError
from alpha_validation import walk_forward_splits


class BaselineExecutionPlan(BaseModel):
    """Frozen initial experiment; validation defaults are the existing public CLI defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    schema_version: Literal[1] = 1
    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._/-]{0,39}$")
    snapshot: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    as_of: date
    strategy: Literal["ts_momentum", "rules"] = "ts_momentum"
    rules_spec: str | None = Field(default=None, max_length=1_000_000)
    lookback: int = Field(default=252, ge=2, le=2000)
    skip: int = Field(default=21, ge=0, le=252)
    vol_window: int = Field(default=63, ge=2, le=1000)
    rebalance_every: int = Field(default=21, ge=1, le=252)
    target_vol: float = Field(default=0.15, gt=0, le=1)
    max_leverage: float = Field(default=1, gt=0, le=1)
    fee_bps: float = Field(default=1, ge=0, le=1000)
    slippage_bps: float = Field(default=2, ge=0, le=1000)
    starting_cash: float = Field(default=1_000_000, gt=0)
    train_size: int = Field(default=504, ge=2, le=5000)
    test_size: int = Field(default=63, ge=2, le=1000)
    embargo: int = Field(default=5, ge=0, le=252)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    seconds: int = Field(default=900, ge=30, le=1500)

    @field_validator("rules_spec")
    @classmethod
    def canonical_rules(cls, value: str | None) -> str | None:
        from alpha_strategies.rules import canonical_json, rule_spec_from_json

        if value is None:
            return None
        try:
            return canonical_json(rule_spec_from_json(value))
        except DataError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def paired_rules(self) -> BaselineExecutionPlan:
        if (self.strategy == "rules") != (self.rules_spec is not None):
            raise ValueError("strategy rules requires rules_spec; other strategies forbid it")
        return self


def command_args(
    plan: BaselineExecutionPlan, stage: str, *, rules_file: Path | None = None
) -> list[str]:
    """Closed argv; no model-generated shell, extra flags, owner override or rules mutation."""
    if stage not in {"baseline", "validation"}:
        raise ValueError("unknown execution stage")
    if (plan.rules_spec is not None) != (rules_file is not None):
        raise ValueError("frozen rule plan requires its immutable file")
    args = [sys.executable, "-m", "alpha_cli.main"]
    args += ["backtest", "run"] if stage == "baseline" else ["validate"]
    args += [plan.symbol]
    shared = (
        "strategy",
        "snapshot",
        "as_of",
        "lookback",
        "skip",
        "vol_window",
        "rebalance_every",
        "target_vol",
        "max_leverage",
        "fee_bps",
        "slippage_bps",
        "starting_cash",
    )
    extra = ("train_size", "test_size", "embargo", "seed") if stage == "validation" else ()
    for name in shared + extra:
        args += ["--" + name.replace("_", "-"), str(getattr(plan, name))]
    args += ["--account-type", "CASH", "--no-allow-short", "--periods-per-year", "252"]
    if rules_file is not None and plan.rules_spec is not None:
        args += [
            "--rules-file",
            str(rules_file),
            "--rules-sha256",
            hashlib.sha256(plan.rules_spec.encode("utf-8")).hexdigest(),
        ]
    if stage == "validation":
        args += ["--max-workers", "1"]
    return args


def run_child(
    args: list[str], *, output: Path, seconds: float, data_dir: Path | None = None
) -> dict[str, Any]:
    """Wait for a terminal child outcome; retain logs and reap its isolated process group."""
    started = time.monotonic()
    env = dict(os.environ)
    if data_dir is not None:
        env["ALPHA_DATA_DIR"] = str(data_dir)

    def interrupt(signum: int, frame: FrameType | None) -> None:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        raise KeyboardInterrupt

    with output.open("x", encoding="utf-8") as log:
        previous = signal.signal(signal.SIGTERM, interrupt)
        process = None
        status = "completed"
        try:
            process = subprocess.Popen(
                args, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True
            )
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            status = "timeout"
        except KeyboardInterrupt:
            status = "interrupted"
        finally:
            try:
                if process is not None:
                    terminate_and_reap(process, process_group_id=process.pid)
            finally:
                signal.signal(signal.SIGTERM, previous)
    returncode = process.returncode if process is not None else None
    if status == "completed" and returncode:
        status = "failed"
    return {
        "status": status,
        "returncode": returncode,
        "elapsed_seconds": time.monotonic() - started,
    }


def _publish(path: Path, value: dict[str, Any]) -> None:
    text = json.dumps(value, sort_keys=True, indent=2, allow_nan=False)
    _artifacts.publish_artifact(path, lambda p: p.write_text(text, encoding="utf-8"))


def _collect(
    plan: BaselineExecutionPlan,
    stage: str,
    log: Path,
    data_dir: Path,
    snapshot_hash: str,
    sessions: int,
) -> dict[str, Any]:
    matches = re.findall(r"^.* -> run ([0-9a-f]{16}):", log.read_text(), re.MULTILINE)
    if len(matches) != 1:
        raise DataError("child did not return exactly one terminal run receipt")
    directory = data_dir / "runs" / matches[0]
    bars, _ = _runner.load_bars(
        plan.symbol,
        data_dir=data_dir,
        snapshot_id=plan.snapshot,
        as_of=_runner.parse_as_of(plan.as_of.isoformat()),
    )
    timestamps = [bar.ts for bar in bars]
    if stage == "validation":
        splits = walk_forward_splits(
            len(bars) - 1,
            train_size=plan.train_size,
            test_size=plan.test_size,
            embargo=plan.embargo,
        )
        timestamps = [bars[splits[0].test.start].ts] + [
            bars[k + 1].ts for split in splits for k in split.test
        ]
    digest = execution_digest(
        directory,
        cutoff=plan.as_of.isoformat(),
        expected_sessions=sessions if stage == "baseline" else len(timestamps),
        expected_timestamps=timestamps,
    )
    manifest = _artifacts.read_manifest(directory)
    config = digest["configuration"]
    symbol = manifest.get("symbol", config.get("symbol"))
    expected_command = "backtest_run" if stage == "baseline" else "validate"
    if (
        symbol != plan.symbol
        or digest["snapshot_id"] != plan.snapshot
        or digest["snapshot_hash"] != snapshot_hash
        or digest["command"] != expected_command
    ):
        raise DataError("child evidence identity mismatch")
    for name in (
        "lookback",
        "skip",
        "vol_window",
        "rebalance_every",
        "target_vol",
        "max_leverage",
        "fee_bps",
        "slippage_bps",
        "starting_cash",
    ):
        if config.get(name) != getattr(plan, name):
            raise DataError(f"child configuration mismatch: {name}")
    child_rules = manifest.get("rules_spec") if stage == "validation" else config.get("rules_spec")
    if child_rules != plan.rules_spec:
        raise DataError("child frozen rule specification mismatch")
    if config.get("strategy_name") != plan.strategy:
        raise DataError("child strategy mismatch")
    for name, expected in {
        "account_type": "CASH",
        "allow_short": False,
        "periods_per_year": 252,
    }.items():
        if config.get(name) != expected:
            raise DataError(f"child configuration mismatch: {name}")
    if stage == "validation":
        for name in ("train_size", "test_size", "embargo", "seed"):
            if config.get(name) != getattr(plan, name):
                raise DataError(f"child validation configuration mismatch: {name}")
    if manifest["execution_fingerprint"] != _identity.execution_fingerprint():
        raise DataError("child execution fingerprint mismatch")
    return digest


def _completion(directory: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    _publish(directory / "receipt.json", receipt)
    hashes = {
        p.name: sha256_file(p)
        for p in sorted(directory.iterdir())
        if p.is_file() and p.name != "manifest.json" and not p.name.startswith(".")
    }
    _publish(directory / "manifest.json", {"schema_version": 1, "sha256": hashes})
    return receipt


def execute_plan(plan: BaselineExecutionPlan, *, data_dir: Path) -> dict[str, Any]:
    """One baseline then one validation; interrupted attempts are never automatically retried.

    Ten seconds are withheld from child execution for cleanup/reconciliation. This is a
    dispatch budget, not a hard wall-time guarantee for storage or OS cleanup. Other callers'
    experiments and information access are outside this per-plan controller boundary.
    """
    started = time.monotonic()
    cutoff = plan.as_of.isoformat()
    bars, _ = _runner.load_bars(
        plan.symbol, data_dir=data_dir, snapshot_id=plan.snapshot, as_of=_runner.parse_as_of(cutoff)
    )
    snapshot_hash = _runner.verified_snapshot_hash(data_dir, plan.snapshot)
    assert snapshot_hash is not None
    identity = {
        "plan": plan.model_dump(mode="json"),
        "snapshot_hash": snapshot_hash,
        "execution_fingerprint": _identity.execution_fingerprint(),
        "controller_sha256": sha256_file(Path(__file__)),
        "digest_sha256": sha256_file(Path(execution_digest.__code__.co_filename)),
    }
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    directory = data_dir / "research_executions" / key
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DataError("research execution is already running") from exc
        _publish(directory / "plan.json", identity)
        if plan.rules_spec is not None:
            raw = plan.rules_spec.encode("utf-8")
            _artifacts.publish_artifact(directory / "rules.json", lambda p: p.write_bytes(raw))
        if (directory / "receipt.json").exists():
            receipt: dict[str, Any] = json.loads((directory / "receipt.json").read_text())
            for attempt in receipt["attempts"]:
                if "digest" in attempt:
                    current = _collect(
                        plan,
                        attempt["stage"],
                        directory / attempt["log"],
                        data_dir,
                        snapshot_hash,
                        len(bars),
                    )
                    if current != attempt["digest"]:
                        raise DataError("completed execution evidence changed")
            return _completion(directory, receipt)
        return _execute_locked(plan, data_dir, directory, snapshot_hash, len(bars), started)


def _execute_locked(
    plan: BaselineExecutionPlan,
    data_dir: Path,
    directory: Path,
    snapshot_hash: str,
    sessions: int,
    started: float,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "execution_id": directory.name,
        "admitted": False,
        "status": "completed_evidence",
        "stop_reason": "fixed_measurements_completed",
        "attempts": [],
        "missing_evidence": ["baseline", "validation"],
        "model_calls": 0,
        "candidate_variants": 0,
        "information_boundary": "controller_operations_only; surrounding_agent_not_certified",
        "objective_coverage": "fixed baseline and validation only; no regime or strategy search",
        "receipt": str(directory / "receipt.json"),
    }
    recovering = any(directory.glob("*.attempt.json"))
    for stage in ("baseline", "validation"):
        attempt_path = directory / f"{stage}.attempt.json"
        result_path = directory / f"{stage}.result.json"
        if result_path.exists():
            attempt = json.loads(result_path.read_text())
            if attempt["status"] == "completed":
                current = _collect(
                    plan, stage, directory / attempt["log"], data_dir, snapshot_hash, sessions
                )
                if current != attempt["digest"]:
                    raise DataError("recovered execution evidence changed")
        elif attempt_path.exists():
            receipt["attempts"].append(
                {
                    "stage": stage,
                    "status": "interrupted_unknown",
                    "cleanup": "unverified_after_controller_death",
                }
            )
            receipt.update(
                status="infrastructure_invalid", stop_reason="interrupted_attempt_not_retried"
            )
            break
        elif recovering:
            receipt.update(
                status="infrastructure_invalid", stop_reason="interrupted_budget_not_replenished"
            )
            break
        else:
            remaining = plan.seconds - (time.monotonic() - started) - 10
            if remaining <= 0:
                receipt.update(
                    status="honest_block", stop_reason="budget_reserved_for_reconciliation"
                )
                break
            args = command_args(
                plan,
                stage,
                rules_file=directory / "rules.json" if plan.rules_spec is not None else None,
            )
            _publish(attempt_path, {"stage": stage, "argv": args, "seconds": remaining})
            log = directory / f"{stage}.log"
            try:
                attempt = {
                    "stage": stage,
                    "log": log.name,
                    **run_child(args, output=log, seconds=remaining, data_dir=data_dir),
                }
                if attempt["status"] == "completed":
                    attempt["digest"] = _collect(
                        plan, stage, log, data_dir, snapshot_hash, sessions
                    )
                else:
                    attempt["error_tail"] = log.read_text()[-2000:]
            except (DataError, OSError, ValueError, KeyError, TypeError, DurableLeaseError) as exc:
                attempt = {"stage": stage, "status": "infrastructure_invalid", "error": str(exc)}
                if log.exists():
                    attempt["log"] = log.name
            _publish(result_path, attempt)
        receipt["attempts"].append(attempt)
        if attempt["status"] != "completed":
            receipt.update(
                status="honest_block"
                if attempt["status"] == "failed"
                else "infrastructure_invalid",
                stop_reason=f"{stage}:{attempt['status']}",
            )
            break
        receipt["missing_evidence"].remove(stage)
    if not receipt["missing_evidence"]:
        sources = {a["digest"]["source_fingerprint"] for a in receipt["attempts"]}
        if len(sources) != 1:
            receipt.update(
                status="infrastructure_invalid", stop_reason="baseline_validation_source_mismatch"
            )
    return _completion(directory, receipt)
