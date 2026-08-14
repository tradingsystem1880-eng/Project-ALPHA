"""Explicit, redacted provider verification receipts.

The registry may describe local package and credential presence. Only this module performs a
bounded, operator-requested check and only its immutable receipt can describe verification.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import socket
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final, Literal

from alpha_cli._atomic import write_text
from alpha_core import DataError
from alpha_data.adapters.quantpad_adapter import QuantPadAdapter
from alpha_data.adapters.tiingo_adapter import TiingoAdapter

type VerificationState = Literal[
    "verified",
    "unverified",
    "authentication_failed",
    "entitlement_denied",
    "rate_limited",
    "connectivity_failed",
    "schema_drift",
    "optional_disabled",
]

_STATES: Final = frozenset(
    {
        "verified",
        "unverified",
        "authentication_failed",
        "entitlement_denied",
        "rate_limited",
        "connectivity_failed",
        "schema_drift",
        "optional_disabled",
    }
)
_DETAIL_KEYS: Final = frozenset(
    {
        "interface",
        "symbol",
        "row_count",
        "schema_version",
        "docker_cli",
        "docker_daemon",
        "image_digest_reviewed",
        "account_alias",
        "gateway_reachable",
        "host",
        "port",
        "permissions",
        "market_data",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataError("provider check timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def record_check_receipt(
    data_dir: Path,
    *,
    provider_id: str,
    verification_state: VerificationState,
    granted_capabilities: Sequence[str],
    checked_at: datetime,
    recovery_action: str,
    details: Mapping[str, object],
) -> dict[str, object]:
    """Persist one immutable receipt after removing everything outside the public schema."""
    provider = provider_id.strip().lower()
    if not provider or not re.fullmatch(r"[a-z0-9_-]+", provider):
        raise DataError("provider id is invalid")
    if verification_state not in _STATES:
        raise DataError("provider verification state is invalid")
    safe_details = {key: details[key] for key in sorted(details) if key in _DETAIL_KEYS}
    body: dict[str, object] = {
        "schema_version": 1,
        "provider_id": provider,
        "verification_state": verification_state,
        "checked_at": _timestamp(checked_at),
        "granted_capabilities": sorted(set(granted_capabilities)),
        "recovery_action": recovery_action.strip()[:500],
        "details": safe_details,
    }
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    receipt = {**body, "receipt_id": digest, "content_sha256": digest}
    path = Path(data_dir) / "provider-checks" / provider / f"{digest}.json"
    rendered = json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise DataError("provider receipt identity collision")
    else:
        write_text(path, rendered)
    return receipt


def _verify_receipt(raw: object, provider_id: str) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    digest = raw.get("content_sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        return None
    body = {key: value for key, value in raw.items() if key not in {"receipt_id", "content_sha256"}}
    if hashlib.sha256(_canonical(body)).hexdigest() != digest:
        return None
    if raw.get("receipt_id") != digest or raw.get("provider_id") != provider_id:
        return None
    return raw


def last_check_status(data_dir: Path, provider_id: str) -> dict[str, object]:
    root = Path(data_dir) / "provider-checks" / provider_id
    if not root.exists():
        return {
            "verification_state": "unverified",
            "verified_at": None,
            "last_receipt_id": None,
            "granted_capabilities": [],
            "recovery_action": "Run an explicit provider check from the Readiness Center.",
        }
    valid: list[dict[str, object]] = []
    tampered = False
    for path in root.glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            tampered = True
            continue
        receipt = _verify_receipt(raw, provider_id)
        if receipt is None:
            tampered = True
        else:
            valid.append(receipt)
    if tampered:
        return {
            "verification_state": "schema_drift",
            "verified_at": None,
            "last_receipt_id": None,
            "granted_capabilities": [],
            "recovery_action": (
                "A provider receipt failed integrity verification; inspect locally and rerun "
                "the check."
            ),
        }
    if not valid:
        return last_check_status(Path(data_dir) / "__missing__", provider_id)
    latest = max(valid, key=lambda row: (str(row["checked_at"]), str(row["receipt_id"])))
    verified = latest["verification_state"] == "verified"
    return {
        "verification_state": latest["verification_state"],
        "verified_at": latest["checked_at"] if verified else None,
        "last_receipt_id": latest["receipt_id"],
        "granted_capabilities": latest["granted_capabilities"] if verified else [],
        "recovery_action": latest["recovery_action"],
    }


def classify_failure(status_code: int | None, detail: str) -> VerificationState:
    if status_code == 401:
        return "authentication_failed"
    if status_code == 403:
        return "entitlement_denied"
    if status_code == 429:
        return "rate_limited"
    lowered = detail.lower()
    if status_code is None and any(
        token in lowered for token in ("timeout", "transport", "connect")
    ):
        return "connectivity_failed"
    return "schema_drift"


def _failure_from_exception(exc: Exception) -> VerificationState:
    match = re.search(r"(?:http|error)\s*(401|403|429)", str(exc), re.IGNORECASE)
    code = int(match.group(1)) if match else None
    return classify_failure(code, str(exc))


def _tiingo_check() -> tuple[tuple[str, ...], dict[str, object]]:
    end = date.today()
    result = TiingoAdapter(canonical_symbol="SPY", asset_class="etf").fetch(
        "SPY", end - timedelta(days=14), end
    )
    return ("historical_bars", "corporate_actions"), {
        "interface": "rest",
        "symbol": "SPY",
        "row_count": result.bars.height,
    }


def _quantpad_check() -> tuple[tuple[str, ...], dict[str, object]]:
    end = date.today()
    result = QuantPadAdapter().fetch("SPY", end - timedelta(days=14), end)
    return ("research_bars",), {
        "interface": "rest",
        "symbol": "SPY",
        "row_count": result.bars.height,
    }


def _verified_what_if_receipt(data_dir: Path, account_alias: str, account_fingerprint: str) -> bool:
    roots = (
        Path(data_dir) / "ibkr-what-if-v2" / "receipts",
        Path(data_dir) / "ibkr-what-if-v1" / "receipts",
    )
    paths = [path for root in roots if root.exists() for path in root.glob("*.json")]
    verified = False
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(raw, dict):
            return False
        receipt_hash = raw.get("receipt_hash")
        body = {key: value for key, value in raw.items() if key != "receipt_hash"}
        valid_hash = (
            isinstance(receipt_hash, str)
            and _SHA256.fullmatch(receipt_hash) is not None
            and hashlib.sha256(_canonical(body)).hexdigest() == receipt_hash
        )
        if not valid_hash:
            return False
        if all(
            (
                raw.get("account_alias") == account_alias,
                raw.get("account_fingerprint") == account_fingerprint,
                raw.get("status") == "PREVIEW_VERIFIED",
                raw.get("what_if") is True,
                raw.get("wire_transmit") is True,
                raw.get("broker_order_transmitted") is False,
                raw.get("position_unchanged") is True,
                raw.get("order_status_callbacks") == 0,
                raw.get("execution_callbacks") == 0,
                raw.get("paper_acceptance_credit") is False,
            )
        ):
            verified = True
    return verified


def _ibkr_check(data_dir: Path | None = None) -> tuple[tuple[str, ...], dict[str, object]]:
    import os

    image = os.environ.get("ALPHA_IBKR_GATEWAY_IMAGE", "")
    account = os.environ.get("ALPHA_IBKR_PAPER_ACCOUNT", "").strip().upper()
    docker_cli = shutil.which("docker") is not None
    docker_daemon = False
    if docker_cli:
        try:
            docker_daemon = (
                subprocess.run(
                    ["docker", "info", "--format", "{{.ServerVersion}}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                ).returncode
                == 0
            )
        except (OSError, subprocess.TimeoutExpired):
            docker_daemon = False
    reachable = False
    try:
        with socket.create_connection(("127.0.0.1", 4002), timeout=2):
            reachable = True
    except OSError:
        pass
    reviewed = bool(re.fullmatch(r"[A-Za-z0-9._/:+-]+@sha256:[0-9a-f]{64}", image))
    alias = f"DU…{account[-4:]}" if re.fullmatch(r"DU[A-Z0-9]+", account) else None
    details: dict[str, object] = {
        "interface": "paper_gateway",
        "docker_cli": docker_cli,
        "docker_daemon": docker_daemon,
        "image_digest_reviewed": reviewed,
        "account_alias": alias,
        "gateway_reachable": reachable,
        "host": "127.0.0.1",
        "port": 4002,
        "permissions": "unknown",
        "market_data": "unknown",
    }
    if not all((docker_cli, docker_daemon, reviewed, alias, reachable)):
        raise ProviderCheckFailure("connectivity_failed", details)
    if (
        data_dir is not None
        and isinstance(alias, str)
        and _verified_what_if_receipt(data_dir, alias, hashlib.sha256(account.encode()).hexdigest())
    ):
        details["permissions"] = "what_if_preview_verified"
        details["market_data"] = "not_verified_by_what_if"
        return ("paper_what_if_preview",), details
    # A socket cannot prove broker permissions or market-data entitlement.
    raise ProviderCheckFailure("unverified", details)


class ProviderCheckFailure(Exception):
    def __init__(self, state: VerificationState, details: Mapping[str, object]) -> None:
        super().__init__(state)
        self.state = state
        self.details = details


_CHECKERS: dict[str, Callable[[], tuple[tuple[str, ...], dict[str, object]]]] = {
    "tiingo": _tiingo_check,
    "quantpad": _quantpad_check,
    "ibkr": _ibkr_check,
}


def run_explicit_check(data_dir: Path, provider_id: str) -> dict[str, object]:
    """Perform exactly one bounded provider check requested by an owner click or CLI command."""
    provider = provider_id.strip().lower()
    checker = _CHECKERS.get(provider)
    if checker is None:
        raise DataError("explicit checks are available only for tiingo, quantpad, and ibkr")
    try:
        capabilities, details = _ibkr_check(data_dir) if provider == "ibkr" else checker()
    except ProviderCheckFailure as exc:
        state = exc.state
        capabilities = ()
        details = dict(exc.details)
    except Exception as exc:
        state = _failure_from_exception(exc)
        capabilities = ()
        details = {"interface": "rest" if provider != "ibkr" else "paper_gateway"}
    else:
        state = "verified"
    recovery = {
        "verified": "No action required.",
        "unverified": (
            "Run the separately checkpointed paper what-if preview to verify broker callbacks."
        ),
        "authentication_failed": (
            "Rotate the credential, reinject it into the process, and run one new explicit check."
        ),
        "entitlement_denied": (
            "Review the provider subscription and requested capability before retrying."
        ),
        "rate_limited": (
            "Wait for the provider limit to reset before running one new explicit check."
        ),
        "connectivity_failed": (
            "Check local network or gateway state, then run one new explicit check."
        ),
        "schema_drift": (
            "Review the provider adapter against the current official schema before retrying."
        ),
    }[state]
    return record_check_receipt(
        data_dir,
        provider_id=provider,
        verification_state=state,
        granted_capabilities=capabilities,
        checked_at=datetime.now(UTC),
        recovery_action=recovery,
        details=details,
    )


__all__ = [
    "classify_failure",
    "last_check_status",
    "record_check_receipt",
    "run_explicit_check",
]
