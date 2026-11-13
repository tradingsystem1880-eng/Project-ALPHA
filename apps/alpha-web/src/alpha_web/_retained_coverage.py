"""Closed CLI relay retaining diagnostic exit-one reports; never execute data code here."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import ValidationError

from alpha_web import _catalog
from alpha_web.api.retained_coverage_models import RetainedCoverageRequest, RetainedCoverageResponse


def retained_coverage(
    manifest_id: str, request: RetainedCoverageRequest, *, data_dir: Path
) -> RetainedCoverageResponse:
    args = ["crypto-data", "quality", manifest_id, "--json"]
    for name, value in request.model_dump(mode="json").items():
        args.extend(["--" + name.replace("_", "-"), str(value)])
    try:
        process = subprocess.run(
            _catalog._command(args),
            capture_output=True,
            text=True,
            env=_catalog._cli_environment(data_dir, args),
            timeout=_catalog.DEFAULT_TIMEOUT_SECONDS,
        )
        if process.returncode not in {0, 1}:
            raise ValueError("unexpected CLI status")
        raw = json.loads(process.stdout)
        if not isinstance(raw, dict) or raw.get("manifest_id") != manifest_id:
            raise ValueError("unexpected CLI identity")
        # This public projection is intentionally a typed subset of the CLI receipt.
        projected = {
            name: raw[name] for name in RetainedCoverageResponse.model_fields if name in raw
        }
        projected.setdefault("row_audit", None)
        projected.setdefault("stored_quality", None)
        projected.setdefault("limits", None)
        report = RetainedCoverageResponse.model_validate(projected)
        rows = report.row_audit
        if rows is not None and (
            rows.start != request.coverage_start
            or rows.end_exclusive != request.coverage_end
            or rows.as_of != request.as_of
            or rows.cadence_seconds != request.expected_cadence_seconds
        ):
            raise ValueError("CLI grid and request differ")
        success = report.row_audit is not None and report.row_audit.declared_grid_satisfied
        if (process.returncode == 0) != success:
            raise ValueError("CLI exit and diagnostic outcome differ")
        return report
    except (OSError, subprocess.SubprocessError, ValueError, ValidationError):
        # Never forward stdout/stderr/exception context or unvalidated CLI JSON to the browser.
        raise RuntimeError("RETAINED_COVERAGE_RELAY_UNAVAILABLE") from None
