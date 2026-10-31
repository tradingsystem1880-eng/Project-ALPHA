"""Immutable canonical chart projections of one admitted daily native result.

CryptoSnapshotV1 remains the source contract. A separately identified canonical
Parquet snapshot is derived only for existing chart readers, with explicit lineage.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import TypeAdapter

from alpha_backtest.results import BacktestResult
from alpha_cli import _artifacts
from alpha_cli._native_daily_rule_protocol import canonical, reopen_daily_study, sha
from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli.artifact_contract import ARTIFACT_CONTRACT_VERSION, MANIFEST_SCHEMA_VERSION
from alpha_core import DataError
from alpha_data.snapshot import create_snapshot, snapshot_manifest_hash
from alpha_data.store import ParquetStore

COMMAND = "research_daily_rule_projection_v1"


def daily_watermark(study: DailyRuleStudyV1) -> str:
    return (
        "ARTIFICIAL FIXTURE / NO MARKET EVIDENCE"
        if study.data_origin == "artificial_fixture"
        else "EXPLORATORY / RECONSTRUCTED DISCOVERY; NOT PROMOTED"
    )


def daily_context(project_id: str, study: DailyRuleStudyV1) -> dict[str, object]:
    return {
        "research_gate": {
            "watermark": daily_watermark(study),
            "state": "exploratory",
            "claim_scope": study.claim_scope,
        },
        "run_context": {
            "kind": "governed_project",
            "project_id": project_id,
            "research_gate_state": "not_completed",
        },
    }


def chart_snapshot(
    data_dir: Path, study: DailyRuleStudyV1, *, create: bool, source_data_dir: Path | None = None
) -> tuple[str, str, dict[str, object]]:
    """Reopen source first; derive/verify separate chart bytes without source relabeling."""
    reopen_daily_study(data_dir if source_data_dir is None else source_data_dir, study)
    query = json.loads(study.query_document)
    rows = query["rows"]
    frame = pl.DataFrame(
        {
            "ts": [datetime.fromisoformat(row["open_time"]) for row in rows],
            **{name: [row[name] for row in rows] for name in ("open", "high", "low", "close")},
            "volume": [row["base_volume"] for row in rows],
        }
    )
    snapshot_id = "daily-price-" + study.query_sha256[:24]
    path = data_dir / "snapshots" / snapshot_id
    if not path.exists() and not create:
        raise DataError("daily canonical chart snapshot is missing")
    captured = max(
        datetime.fromisoformat(receipt["fetched_at"].replace("Z", "+00:00"))
        for receipt in query["source_receipts"]
    )
    source = "binance:spot:daily-query-v1"
    with tempfile.TemporaryDirectory(prefix="alpha-daily-chart-") as temporary:
        root = Path(temporary)
        store = ParquetStore(root / "source")
        store.write_bars(study.symbol, frame)
        store.write_provenance(
            study.symbol,
            source=source,
            adapter_version="CryptoSnapshotV1-to-chart-v1",
            parser_version=study.query_sha256,
        )
        destinations = [root / "snapshots"]
        if not path.exists():
            destinations.append(data_dir / "snapshots")
        for destination in destinations:
            create_snapshot(
                store,
                destination,
                snapshot_id,
                [study.symbol],
                source=source,
                adapter_version="CryptoSnapshotV1-to-chart-v1",
                parser_version=study.query_sha256,
                created_at=captured,
            )
        expected = snapshot_manifest_hash(root / "snapshots" / snapshot_id)
    digest = snapshot_manifest_hash(path)
    if digest != expected or not ParquetStore(path).read_bars(study.symbol).equals(frame):
        raise DataError("daily canonical chart snapshot differs from frozen query lineage")
    lineage = {
        "schema": "DailyRuleChartLineageV1",
        "crypto_snapshot_id": study.snapshot_sha256,
        "normalized_manifest_id": query["normalized_manifest_id"],
        "normalized_artifact_sha256": query["artifact_sha256"],
        "query_sha256": study.query_sha256,
        "source_receipt_ids": [receipt["receipt_id"] for receipt in query["source_receipts"]],
        "chart_snapshot_id": snapshot_id,
        "chart_snapshot_hash": digest,
        "conversion": "native_utc_daily_ohlcv_to_canonical_chart_parquet_v1",
        "availability_basis": query["availability_basis"],
        "point_in_time_claim": False,
        "data_origin": study.data_origin,
    }
    return snapshot_id, digest, lineage


def _manifest(
    *,
    project_id: str,
    parent_run_id: str,
    admission: dict[str, Any],
    role: str,
    raw: object,
    study: DailyRuleStudyV1,
    snapshot_id: str,
    snapshot_hash: str,
    source_fingerprint: str,
) -> dict[str, Any]:
    replay = TypeAdapter(BacktestResult).validate_python(raw)
    identity = {
        "schema": "DailyRuleProjectionV1",
        "parent_run_id": parent_run_id,
        "trial_id": admission["trial_id"],
        "role": role,
        "result_sha256": sha(raw),
        "study_sha256": study.content_sha256,
        "snapshot_hash": snapshot_hash,
    }
    return {
        **identity,
        **daily_context(project_id, study),
        "run_id": sha(identity)[:16],
        "run_identity_version": 3,
        "command": COMMAND,
        "kind": "research",
        "scope": "research_only",
        "symbol": study.symbol,
        "snapshot_id": snapshot_id,
        "snapshot_hash": snapshot_hash,
        "research_cutoff": study.discovery_end_exclusive,
        "scientific_acceptance": "not_admitted",
        "synthetic": study.data_origin == "artificial_fixture",
        "data_origin": study.data_origin,
        "real_market_evidence": study.data_origin == "captured_provider_history",
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "execution_fingerprint": admission["spec_sha256"],
        "strategy_fingerprint": None,
        "source_fingerprint": source_fingerprint,
        "orders": replay.orders,
        "fills": replay.fills,
        "rejected": replay.rejected,
        "n_trades": len(replay.trades),
        "starting_equity": replay.starting_equity,
        "final_equity": replay.final_equity,
        "watermark": daily_watermark(study),
        "params": study.economics.model_dump(mode="json"),
        "control_relationship": "same-unit buy-once control; passive benchmark separate",
        "daily_rule": {
            "parent_run_id": parent_run_id,
            "role": role,
            "data_origin": study.data_origin,
            "query_sha256": study.query_sha256,
            "crypto_snapshot_id": study.snapshot_sha256,
        },
    }


def publish_daily_projections(
    data_dir: Path,
    parent_run_id: str,
    receipt: dict[str, Any],
    study: DailyRuleStudyV1,
    *,
    project_id: str,
    source_fingerprint: str,
) -> dict[str, object]:
    from alpha_cli._native_daily_rule_artifacts import validate_daily_economics

    economics = validate_daily_economics(study, receipt.get("economics"))
    snapshot_id, snapshot_hash, lineage = chart_snapshot(data_dir, study, create=True)
    admission = receipt["admission"]
    roles = {}
    for role in ("baseline", "control"):
        raw = economics[role]
        replay = TypeAdapter(BacktestResult).validate_python(raw)
        manifest = _manifest(
            project_id=project_id,
            parent_run_id=parent_run_id,
            admission=admission,
            role=role,
            raw=raw,
            study=study,
            snapshot_id=snapshot_id,
            snapshot_hash=snapshot_hash,
            source_fingerprint=source_fingerprint,
        )
        rdir = _artifacts.run_dir(data_dir, str(manifest["run_id"]))
        for name, payload in (("raw_result.json", raw), ("lineage.json", lineage)):

            def write_json(path: Path, text: str = canonical(payload)) -> None:
                path.write_text(text)

            _artifacts.publish_artifact(rdir / name, write_json)
        _artifacts.write_run_sidecars(
            rdir,
            equity=replay.equity_curve,
            trades=replay.trades,
            trace_result=replay,
            periods_per_year=365,
        )
        _artifacts.write_manifest(rdir, manifest)
        roles[role] = {
            "run_id": manifest["run_id"],
            "manifest_sha256": hashlib.sha256((rdir / "manifest.json").read_bytes()).hexdigest(),
        }
    return {
        "schema": "DailyRuleProjectionSelectorsV1",
        "parent_run_id": parent_run_id,
        "trial_id": admission["trial_id"],
        "crypto_snapshot_id": study.snapshot_sha256,
        "query_sha256": study.query_sha256,
        "chart_snapshot_id": snapshot_id,
        "chart_snapshot_hash": snapshot_hash,
        "roles": roles,
        "data_origin": study.data_origin,
        "scientific_acceptance": "not_admitted",
    }


def validate_daily_projections(
    data_dir: Path,
    selectors: object,
    receipt: dict[str, Any],
    study: DailyRuleStudyV1,
    *,
    project_id: str,
    parent_run_id: str,
    source_fingerprint: str,
    source_data_dir: Path | None = None,
) -> None:
    from alpha_cli._native_daily_rule_artifacts import same_artifact, validate_daily_economics

    economics = validate_daily_economics(study, receipt.get("economics"))
    snapshot_id, snapshot_hash, lineage = chart_snapshot(
        data_dir, study, create=False, source_data_dir=source_data_dir
    )
    if not isinstance(selectors, dict):
        raise DataError("daily projection selectors are missing")
    expected = {
        "schema": "DailyRuleProjectionSelectorsV1",
        "parent_run_id": parent_run_id,
        "trial_id": receipt["admission"]["trial_id"],
        "crypto_snapshot_id": study.snapshot_sha256,
        "query_sha256": study.query_sha256,
        "chart_snapshot_id": snapshot_id,
        "chart_snapshot_hash": snapshot_hash,
        "data_origin": study.data_origin,
        "scientific_acceptance": "not_admitted",
    }
    if canonical({key: value for key, value in selectors.items() if key != "roles"}) != canonical(
        expected
    ):
        raise DataError("daily projection selector identity changed")
    roles = selectors.get("roles")
    if not isinstance(roles, dict) or set(roles) != {"baseline", "control"}:
        raise DataError("daily projection selector roles changed")
    for role, reference in roles.items():
        manifest = _manifest(
            project_id=project_id,
            parent_run_id=parent_run_id,
            admission=receipt["admission"],
            role=role,
            raw=economics[role],
            study=study,
            snapshot_id=snapshot_id,
            snapshot_hash=snapshot_hash,
            source_fingerprint=source_fingerprint,
        )
        if (
            not isinstance(reference, dict)
            or set(reference) != {"run_id", "manifest_sha256"}
            or reference["run_id"] != manifest["run_id"]
        ):
            raise DataError("daily projection reference changed")
        rdir = _artifacts.find_run_dir(data_dir, str(manifest["run_id"]))
        if (
            rdir is None
            or hashlib.sha256((rdir / "manifest.json").read_bytes()).hexdigest()
            != reference["manifest_sha256"]
        ):
            raise DataError("daily projection manifest reference changed")
        actual = _artifacts.read_manifest(rdir)
        manifest.update(
            schema_version=MANIFEST_SCHEMA_VERSION,
            artifact_contract_version=ARTIFACT_CONTRACT_VERSION,
        )
        if canonical(
            {key: value for key, value in actual.items() if key != "artifacts"}
        ) != canonical(manifest):
            raise DataError("daily projection semantic manifest changed")
        if not same_artifact(
            rdir / "raw_result.json", canonical(economics[role]).encode()
        ) or not same_artifact(rdir / "lineage.json", canonical(lineage).encode()):
            raise DataError("daily projection numerical/source lineage changed")
        replay = TypeAdapter(BacktestResult).validate_python(economics[role])
        with tempfile.TemporaryDirectory(prefix="alpha-daily-sidecars-") as temporary:
            expected_root = Path(temporary)
            _artifacts.write_run_sidecars(
                expected_root,
                equity=replay.equity_curve,
                trades=replay.trades,
                trace_result=replay,
                periods_per_year=365,
            )
            for path in expected_root.iterdir():
                if not same_artifact(rdir / path.name, path.read_bytes()):
                    raise DataError("daily canonical sidecar differs from native result")
