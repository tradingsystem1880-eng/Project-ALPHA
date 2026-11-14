"""Exact capture equivalence and closed observed-range membership rules."""

from __future__ import annotations

import importlib
import importlib.util
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoSnapshotMemberV1,
)


@pytest.fixture
def members() -> ModuleType:
    name = "alpha_cli._crypto_snapshot_members"
    assert importlib.util.find_spec(name) is not None, "shared snapshot member resolver is missing"
    return importlib.import_module(name)


def _pair(
    start: int | None = 1, end: int | None = 2, *, digest: str = "a", instrument: str = "BTCUSDT"
) -> tuple[CryptoSnapshotMemberV1, CryptoQualityReportV1]:
    dataset = CryptoDatasetIdentityV1(
        provider="binance",
        venue="binance",
        market_type="spot",
        family="market_bars",
        instrument=instrument,
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1d",
        units="quote_price",
        timestamp_convention="bar_open",
    )
    return (
        CryptoSnapshotMemberV1(dataset, f"normalized/{digest}.parquet", digest * 64),
        CryptoQualityReportV1(
            digest * 64,
            "quality-v1",
            "qualified",
            (),
            (),
            datetime(2025, 1, start, tzinfo=UTC) if start else None,
            datetime(2025, 1, end, tzinfo=UTC) if end else None,
            2,
            (),
        ),
    )


def _capture() -> tuple[dict[str, Any], dict[str, Any]]:
    member, quality = _pair()
    manifest = dict(
        manifest_id="n1",
        artifact_kind="normalized",
        artifact_key=member.artifact_key,
        artifact_sha256=member.artifact_sha256,
        artifact_bytes=123,
        dataset=member.dataset.to_dict(),
        provider="binance",
        schema_version=1,
        input_manifest_ids=["r1"],
        quality=quality.to_dict(),
        acquisition_scope={"case_id": "case-a"},
    )
    raw = dict(
        manifest_id="r1",
        artifact_kind="raw",
        artifact_key="raw/r1",
        receipt_id="receipt1",
        artifact_sha256="b" * 64,
        artifact_bytes=321,
        provider="binance",
        schema_version=1,
        dataset=member.dataset.to_dict(),
        receipt={
            "receipt_id": "receipt1",
            "fetched_at": "2026-01-01T00:00:00Z",
            "response_sha256": "b" * 64,
            "request": {"period": "2025-01"},
            "parser_version": "v1",
            "schema_version": 1,
            "provider": "binance",
            "upstream_checksum": "c" * 64,
        },
    )
    return manifest, {"r1": raw}


def test_signature_ignores_exact_per_fetch_fields_and_raw_order(members: ModuleType) -> None:
    manifest, raws = _capture()
    original = deepcopy((manifest, raws))
    other, other_raws = deepcopy((manifest, raws))
    other["manifest_id"] = "n2"
    other["input_manifest_ids"] = ["r2"]
    raw = other_raws.pop("r1")
    raw.update(manifest_id="r2", artifact_key="raw/r2", receipt_id="receipt2")
    raw["receipt"].update(receipt_id="receipt2", fetched_at="2026-02-01T00:00:00Z")
    other_raws["r2"] = raw
    assert members.capture_signature(manifest, raws) == members.capture_signature(other, other_raws)
    assert (manifest, raws) == original
    raws["r3"] = deepcopy(raws["r1"])
    raws["r3"]["artifact_sha256"] = "d" * 64
    manifest["input_manifest_ids"] = ["r1", "r3"]
    other = deepcopy(manifest)
    other["input_manifest_ids"].reverse()
    assert members.capture_signature(manifest, raws) == members.capture_signature(other, raws)


@pytest.mark.parametrize(
    "path",
    [
        "artifact_kind",
        "artifact_key",
        "artifact_sha256",
        "artifact_bytes",
        "dataset",
        "provider",
        "schema_version",
        "acquisition_scope",
        "quality.method_version",
        "quality.correction_lineage",
        "quality.state",
        "quality.failures",
        "quality.warnings",
        "quality.observed_start",
        "quality.observed_end",
        "quality.row_count",
        "quality.schema_version",
        "quality.dataset_sha256",
        "raw.artifact_sha256",
        "raw.artifact_bytes",
        "raw.provider",
        "raw.schema_version",
        "raw.dataset",
        "raw.receipt.response_sha256",
        "raw.receipt.request",
        "raw.receipt.parser_version",
        "raw.receipt.schema_version",
        "raw.receipt.provider",
        "raw.receipt.upstream_checksum",
    ],
)
def test_signature_keeps_every_evidence_field(members: ModuleType, path: str) -> None:
    manifest, raws = _capture()
    other, other_raws = deepcopy((manifest, raws))
    parts = path.split(".")
    target = other_raws["r1"] if parts[0] == "raw" else other
    if parts[0] == "raw":
        parts.pop(0)
    for key in parts[:-1]:
        target = target[key]
    target[parts[-1]] = "changed"
    assert members.capture_signature(manifest, raws) != members.capture_signature(other, other_raws)


@pytest.mark.parametrize("invalid", ["missing", "non_list", "not_raw", "invalid_id"])
def test_signature_rejects_invalid_raw_lineage(members: ModuleType, invalid: str) -> None:
    manifest, raws = _capture()
    if invalid == "missing":
        raws.clear()
    elif invalid == "non_list":
        manifest["input_manifest_ids"] = "r1"
    elif invalid == "not_raw":
        raws["r1"]["artifact_kind"] = "normalized"
    else:
        manifest["input_manifest_ids"] = [{}]
    with pytest.raises(DataError, match="raw lineage is missing or invalid"):
        members.capture_signature(manifest, raws)


@pytest.mark.parametrize("case", ["none", "one", "equal", "unequal"])
def test_resolve_member_candidates(members: ModuleType, case: str) -> None:
    manifest, raws = _capture()
    member, _ = _pair()
    if case == "none":
        with pytest.raises(DataError, match="missing or mismatched"):
            members.resolve_member(replace(member, artifact_key="different"), [manifest], raws)
        return
    candidates = [manifest]
    if case in {"equal", "unequal"}:
        other = deepcopy(manifest)
        other["manifest_id"] = "n0"
        candidates.append(other)
        if case == "unequal":
            other["quality"]["correction_lineage"] = ["changed"]
            with pytest.raises(DataError, match="ambiguous; retained captures"):
                members.resolve_member(member, candidates, raws)
            return
    assert members.resolve_member(member, candidates, raws)["manifest_id"] == (
        "n0" if case == "equal" else "n1"
    )


def test_canonical_order_uses_dataset_start_and_hash(members: ModuleType) -> None:
    expected = [
        _pair(None, None, digest="a"),
        _pair(digest="a"),
        _pair(digest="b"),
        _pair(3, 4),
        _pair(instrument="ETHUSDT"),
    ]
    assert list(members.canonical_order(expected)) == expected
    assert list(members.canonical_order(list(reversed(expected)))) == expected


@pytest.mark.parametrize("start,end", [(2, 3), (1, 2), (None, 3), (3, None)])
def test_closed_ranges_reject_touching_overlap_and_missing(
    members: ModuleType,
    start: int | None,
    end: int | None,
) -> None:
    with pytest.raises(DataError, match="disjoint observed ranges"):
        members.check_dataset_ranges([_pair(), _pair(start, end, digest="b")])


def test_disjoint_ranges_and_distinct_datasets_are_accepted(members: ModuleType) -> None:
    members.check_dataset_ranges([_pair(3, 4), _pair(), _pair(instrument="ETHUSDT")])


@pytest.mark.parametrize(
    ("artifact_key", "accepted"), [("raw/legacy/archive.zip", True), ("other/archive.zip", False)]
)
def test_signature_accepts_legacy_raw_inputs_like_publication(
    members: ModuleType, artifact_key: str, accepted: bool
) -> None:
    manifest, raws = _capture()
    del raws["r1"]["artifact_kind"]
    raws["r1"]["artifact_key"] = artifact_key
    if accepted:
        assert members.capture_signature(manifest, raws)["raw_inputs"]
    else:
        with pytest.raises(DataError, match="raw lineage is missing or invalid"):
            members.capture_signature(manifest, raws)
