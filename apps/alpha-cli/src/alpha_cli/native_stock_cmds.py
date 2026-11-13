"""Read existing native stock results through the canonical non-admitted CLI group."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from alpha_core import DataError


class StockMode(StrEnum):
    resume = "resume"
    cancel = "cancel"
    exhaust = "exhaust"
    tamper = "tamper"


def _operator_result(report: dict[str, object]) -> tuple[dict[str, object], int]:
    if (
        report.get("schema") != "StockRDLoopInspectionV1"
        or report.get("resume_allowed") is not False
        or report.get("scientific_acceptance") != "not_admitted"
    ):
        raise DataError("native result report contract differs")
    recovery, artifacts = report.get("result_recovery"), report.get("artifact_validation")
    if not isinstance(recovery, dict) or not isinstance(artifacts, dict):
        raise DataError("native result recovery is unavailable")
    state = recovery.get("status")
    if state == "mismatch" or artifacts.get("status") == "invalid":
        status, code = "invalid", 2
    elif state == "verified" and artifacts.get("status") == "current_bytes_validated_only":
        status, code = "completed", 0
    elif state == "unavailable":
        status, code = "unavailable", 3
    else:
        raise DataError("native result recovery status is unsupported")
    result: dict[str, object] = {
        "schema": "NativeStockOperatorResultV1",
        "operation": "recover_native_stock_result",
        "classification": "synthetic_only_unqualified",
        "status": status,
        "reason": recovery.get("reason"),
        "dispatch": report.get("dispatch"),
        "provenance": {
            key: artifacts.get(key)
            for key in (
                "receipt_sha256",
                "trace_sha256",
                "checkpoint_sha256",
            )
        }
        | {"owner_receipt_match": recovery.get("owner_receipt_match")},
        "resume_allowed": False,
        "scientific_acceptance": "not_admitted",
    }
    if status == "completed":
        receipt, trace = artifacts.get("validated_receipt"), artifacts.get("validated_trace")
        if not isinstance(receipt, dict) or not isinstance(trace, dict):
            raise DataError("validated native result values are unavailable")
        result.update(
            {
                "receipt": receipt,
                "result": trace["result"],
                "feedback": {"decision": trace["decision"], "acceptable": trace["acceptable"]},
            }
        )
    return result, code


def native_result_command(
    data_dir: Annotated[Path, typer.Option("--data-dir", help="Existing synthetic fixture root.")],
    job_id: Annotated[UUID, typer.Option("--job-id", help="Existing native job UUID.")],
    profile_source: Annotated[Path, typer.Option("--profile-source", help="Pinned public source.")],
    profile_runtime: Annotated[
        Path, typer.Option("--profile-runtime", help="Existing runtime bundle.")
    ],
    profile_mode: Annotated[
        StockMode, typer.Option("--profile-mode", help="Original selected mode.")
    ],
) -> None:
    """Recover owner-observed synthetic receipt/result; never launch, resume or admit research."""
    from alpha_cli.native_stock_inspect import inspect_run
    from alpha_cli.native_stock_profile import ProfileSelection

    try:
        report = inspect_run(
            data_dir,
            str(job_id),
            profile_selection=ProfileSelection(
                profile_source,
                profile_runtime,
                profile_mode.value,
            ),
        )
        result, code = _operator_result(report)
        encoded = json.dumps(result, sort_keys=True, allow_nan=False)
    except (DataError, OSError, ValueError, TypeError, KeyError, RecursionError):
        # No raw paths, exception/SQL text, prompts, settings or provider fallback.
        code = 3
        encoded = json.dumps(
            {
                "schema": "NativeStockOperatorResultV1",
                "operation": "recover_native_stock_result",
                "classification": "synthetic_only_unqualified",
                "status": "unavailable",
                "reason": "recorded_native_evidence_unavailable_or_invalid",
                "resume_allowed": False,
                "scientific_acceptance": "not_admitted",
            },
            sort_keys=True,
        )
    typer.echo(encoded)
    raise typer.Exit(code)
