"""Provider readiness separates local configuration from explicit verification."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self, cast

import pytest

from alpha_cli import ibkr_what_if, paper_acceptance, provider_readiness
from alpha_core import DataError


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


def test_reachable_ibkr_gateway_stays_unverified_without_broker_callbacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0})(),
    )

    class Connection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: Connection(),
    )
    monkeypatch.setenv(
        "ALPHA_IBKR_GATEWAY_IMAGE",
        "gateway:latest@sha256:" + "a" * 64,
    )
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ACCOUNT", "DU123456")

    receipt = provider_readiness.run_explicit_check(tmp_path, "ibkr")

    assert receipt["verification_state"] == "unverified"
    assert receipt["granted_capabilities"] == []
    details = cast(dict[str, object], receipt["details"])
    assert details["account_alias"] == "DU…3456"


def test_signed_local_ibkr_gateway_is_a_reviewed_installation_without_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Connection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: Connection())
    monkeypatch.setenv("ALPHA_IBKR_GATEWAY_APP", "/Applications/IB Gateway.app")
    monkeypatch.setattr(provider_readiness, "_signed_local_ibkr_gateway", lambda _: True)

    receipt = provider_readiness.run_explicit_check(tmp_path, "ibkr")

    assert receipt["verification_state"] == "unverified"
    details = cast(dict[str, object], receipt["details"])
    assert details["signed_local_app_reviewed"] is True
    assert details["gateway_reachable"] is True
    assert details["docker_cli"] is False


def test_ibkr_verified_what_if_receipt_grants_only_preview_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: type("Result", (), {"returncode": 0})()
    )

    class Connection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: Connection())
    monkeypatch.setenv("ALPHA_IBKR_GATEWAY_IMAGE", "gateway@sha256:" + "a" * 64)
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ACCOUNT", "DU123456")
    now = datetime(2026, 8, 13, tzinfo=UTC)
    plan = paper_acceptance.create_ibkr_what_if_plan(
        tmp_path,
        account_id="DU123456",
        gateway_image="gateway@sha256:" + "a" * 64,
        limit_price=640.0,
        collar_low=600.0,
        collar_high=680.0,
        expires_at=datetime(2026, 8, 14, tzinfo=UTC),
        now=now,
    )

    class Transport:
        def preview(self, **kwargs: object) -> ibkr_what_if.PreviewEvidence:
            return ibkr_what_if.PreviewEvidence(
                broker_status="PreSubmitted",
                commission=1.0,
                commission_currency="USD",
                initial_margin_change="640",
                maintenance_margin_change="0",
                equity_with_loan_change="-640",
                position_before=0.0,
                position_after=0.0,
                order_status_callbacks=0,
                execution_callbacks=0,
            )

    ibkr_what_if.execute_preview(
        tmp_path,
        plan_hash=str(plan["plan_hash"]),
        account_id="DU123456",
        transport=Transport(),
        now=datetime(2026, 8, 13, 1, tzinfo=UTC),
    )

    receipt = provider_readiness.run_explicit_check(tmp_path, "ibkr")
    assert receipt["verification_state"] == "verified"
    assert receipt["granted_capabilities"] == ["paper_what_if_preview"]
    details = cast(dict[str, object], receipt["details"])
    assert details["permissions"] == "what_if_preview_verified"
    assert details["market_data"] == "not_verified_by_what_if"


@pytest.mark.parametrize(
    ("provider", "state", "checked_at", "message"),
    [
        ("bad provider", "verified", datetime(2026, 8, 13, tzinfo=UTC), "provider id"),
        ("tiingo", "future", datetime(2026, 8, 13, tzinfo=UTC), "verification state"),
        ("tiingo", "verified", datetime(2026, 8, 13), "timezone-aware"),
    ],
)
def test_receipt_rejects_invalid_identity_state_and_time(
    tmp_path: Path,
    provider: str,
    state: str,
    checked_at: datetime,
    message: str,
) -> None:
    with pytest.raises(DataError, match=message):
        provider_readiness.record_check_receipt(
            tmp_path,
            provider_id=provider,
            verification_state=cast(Any, state),
            granted_capabilities=(),
            checked_at=checked_at,
            recovery_action="recover",
            details={},
        )


def test_receipt_collision_and_malformed_receipts_fail_closed(tmp_path: Path) -> None:
    receipt = provider_readiness.record_check_receipt(
        tmp_path,
        provider_id="tiingo",
        verification_state="verified",
        granted_capabilities=("historical_bars",),
        checked_at=datetime(2026, 8, 13, tzinfo=UTC),
        recovery_action="none",
        details={"interface": "rest"},
    )
    path = tmp_path / "provider-checks" / "tiingo" / f"{receipt['receipt_id']}.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="identity collision"):
        provider_readiness.record_check_receipt(
            tmp_path,
            provider_id="tiingo",
            verification_state="verified",
            granted_capabilities=("historical_bars",),
            checked_at=datetime(2026, 8, 13, tzinfo=UTC),
            recovery_action="none",
            details={"interface": "rest"},
        )
    assert (
        provider_readiness.last_check_status(tmp_path, "tiingo")["verification_state"]
        == "schema_drift"
    )


@pytest.mark.parametrize(
    ("exc", "state"),
    [
        (DataError("HTTP 401"), "authentication_failed"),
        (DataError("error 403"), "entitlement_denied"),
        (DataError("HTTP 429"), "rate_limited"),
        (DataError("transport failed"), "connectivity_failed"),
        (DataError("unexpected payload"), "schema_drift"),
    ],
)
def test_explicit_check_redacts_vendor_errors_into_typed_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
    state: str,
) -> None:
    def failed_check() -> tuple[tuple[str, ...], dict[str, object]]:
        raise exc

    checkers = cast(dict[str, object], provider_readiness.__dict__["_CHECKERS"])
    monkeypatch.setitem(checkers, "tiingo", failed_check)
    receipt = provider_readiness.run_explicit_check(tmp_path, "tiingo")
    assert receipt["verification_state"] == state
    assert str(exc) not in json.dumps(receipt)


def test_explicit_check_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="supported providers"):
        provider_readiness.run_explicit_check(tmp_path, "unknown")


def test_coingecko_check_receipt_never_contains_injected_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "coingecko-secret-sentinel"
    monkeypatch.setenv("ALPHA_COINGECKO_API_KEY", secret)
    monkeypatch.setattr(
        provider_readiness,
        "fetch_coingecko_demo",
        lambda *_args, **_kwargs: b'{"gecko_says":"(V3) To the Moon!"}',
    )

    receipt = provider_readiness.run_explicit_check(tmp_path, "coingecko")

    assert receipt["verification_state"] == "verified"
    assert receipt["granted_capabilities"] == ["asset_metadata", "market_reference"]
    assert secret not in json.dumps(receipt)


def test_ibkr_missing_local_prerequisites_are_connectivity_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    def closed(*args: object, **kwargs: object) -> None:
        raise OSError("closed")

    monkeypatch.setattr(socket, "create_connection", closed)
    receipt = provider_readiness.run_explicit_check(tmp_path, "ibkr")
    assert receipt["verification_state"] == "connectivity_failed"
    assert receipt["granted_capabilities"] == []


def test_empty_and_malformed_receipt_directories_never_imply_readiness(tmp_path: Path) -> None:
    root = tmp_path / "provider-checks" / "tiingo"
    root.mkdir(parents=True)
    assert (
        provider_readiness.last_check_status(tmp_path, "tiingo")["verification_state"]
        == "unverified"
    )
    (root / "broken.json").write_text("not-json", encoding="utf-8")
    assert (
        provider_readiness.last_check_status(tmp_path, "tiingo")["verification_state"]
        == "schema_drift"
    )


def test_receipt_verifier_rejects_non_objects_and_cross_provider_replay(tmp_path: Path) -> None:
    verify = cast(
        Callable[[object, str], dict[str, object] | None],
        provider_readiness.__dict__["_verify_receipt"],
    )
    assert verify([], "tiingo") is None
    receipt = provider_readiness.record_check_receipt(
        tmp_path,
        provider_id="tiingo",
        verification_state="verified",
        granted_capabilities=(),
        checked_at=datetime(2026, 8, 13, tzinfo=UTC),
        recovery_action="none",
        details={},
    )
    assert verify(receipt, "quantpad") is None


def test_bounded_tiingo_and_quantpad_checks_grant_only_their_capabilities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Bars:
        height = 7

    class Result:
        bars = Bars()

    class Adapter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def fetch(self, *args: object, **kwargs: object) -> Result:
            return Result()

    monkeypatch.setitem(provider_readiness.__dict__, "TiingoAdapter", Adapter)
    monkeypatch.setitem(provider_readiness.__dict__, "QuantPadAdapter", Adapter)

    tiingo = provider_readiness.run_explicit_check(tmp_path, "tiingo")
    quantpad = provider_readiness.run_explicit_check(tmp_path, "quantpad")

    assert tiingo["granted_capabilities"] == ["corporate_actions", "historical_bars"]
    assert quantpad["granted_capabilities"] == ["research_bars"]
    assert cast(dict[str, object], tiingo["details"])["row_count"] == 7


def test_ibkr_docker_probe_failure_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/docker")

    def timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("docker", 5)

    def closed(*args: object, **kwargs: object) -> None:
        raise OSError("closed")

    monkeypatch.setattr(subprocess, "run", timeout)
    monkeypatch.setattr(socket, "create_connection", closed)
    receipt = provider_readiness.run_explicit_check(tmp_path, "ibkr")
    details = cast(dict[str, object], receipt["details"])
    assert receipt["verification_state"] == "connectivity_failed"
    assert details["docker_cli"] is True
    assert details["docker_daemon"] is False


def test_internal_defect_propagates_instead_of_recording_schema_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def defective_check() -> tuple[tuple[str, ...], dict[str, object]]:
        raise AttributeError("adapter object has no attribute 'bars'")

    checkers = cast(dict[str, object], provider_readiness.__dict__["_CHECKERS"])
    monkeypatch.setitem(checkers, "tiingo", defective_check)

    with pytest.raises(AttributeError):
        provider_readiness.run_explicit_check(tmp_path, "tiingo")

    assert not (tmp_path / "provider-checks").exists()
