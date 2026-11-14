"""Monthly frozen studies reopen their exact provenance and project V2 chart lineage."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from alpha_cli import crypto_bulk_store, daily_native_cmds
from alpha_cli._native_daily_rule_projection import chart_snapshot
from alpha_cli._native_daily_rule_protocol import reopen_daily_study
from alpha_cli._native_daily_rule_study import (
    DailyRuleStudyV1,
    bind_daily_study,
    daily_rule_terms_proposal,
)
from alpha_cli.crypto_price_snapshot_query import BinanceDailyPriceSnapshotQueryV2
from alpha_cli.main import app
from alpha_core import DataError
from alpha_data.crypto.storage import CryptoBulkStore
from tests.fixtures.daily_price_months import month_start, publish_month, snapshot_for
from tests.unit.test_crypto_price_snapshot_months import query
from tests.unit.test_crypto_price_snapshot_query import _store

MonthlySource = tuple[Path, CryptoBulkStore, BinanceDailyPriceSnapshotQueryV2]


@pytest.fixture(scope="module")
def monthly_source(tmp_path_factory: pytest.TempPathFactory) -> MonthlySource:
    directory = tmp_path_factory.mktemp("monthly-source")
    store = _store(directory)
    results = [
        publish_month(store, date.year, date.month)
        for date in (month_start(2020, month) for month in range(1, 37))
    ]
    snapshot = snapshot_for(*results)
    root = directory / "control"
    config = root / "crypto" / "storage-config.json"
    config.write_text('{"fixture":"artificial monthly backend"}')
    snapshots = root / "crypto" / "snapshots"
    snapshots.mkdir()
    (snapshots / (snapshot.snapshot_id + ".json")).write_text(json.dumps(snapshot.to_dict()))
    price_query = query(store, results)
    assert isinstance(price_query, BinanceDailyPriceSnapshotQueryV2)
    return root, store, price_query


def bind(root: Path, price_query: BinanceDailyPriceSnapshotQueryV2) -> DailyRuleStudyV1:
    economics, resources = daily_rule_terms_proposal()
    return bind_daily_study(
        price_query,
        snapshot_sha256=price_query.snapshot_id,
        runtime_profile_sha256="a" * 64,
        container_image_id="sha256:" + "b" * 64,
        storage_config_sha256=hashlib.sha256(
            (root / "crypto" / "storage-config.json").read_bytes()
        ).hexdigest(),
        economics=economics,
        resources=resources,
        data_origin="artificial_fixture",
    )


def test_monthly_study_reopens_restored_store_and_chart_lineage(
    monthly_source: MonthlySource, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, _, price_query = monthly_source
    study = bind(original, price_query)
    assert DailyRuleStudyV1.model_validate(study.to_dict()) == study
    assert len(price_query.rows) == 1096
    restored = tmp_path / "restored"
    shutil.copytree(original.parent, restored)
    store = _store(restored)
    root = restored / "control"
    monkeypatch.setattr(crypto_bulk_store, "configured_crypto_bulk_store", lambda selected: store)
    reopen_daily_study(root, study)
    _, _, lineage = chart_snapshot(root, study, create=True)
    assert lineage["schema"] == "DailyRuleChartLineageV2"
    assert lineage["normalized_members"] == [
        {
            "normalized_manifest_id": member.normalized_manifest_id,
            "normalized_artifact_sha256": member.artifact_sha256,
        }
        for member in price_query.members
    ]
    assert "normalized_manifest_id" not in lineage
    assert "normalized_artifact_sha256" not in lineage
    assert lineage["source_receipt_ids"] == [
        receipt.receipt_id for receipt in price_query.source_receipts
    ]
    assert chart_snapshot(root, study, create=False)[2] == lineage


@pytest.mark.parametrize("defect", ["member_id", "receipt_id", "member_order"])
def test_frozen_monthly_lineage_tampering_refused(
    monthly_source: MonthlySource, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    root, store, price_query = monthly_source
    study = bind(root, price_query)
    document = json.loads(study.query_document)
    if defect == "member_id":
        document["members"][0]["normalized_manifest_id"] = "f" * 64
    elif defect == "receipt_id":
        document["members"][0]["source_receipt_ids"][0] = "f" * 64
    else:
        document["members"].reverse()
    changed = study.to_dict()
    query_document = json.dumps(document, sort_keys=True, separators=(",", ":"))
    changed["query_document"] = query_document
    with pytest.raises(ValidationError):
        DailyRuleStudyV1.model_validate(changed)
    changed["query_sha256"] = hashlib.sha256(query_document.encode()).hexdigest()
    if defect == "member_id":
        altered = DailyRuleStudyV1.model_validate(changed)
        monkeypatch.setattr(
            crypto_bulk_store, "configured_crypto_bulk_store", lambda selected: store
        )
        with pytest.raises(DataError, match="binding differs"):
            reopen_daily_study(root, altered)
    else:
        with pytest.raises(ValidationError):
            DailyRuleStudyV1.model_validate(changed)


def test_draft_daily_repeated_manifest_options_reach_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[tuple[str, dict[str, object]]] = []

    def draft(project_id: str, **kwargs: object) -> dict[str, str]:
        observed.append((project_id, kwargs))
        return {"contract_id": "draft"}

    monkeypatch.setattr(daily_native_cmds, "draft_daily_request", draft)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = CliRunner().invoke(
        app,
        [
            "research",
            "draft-daily",
            "project",
            "--source-pack-id",
            "pack",
            "--snapshot-id",
            "a" * 64,
            "--normalized-manifest-id",
            "b" * 64,
            "--normalized-manifest-id",
            "c" * 64,
        ],
    )
    assert result.exit_code == 0, result.output
    assert observed[0][1]["normalized_manifest_ids"] == ("b" * 64, "c" * 64)
