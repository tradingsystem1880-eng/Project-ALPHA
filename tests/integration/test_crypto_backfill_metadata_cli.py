"""Bound metadata bodies through actual status CLI, with temporary synthetic stores."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import crypto_data_cmds
from alpha_cli.crypto_bulk_store import configured_crypto_bulk_store
from alpha_data.crypto.storage import CryptoBulkStore

from .test_crypto_backfill_resume_cli import _completion, _invoke
from .test_crypto_backfill_resume_cli import environment as environment
from .test_crypto_backfill_status_cli import _fingerprint, _no_effects, _status


def _manifest_path(store: CryptoBulkStore, root: Path) -> Path:
    _, _, _, entry = _completion(root)
    return store.manifest_root / f"{entry['manifest_id']}.json"


@pytest.mark.parametrize(
    "kind",
    [
        "oversized_manifest",
        "truncated_manifest",
        "malformed_manifest",
        "deep_manifest",
        "utf16_manifest",
        "oversized_retirement",
        "malformed_retirement",
    ],
)
def test_cli_bad_metadata_blocks_without_write_or_fetch(
    environment: Any, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    path = _manifest_path(store, root)
    if "retirement" in kind:
        path = store.manifest_root.parent / "retirements" / path.name
        path.parent.mkdir()
    if kind.startswith("oversized"):
        path.write_bytes(b" " * 20000)
    elif kind.startswith("deep"):
        path.write_bytes(b"[" * 100 + b"]" * 100)
    elif kind.startswith("utf16"):
        path.write_bytes(path.read_text(encoding="utf-8").encode("utf-16"))
    elif kind.startswith("truncated"):
        path.write_bytes(path.read_bytes()[:30])
    else:
        path.write_bytes(b"{SECRET_CANARY")
    calls.clear()
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _no_effects(monkeypatch, store)
    result = _status(**{"max-verify-metadata-bytes": "10000"})
    assert result.exit_code == 1, result.output
    report = json.loads(result.stdout)
    assert report["windows"][0]["status"] == "unverifiable"
    assert report["metadata_verification_aborted"] is True
    assert "SECRET_CANARY" not in result.output
    assert report["metadata_bytes_read"] <= 10000 and report["historical_quota_usage"] is None
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


def test_cli_counts_repeated_metadata_and_exhaustion_defers_later_windows(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    assert _invoke("ETHUSDT,BTCUSDT").exit_code == 0
    calls.clear()
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _no_effects(monkeypatch, store)
    successful = _status("ETHUSDT,BTCUSDT")
    report = json.loads(successful.stdout)
    cost = report["metadata_bytes_read"]
    assert cost > 0 and cost == report["metadata_bytes_reserved"]
    exact = _status("ETHUSDT,BTCUSDT", **{"max-verify-metadata-bytes": str(cost)})
    assert exact.exit_code == 0, exact.output
    failed = _status(
        "ETHUSDT,BTCUSDT",
        **{"max-verify-metadata-bytes": str(_manifest_path(store, root).stat().st_size - 1)},
    )
    payload = json.loads(failed.stdout)
    assert failed.exit_code == 1
    assert [row["status"] for row in payload["windows"]] == ["unverifiable", "not_checked"]
    assert payload["metadata_bytes_read"] == 0
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


def test_cli_replaced_metadata_is_unverifiable_and_artifacts_stay_unchanged(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    target = _manifest_path(store, root)
    original = target.read_bytes()
    ledger = _completion(root)[0]
    ledger_before = ledger.read_bytes(), ledger.stat().st_mtime_ns
    artifacts_before = _fingerprint(store.bulk_root)
    calls.clear()
    _no_effects(monkeypatch, store)
    read = os.read
    changed = False

    def replacing_read(fd: int, size: int) -> bytes:
        nonlocal changed
        body = read(fd, size)
        if not changed:
            changed = True
            replacement = target.with_name("synthetic-replacement.json")
            replacement.write_bytes(original)
            os.replace(replacement, target)
        return body

    monkeypatch.setattr(os, "read", replacing_read)
    result = _status()
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and report["windows"][0]["status"] == "unverifiable"
    assert report["metadata_verification_aborted"] is True
    assert target.read_bytes() == original
    assert (ledger.read_bytes(), ledger.stat().st_mtime_ns) == ledger_before
    assert _fingerprint(store.bulk_root) == artifacts_before and calls == []
    assert not (root / "control").exists()


def test_deep_configuration_decoder_failure_is_unavailable_not_a_traceback(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:

    store, root, calls = environment
    assert _invoke().exit_code == 0
    path = root / "crypto" / "storage-config.json"
    payload = b"[" * 100 + b"]" * 100
    path.write_bytes(payload)
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: configured_crypto_bulk_store(root))
    load = json.loads

    def nested_failure(value: Any, *args: Any, **kwargs: Any) -> Any:
        if value == payload:
            raise RecursionError("SECRET_CANARY")
        return load(value, *args, **kwargs)

    monkeypatch.setattr(json, "loads", nested_failure)
    calls.clear()
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _no_effects(monkeypatch, store)
    result = _status()
    report = load(result.stdout)
    assert result.exit_code == 1 and report["windows"][0]["status"] == "unavailable"
    assert "SECRET_CANARY" not in result.output
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


def test_content_addressed_malformed_kind_is_unverifiable_not_an_exception(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    from alpha_data.crypto.contracts import canonical_bytes

    store, root, calls = environment
    assert _invoke().exit_code == 0
    ledger, progress, key, entry = _completion(root)
    malformed = json.loads(_manifest_path(store, root).read_bytes())
    body = {k: v for k, v in malformed.items() if k != "manifest_id"}
    body["artifact_kind"] = []
    identity = hashlib.sha256(canonical_bytes(body)).hexdigest()
    body["manifest_id"] = identity
    (store.manifest_root / (identity + ".json")).write_bytes(canonical_bytes(body))
    entry["manifest_id"] = identity
    ledger.write_text(json.dumps(progress))
    calls.clear()
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _no_effects(monkeypatch, store)
    result = _status()
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and report["windows"][0]["status"] == "unverifiable"
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


def test_artifact_budget_only_recursion_preserves_legacy_override_signature(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import cast

    from alpha_data.crypto.verification import ArtifactVerificationBudget

    store, root, calls = environment
    assert _invoke().exit_code == 0
    typed_store = cast(CryptoBulkStore, store)
    original = typed_store.verify_manifest
    observed: list[object] = []

    def legacy_signature(
        manifest_id: object, *, budget: ArtifactVerificationBudget | None = None
    ) -> dict[str, object]:
        observed.append(manifest_id)
        return original(manifest_id, budget=budget)

    monkeypatch.setattr(typed_store, "verify_manifest", legacy_signature)
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    calls.clear()
    entry = _completion(root)[3]
    result = typed_store.verify_manifest(
        entry["manifest_id"], budget=ArtifactVerificationBudget(1000000)
    )
    assert result["artifact_kind"] == "normalized" and len(observed) >= 2
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []
