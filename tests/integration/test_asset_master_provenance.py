"""Real catalog→master→snapshot/contract consumers with disposable evidence only."""

from __future__ import annotations

import io
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

NOW = datetime(2026, 1, 1, tzinfo=UTC)
runner = CliRunner()


def invoke(*args: str) -> Any:
    return runner.invoke(app, ["crypto-data", *args, "--json"])


@pytest.fixture
def evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    store = CryptoBulkStore(
        bulk_root=tmp_path / "bulk",
        manifest_root=tmp_path / "manifests",
        expected_volume_uuid="SYNTHETIC",
        volume_uuid=lambda _: "SYNTHETIC",
        capacity=lambda _: Capacity(2_000_000_000_000, 1_500_000_000_000),
    )
    store.bulk_root.mkdir()
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "control"))
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    for name in ["_control_store", "fetch_bybit_public", "_acquire_result"]:
        monkeypatch.setattr(
            crypto_data_cmds, name, lambda *a, **k: pytest.fail("no provider/control-store action")
        )
    cg = CryptoDatasetIdentityV1(
        provider="coingecko",
        venue="coingecko",
        market_type="network",
        family="asset_metadata",
        instrument="all",
        base_asset=None,
        quote_asset=None,
        frequency="catalog_snapshot",
        units="provider_native",
        timestamp_convention="captured_at_utc",
    )
    dex = replace(
        cg,
        provider="geckoterminal",
        venue="geckoterminal",
        family="dex_pools",
        instrument="ethereum",
    )
    funding = replace(
        cg,
        provider="bybit",
        venue="bybit",
        market_type="linear",
        family="funding",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="funding_interval",
        units="dimensionless_rate",
        timestamp_convention="provider_event_utc",
    )
    frames = [
        pl.DataFrame(
            {
                "observed_at": [NOW],
                "coingecko_id": ["token-x"],
                "network": ["ethereum"],
                "contract_address": ["0xabcd"],
            }
        ),
        pl.DataFrame(
            {
                "observed_at": [NOW],
                "network": ["eth"],
                "base_token_address": ["0xabcd"],
                "quote_token_address": ["0x1234"],
                "reserve_usd": [100_000.0],
                "h24_volume_usd": [1_000.0],
            }
        ),
        pl.DataFrame({"observed_at": [NOW], "timestamp": [NOW], "funding_rate": [0.001]}),
    ]
    ids = []
    for dataset, frame in zip([cg, dex, funding], frames, strict=True):

        def parse(_: bytes, selected: pl.DataFrame = frame) -> pl.DataFrame:
            return selected

        result = ingest_provider_payload(
            store,
            dataset=dataset,
            payload=("synthetic-" + dataset.family).encode(),
            request=(("family", dataset.family),),
            fetched_at=NOW,
            provider_schema="synthetic",
            parser_version="synthetic-v1",
            logical_name="catalog.json",
            parser=parse,
            observed_column="observed_at",
            key_columns=("observed_at",),
        )
        assert result.quality.state == "qualified", result.quality
        ids.append(str(result.normalized_manifest["manifest_id"]))
    created = invoke(
        "asset-master-create",
        "--coingecko-manifest-id",
        ids[0],
        "--geckoterminal-manifest-id",
        ids[1],
    )
    assert created.exit_code == 0, created.output
    master = json.loads(created.stdout)["asset_master_version"]
    return store, ids, master, tmp_path


def test_existing_consumer_reopens_committed_source_manifest(evidence: Any) -> None:
    store, ids, master, root = evidence
    (store.manifest_root / (ids[0] + ".json")).unlink()
    result = invoke("asset-master-verify", master)
    assert result.exit_code != 0 and "frozen" not in result.stdout


def test_snapshot_admission_refuses_missing_master_source_without_publishing(evidence: Any) -> None:
    store, ids, master, root = evidence
    (store.manifest_root / (ids[0] + ".json")).unlink()
    before = list((root / "control").rglob("*.json"))
    result = invoke("snapshot-create", "--manifest-id", ids[2], "--asset-master-version", master)
    assert result.exit_code != 0
    assert list((root / "control").rglob("*.json")) == before


def fingerprint(root: Path) -> dict[str, str]:
    import hashlib

    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def snapshot(member: str, master: str | None = None) -> Any:
    args = ["snapshot-create", "--manifest-id", member]
    if master is not None:
        args += ["--asset-master-version", master]
    return invoke(*args)


def test_valid_sources_contract_and_snapshot_reopen_without_rebuilding_identity(
    evidence: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, ids, master, root = evidence
    before = fingerprint(root)
    monkeypatch.setattr(
        store, "verify_ready", lambda **k: pytest.fail("read verification must not probe writes")
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "build_cross_provider_asset_master",
        lambda **k: pytest.fail("never rebuild frozen identities with current builder"),
    )
    checked = invoke("asset-master-verify", master)
    assert checked.exit_code == 0 and json.loads(checked.stdout)["asset_master_version"] == master
    resolved = invoke(
        "asset-contract",
        "ethereum",
        "0xabcd",
        "--asset-master-version",
        master,
        "--as-of",
        NOW.isoformat(),
    )
    assert resolved.exit_code == 0 and json.loads(resolved.stdout)["coingecko_id"] == "token-x"
    assert fingerprint(root) == before
    created = snapshot(ids[2], master)
    assert created.exit_code == 0, created.output
    sid = json.loads(created.stdout)["snapshot_id"]
    checked = invoke("snapshot-verify", sid, "--required-family", "funding")
    assert checked.exit_code == 0 and json.loads(checked.stdout)["eligible"] is True
    assert snapshot(ids[2], master).stdout == created.stdout


@pytest.mark.parametrize("fault", ["normalized_bytes", "raw_bytes", "missing_raw_manifest"])
def test_source_byte_or_raw_lineage_failure_is_unavailable_and_read_only(
    evidence: Any, fault: str
) -> None:
    store, ids, master, root = evidence
    source = store.verify_manifest(ids[0])
    if fault == "normalized_bytes":
        (store.bulk_root / source["artifact_key"]).write_bytes(b"changed")
    else:
        raw_id = source["input_manifest_ids"][0]
        raw = store.verify_manifest(raw_id)
        if fault == "raw_bytes":
            (store.bulk_root / raw["artifact_key"]).write_bytes(b"changed")
        else:
            (store.manifest_root / (raw_id + ".json")).unlink()
    before = fingerprint(root)
    assert invoke("asset-master-verify", master).exit_code != 0
    assert fingerprint(root) == before
    assert snapshot(ids[2], master).exit_code != 0


def test_deleted_catalog_manifest_blocks_existing_snapshot_and_contract_consumers(
    evidence: Any,
) -> None:
    store, ids, master, root = evidence
    created = snapshot(ids[2], master)
    assert created.exit_code == 0, created.output
    sid = json.loads(created.stdout)["snapshot_id"]
    (store.manifest_root / (ids[0] + ".json")).unlink()
    before = fingerprint(root)
    assert invoke("snapshot-verify", sid, "--required-family", "funding").exit_code != 0
    assert (
        invoke(
            "asset-contract",
            "ethereum",
            "0xabcd",
            "--asset-master-version",
            master,
            "--as-of",
            NOW.isoformat(),
        ).exit_code
        != 0
    )
    assert fingerprint(root) == before


@pytest.mark.parametrize("fault", ["wrong_family", "unbound"])
def test_unsupported_provenance_is_not_inferred_for_legacy_master(
    evidence: Any, fault: str
) -> None:
    from alpha_data.crypto.asset_master import AssetMaster

    store, ids, master, root = evidence
    decoded = crypto_data_cmds._read_asset_master(master)
    candidate = AssetMaster(
        decoded.identities, source_manifest_ids=() if fault == "unbound" else (ids[2], ids[1])
    )
    crypto_data_cmds._write_asset_master(candidate)
    # Historical content decoding remains available and byte/schema compatible.
    assert crypto_data_cmds._read_asset_master(candidate.version).to_dict() == candidate.to_dict()
    before = fingerprint(root)
    assert invoke("asset-master-verify", candidate.version).exit_code != 0
    assert snapshot(ids[2], candidate.version).exit_code != 0
    assert fingerprint(root) == before


def test_valid_artifact_under_wrong_filename_cannot_substitute_requested_master(
    evidence: Any,
) -> None:
    from alpha_data.crypto.asset_master import AssetMaster

    store, ids, master, root = evidence
    decoded = crypto_data_cmds._read_asset_master(master)
    different = AssetMaster(
        tuple(
            replace(i, coingecko_id="other-token") if not i.native_asset else i
            for i in decoded.identities
        ),
        source_manifest_ids=decoded.source_manifest_ids,
    )
    assert different.version != master
    path = crypto_data_cmds._asset_master_root() / (master + ".json")
    path.write_text(json.dumps(different.to_dict()))
    result = invoke("asset-master-verify", master)
    assert result.exit_code != 0 and "requested version" in result.output
    assert snapshot(ids[2], master).exit_code != 0


def test_reviewed_builtin_snapshot_does_not_require_catalog_sources(evidence: Any) -> None:
    store, ids, master, root = evidence
    (store.manifest_root / (ids[0] + ".json")).unlink()
    created = snapshot(ids[2])
    assert created.exit_code == 0, created.output
    # Creation relies only on its selected member and the unchanged reviewed native label.
    assert json.loads(created.stdout)["asset_master_version"] == "reviewed-native-v1"


def test_asset_master_publication_is_inside_existing_admission_lock(
    evidence: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    store, ids, master, root = evidence
    held = []
    writer = crypto_data_cmds._write_asset_master

    @contextmanager
    def locked() -> Any:
        held.append(True)
        try:
            yield
        finally:
            held.pop()

    def write(value: Any) -> None:
        assert held == [True]
        writer(value)

    monkeypatch.setattr(store, "admission_lock", locked)
    monkeypatch.setattr(crypto_data_cmds, "_write_asset_master", write)
    result = invoke(
        "asset-master-create",
        "--coingecko-manifest-id",
        ids[0],
        "--geckoterminal-manifest-id",
        ids[1],
    )
    assert result.exit_code == 0 and not held


@pytest.mark.bias_guard
def test_future_catalog_append_never_rebinds_frozen_master(evidence: Any) -> None:
    from datetime import timedelta

    store, ids, master, root = evidence
    first = snapshot(ids[2], master)
    assert first.exit_code == 0, first.output
    old = crypto_data_cmds._read_asset_master(master)
    future = NOW + timedelta(days=1)
    dataset = CryptoDatasetIdentityV1.from_dict(store.verify_manifest(ids[0])["dataset"])
    frame = pl.DataFrame(
        {
            "observed_at": [future],
            "coingecko_id": ["future-canary"],
            "network": ["ethereum"],
            "contract_address": ["0xabcd"],
        }
    )
    later = ingest_provider_payload(
        store,
        dataset=dataset,
        payload=b"future-canary-catalog",
        request=(("family", "asset_metadata"),),
        fetched_at=future,
        provider_schema="synthetic",
        parser_version="synthetic-v1",
        logical_name="future.json",
        parser=lambda _: frame,
        observed_column="observed_at",
        key_columns=("observed_at",),
    )
    assert later.quality.state == "qualified" and later.normalized_manifest["manifest_id"] != ids[0]
    # Positive control: explicitly selecting the later source produces a different master.
    changed = invoke(
        "asset-master-create",
        "--coingecko-manifest-id",
        str(later.normalized_manifest["manifest_id"]),
        "--geckoterminal-manifest-id",
        ids[1],
    )
    assert changed.exit_code == 0 and json.loads(changed.stdout)["asset_master_version"] != master
    assert crypto_data_cmds._read_asset_master(master).to_dict() == old.to_dict()
    assert invoke("asset-master-verify", master).exit_code == 0
    assert snapshot(ids[2], master).stdout == first.stdout
    resolved = invoke(
        "asset-contract",
        "ethereum",
        "0xabcd",
        "--asset-master-version",
        master,
        "--as-of",
        NOW.isoformat(),
    )
    assert resolved.exit_code == 0 and json.loads(resolved.stdout)["coingecko_id"] == "token-x"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("quarantined", [False, True])
def test_snapshot_verify_refuses_ambiguous_recapture(
    evidence: Any, monkeypatch: pytest.MonkeyPatch, reverse: bool, quarantined: bool
) -> None:
    store, ids, master, root = evidence
    made = invoke("snapshot-create", "--manifest-id", ids[2], "--asset-master-version", master)
    assert made.exit_code == 0, made.output
    snapshot = json.loads(made.stdout)["snapshot_id"]
    before = invoke("snapshot-verify", snapshot)
    assert before.exit_code == 0 and json.loads(before.stdout)["eligible"]
    original, payload = store.read_verified_normalized(ids[2], max_bytes=32 * 1024 * 1024)
    dataset = CryptoDatasetIdentityV1.from_dict(original["dataset"])
    duplicate = ingest_provider_payload(
        store,
        dataset=dataset,
        payload=b"a-distinct-synthetic-capture",
        request=(("capture", "second"),),
        fetched_at=NOW,
        provider_schema="synthetic",
        parser_version="synthetic-v1",
        logical_name="second.json",
        parser=lambda _: pl.read_parquet(io.BytesIO(payload)),
        observed_column="observed_at",
        key_columns=("observed_at",),
    )
    assert duplicate.normalized_manifest["manifest_id"] != ids[2]
    assert duplicate.normalized_manifest["artifact_sha256"] == original["artifact_sha256"]
    if quarantined:
        # A competing capture with different eligibility evidence must not be preferred
        # or discarded simply to recover a unique qualified match.
        path = store.manifest_root / (str(duplicate.normalized_manifest["manifest_id"]) + ".json")
        body = json.loads(path.read_text())
        path.unlink()
        body.pop("manifest_id")
        quality = CryptoQualityReportV1.from_dict(body["quality"])
        body["quality"] = replace(quality, state="quarantined", failures=("synthetic",)).to_dict()
        store._publish_manifest(body)
    inventory = store.inventory
    if reverse:
        monkeypatch.setattr(store, "inventory", lambda **kw: tuple(reversed(inventory(**kw))))
    before = fingerprint(root)
    result = invoke("snapshot-verify", snapshot)
    assert result.exit_code != 0 and "ambiguous" in result.output
    assert fingerprint(root) == before


@pytest.mark.parametrize(
    "fault", ["missing_manifest", "raw_bytes", "normalized_bytes", "snapshot_alias"]
)
def test_snapshot_member_reopen_failure_is_read_only(evidence: Any, fault: str) -> None:
    store, ids, master, root = evidence
    made = snapshot(ids[2], master)
    assert made.exit_code == 0, made.output
    sid = json.loads(made.stdout)["snapshot_id"]
    original = store.verify_manifest(ids[2])
    if fault == "missing_manifest":
        (store.manifest_root / (ids[2] + ".json")).unlink()
    elif fault == "snapshot_alias":
        alias = "a" * 64 if sid != "a" * 64 else "b" * 64
        path = crypto_data_cmds._snapshot_root() / (alias + ".json")
        path.write_bytes((crypto_data_cmds._snapshot_root() / (sid + ".json")).read_bytes())
        sid = alias
    elif fault == "raw_bytes":
        raw = store.verify_manifest(original["input_manifest_ids"][0])
        (store.bulk_root / raw["artifact_key"]).write_bytes(b"tampered")
    else:
        (store.bulk_root / original["artifact_key"]).write_bytes(b"tampered")
    before = fingerprint(root)
    result = invoke("snapshot-verify", sid, "--required-family", "funding")
    assert result.exit_code != 0
    assert fingerprint(root) == before


@pytest.mark.parametrize("reverse", [False, True])
def test_distinct_dataset_metadata_cannot_overwrite_exact_member(
    evidence: Any, monkeypatch: pytest.MonkeyPatch, reverse: bool
) -> None:
    store, ids, master, root = evidence
    made = snapshot(ids[2], master)
    assert made.exit_code == 0, made.output
    sid = json.loads(made.stdout)["snapshot_id"]
    original = store.verify_manifest(ids[2])
    # Correctly content-addressed but incompatible metadata references the same bytes.
    # It must neither replace the exact dataset match nor create its ambiguity.
    body = {k: v for k, v in original.items() if k != "manifest_id"}
    dataset = CryptoDatasetIdentityV1.from_dict(body["dataset"])
    body["dataset"] = replace(dataset, quote_asset="USD").to_dict()
    other = store._publish_manifest(body)
    assert other["manifest_id"] != ids[2]
    inventory = store.inventory
    if reverse:
        monkeypatch.setattr(store, "inventory", lambda **kw: tuple(reversed(inventory(**kw))))
    before = fingerprint(root)
    result = invoke("snapshot-verify", sid, "--required-family", "funding")
    assert result.exit_code == 0 and json.loads(result.stdout)["eligible"]
    assert fingerprint(root) == before
