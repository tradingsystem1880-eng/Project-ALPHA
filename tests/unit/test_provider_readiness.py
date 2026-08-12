"""Provider readiness separates local configuration from explicit verification."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from alpha_cli import provider_readiness


def test_receipt_is_redacted_content_addressed_and_drives_status(tmp_path: Path) -> None:
    secret = "never-store-this-provider-secret"
    receipt = provider_readiness.record_check_receipt(
        tmp_path,
        provider_id="tiingo",
        verification_state="verified",
        granted_capabilities=("historical_bars", "corporate_actions"),
        checked_at=datetime(2026, 8, 13, tzinfo=UTC),
        recovery_action="No action required.",
        details={"symbol": "SPY", "rows": 5, "unsafe": secret},
    )

    assert receipt["schema_version"] == 1
    assert receipt["receipt_id"] == receipt["content_sha256"]
    stored = list((tmp_path / "provider-checks" / "tiingo").glob("*.json"))
    assert len(stored) == 1
    assert secret not in stored[0].read_text(encoding="utf-8")
    assert "unsafe" not in json.loads(stored[0].read_text(encoding="utf-8"))["details"]

    status = provider_readiness.last_check_status(tmp_path, "tiingo")
    assert status["verification_state"] == "verified"
    assert status["verified_at"] == "2026-08-13T00:00:00Z"
    assert status["granted_capabilities"] == ["corporate_actions", "historical_bars"]


def test_missing_receipt_is_unverified_and_tamper_fails_closed(tmp_path: Path) -> None:
    assert provider_readiness.last_check_status(tmp_path, "quantpad") == {
        "verification_state": "unverified",
        "verified_at": None,
        "last_receipt_id": None,
        "granted_capabilities": [],
        "recovery_action": "Run an explicit provider check from the Readiness Center.",
    }

    receipt = provider_readiness.record_check_receipt(
        tmp_path,
        provider_id="quantpad",
        verification_state="authentication_failed",
        granted_capabilities=(),
        checked_at=datetime(2026, 8, 13, tzinfo=UTC),
        recovery_action="Rotate the REST key, reinject it, and run one new explicit check.",
        details={"interface": "rest"},
    )
    path = tmp_path / "provider-checks" / "quantpad" / f"{receipt['receipt_id']}.json"
    path.write_text(path.read_text(encoding="utf-8").replace("rest", "oauth"), encoding="utf-8")
    status = provider_readiness.last_check_status(tmp_path, "quantpad")
    assert status["verification_state"] == "schema_drift"
    assert status["granted_capabilities"] == []


def test_classifies_provider_failures_without_raw_vendor_body() -> None:
    assert provider_readiness.classify_failure(401, "anything") == "authentication_failed"
    assert provider_readiness.classify_failure(403, "anything") == "entitlement_denied"
    assert provider_readiness.classify_failure(429, "anything") == "rate_limited"
    assert provider_readiness.classify_failure(None, "timeout") == "connectivity_failed"
    assert provider_readiness.classify_failure(200, "schema") == "schema_drift"
