"""Read-only progress/evidence inspection. No acquisition, owner lock or quota authority."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from alpha_cli._crypto_backfill import (
    BackfillInspectionLimit,
    BackfillWindow,
    Ledger,
    plan_windows,
    split_symbol,
)
from alpha_cli._crypto_backfill_evidence import verify_completed_window
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoFamily
from alpha_data.crypto.storage import CryptoBulkStore
from alpha_data.crypto.verification import (
    DEFAULT_METADATA_READ_BYTES,
    ArtifactVerificationBudget,
    MetadataVerificationBudget,
)


def inspect_backfill(
    *,
    provider: str,
    family: CryptoFamily,
    symbols: Sequence[str],
    quote: str,
    category: str,
    frequency: str,
    start: date,
    end: date,
    ledger_path: Path,
    now: datetime,
    max_ledger_bytes: int,
    max_windows: int,
    max_verify_artifact_bytes: int,
    load_store: Callable[[], CryptoBulkStore],
    max_verify_metadata_bytes: int = DEFAULT_METADATA_READ_BYTES,
) -> dict[str, Any]:
    """Inspect one requested scope without writes or calls; resume remains advisory.

    Limits cover ledger bytes, topology visits, artifact hashes and manifest/retirement JSON.
    Config/identity queries, decoded-object overhead and wall time remain outside the counters.
    No return value authorizes retries, quota use, acquisition or research.
    """
    for limit in (
        max_ledger_bytes,
        max_windows,
        max_verify_artifact_bytes,
        max_verify_metadata_bytes,
    ):
        if type(limit) is not int or limit < 1:
            raise DataError("backfill inspection limits must be positive integers")
    if now.tzinfo is None:
        raise DataError("backfill inspection time must be timezone-aware")
    budget = ArtifactVerificationBudget(max_verify_artifact_bytes)
    metadata_budget = MetadataVerificationBudget(max_verify_metadata_bytes)
    report: dict[str, Any] = {
        "inspection_state": "blocked",
        "reason": None,
        "execution_authority": False,
        "inspection_provider_calls": 0,
        "historical_quota_usage": None,
        "historical_coverage_complete": False,
        "freshness_qualified": False,
        "source_availability_qualified": False,
        "scope": {
            "provider": provider,
            "family": family,
            "category": category,
            "requested_frequency": frequency,
            "quote": quote,
            "symbols": [],
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "ledger_sha256": None,
        "inspected_at": now.isoformat(),
        "windows": [],
        "window_visits": 0,
        "truncated": False,
        "counts": None,
        "ledger_unchanged_at_recheck": None,
        "resume_evidence": "unknown",
        "last_verified_checkpoint": None,
        "next_action": "reconcile_progress_before_resume",
        "limits": {
            "ledger_bytes_per_read": max_ledger_bytes,
            "window_visits": max_windows,
            "artifact_hash_bytes": max_verify_artifact_bytes,
            "manifest_retirement_json_bytes": max_verify_metadata_bytes,
            "metadata_json_nesting": metadata_budget.max_depth,
        },
        "limit_exclusions": [
            "root config (separately bounded to 8192 bytes)",
            "local identity/capacity queries",
            "decoded-object overhead",
            "wall time",
        ],
    }

    def finish(reason: str) -> dict[str, Any]:
        report["reason"] = reason
        report["artifact_bytes_reserved"] = budget.reserved_bytes
        report["artifact_bytes_read"] = budget.bytes_read
        report["artifact_verification_aborted"] = budget.failed
        report["metadata_bytes_reserved"] = metadata_budget.reserved_bytes
        report["metadata_bytes_read"] = metadata_budget.bytes_read
        report["metadata_verification_aborted"] = metadata_budget.failed
        return report

    if not symbols or len(symbols) > max_windows or len(set(symbols)) != len(symbols):
        return finish("INVALID_SYMBOLS_OR_WINDOW_LIMIT")
    report["scope"]["symbols"] = list(symbols)
    try:
        for symbol in symbols:
            split_symbol(symbol, quote=quote)
        roots = plan_windows(
            provider, family, frequency, start=start, end=end, now=now, max_windows=max_windows
        )
        if len(roots) * len(symbols) > max_windows:
            raise BackfillInspectionLimit("requested windows exceed inspection limit")
    except BackfillInspectionLimit:
        report["truncated"] = True
        return finish("WINDOW_LIMIT")
    except (DataError, ValueError, OSError):
        return finish("INVALID_REQUEST")
    try:
        ledger = Ledger.open(
            ledger_path,
            provider=provider,
            family=family,
            category=category,
            frequency=frequency,
            max_bytes=max_ledger_bytes,
        )
    except BackfillInspectionLimit:
        return finish("LEDGER_BYTE_LIMIT")
    except (DataError, OSError, ValueError, RecursionError):
        return finish("LEDGER_UNREADABLE_OR_INVALID")
    report["ledger_sha256"] = ledger.source_sha256
    if ledger.source_sha256 is None:
        return finish("LEDGER_MISSING")

    def visit() -> None:
        if report["window_visits"] >= max_windows:
            raise BackfillInspectionLimit("split traversal exceeds inspection limit")
        report["window_visits"] += 1

    leaves: list[tuple[str, BackfillWindow]] = []
    try:
        for symbol in symbols:
            for window in roots:
                leaves.extend(
                    (symbol, leaf) for leaf in ledger.requested_leaves(symbol, window, visit=visit)
                )
    except BackfillInspectionLimit:
        report["truncated"] = True
        return finish("WINDOW_LIMIT")
    except (DataError, ValueError, RecursionError):
        return finish("TOPOLOGY_OR_ENTRY_INVALID")

    store: CryptoBulkStore | None = None
    storage_failed = False
    blocked = False
    verified: list[dict[str, Any]] = []
    for symbol, window in leaves:
        entry = ledger.entry(f"{symbol}|{window.key}")
        row = {
            "symbol": symbol,
            "start": window.start,
            "end": window.end,
            "period": window.period,
            "manifest_id": None,
            "quality_state": None,
        }
        if entry is None:
            row.update(status="pending_unrecorded", reason="NO_CHECKPOINT_RECORDED")
        elif entry["state"] == "failed":
            row.update(status="recorded_failure", reason="REVIEW_FAILURE_BEFORE_RESUME")
        elif entry["state"] == "done":
            manifest = entry.get("manifest_id")
            if isinstance(manifest, str) and re.fullmatch(r"[0-9a-f]{64}", manifest):
                row["manifest_id"] = manifest
            if budget.failed or metadata_budget.failed:
                blocked = True
                row.update(status="not_checked", reason="PREVIOUS_VERIFICATION_ABORTED")
            else:
                if store is None and not storage_failed:
                    try:
                        store = load_store()
                    except (DataError, OSError, ValueError, RecursionError):
                        storage_failed = True
                if storage_failed:
                    blocked = True
                    row.update(status="unavailable", reason="STORAGE_UNAVAILABLE")
                else:
                    assert store is not None
                    try:
                        verify_completed_window(
                            store,
                            symbol,
                            window,
                            entry,
                            provider=provider,
                            family=family,
                            category=category,
                            frequency=frequency,
                            quote=quote,
                            now=now,
                            budget=budget,
                            metadata_budget=metadata_budget,
                        )
                    except (DataError, OSError, ValueError, RecursionError):
                        blocked = True
                        row.update(
                            status="unverifiable",
                            reason=(
                                "METADATA_UNAVAILABLE_CORRUPT_OR_LIMIT"
                                if metadata_budget.failed
                                else "EVIDENCE_UNAVAILABLE_CORRUPT_OR_LIMIT"
                            ),
                        )
                    else:
                        row.update(
                            status="completed_verified", reason="VERIFIED_RETAINED_COMPLETION"
                        )
                        row["quality_state"] = entry.get("quality_state")
                        verified.append(row)
        else:
            raise AssertionError("requested leaves must not retain split state")
        report["windows"].append(row)
    try:
        current = Ledger.open(
            ledger_path,
            provider=provider,
            family=family,
            category=category,
            frequency=frequency,
            max_bytes=max_ledger_bytes,
        )
        unchanged = current.source_sha256 == ledger.source_sha256
    except (DataError, OSError, ValueError, RecursionError):
        unchanged = False
    report["ledger_unchanged_at_recheck"] = unchanged
    report["counts"] = {
        state: sum(r["status"] == state for r in report["windows"])
        for state in (
            "pending_unrecorded",
            "recorded_failure",
            "completed_verified",
            "unavailable",
            "unverifiable",
            "not_checked",
        )
    }
    if verified:
        report["last_verified_checkpoint"] = max(
            verified, key=lambda r: (r["end"] or r["period"] or "", r["symbol"])
        )
    if not unchanged:
        report["next_action"] = "repeat_inspection_after_progress_change"
        report["resume_evidence"] = "stale"
        return finish("LEDGER_CHANGED_DURING_INSPECTION")
    if blocked:
        report["resume_evidence"] = "blocked"
        report["next_action"] = "reconcile_storage_evidence_and_inspection_limits"
        return finish("RETAINED_EVIDENCE_NOT_VERIFIED")
    report["inspection_state"] = "complete"
    report["resume_evidence"] = "recorded_completions_verified_only"
    report["next_action"] = (
        "review_failures_unrecorded_work_and_existing_admission"
        if report["counts"]["pending_unrecorded"] or report["counts"]["recorded_failure"]
        else "no_unfinished_work_recorded_for_request"
    )
    report["safe_next_command_argv"] = [
        "alpha",
        "crypto-data",
        "backfill",
        provider,
        family,
        "--symbols",
        ",".join(symbols),
        "--quote",
        quote,
        "--category",
        category,
        "--frequency",
        frequency,
        "--start",
        start.isoformat(),
        "--end",
        end.isoformat(),
        "--ledger",
        ledger_path.stem,
        "--max-verify-artifact-bytes",
        str(max_verify_artifact_bytes),
        "--dry-run",
        "--json",
    ]
    return finish("INSPECTION_COMPLETE")
