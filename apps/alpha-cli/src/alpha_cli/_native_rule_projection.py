"""Canonical chart/report projections of the SAME completed synthetic trial."""

from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import TypeAdapter

from alpha_backtest.results import BacktestResult
from alpha_cli import _artifacts
from alpha_cli._native_rule_economics import fixed_costed_study, validate_costed_result
from alpha_cli._native_rule_protocol import canonical, sha
from alpha_cli.artifact_contract import ARTIFACT_CONTRACT_VERSION, MANIFEST_SCHEMA_VERSION
from alpha_core import DataError
from alpha_data.snapshot import create_snapshot, snapshot_manifest_hash
from alpha_data.store import ParquetStore


def _snapshot(data_dir: Path, *, create: bool = True) -> tuple[str, str]:
    study = fixed_costed_study().to_dict()
    rows = study["bars"]
    assert isinstance(rows, list)
    frame = pl.DataFrame(
        {
            "ts": [datetime.fromisoformat(row[0]) for row in rows],
            **{
                name: [row[i] for row in rows]
                for i, name in enumerate(("open", "high", "low", "close", "volume"), 1)
            },
        }
    )
    snapshot_id = "synthetic-rule-" + str(study["data_sha256"])[:16]
    path = data_dir / "snapshots" / snapshot_id
    if not path.exists() and not create:
        raise DataError("costed synthetic snapshot is missing")
    # Reuse the canonical publisher to derive this closed fixture's entire identity.
    # File self-consistency alone does not bind source/cutoff/provenance or exclude
    # extra symbols/actions. Never repair or relabel an existing snapshot.
    with tempfile.TemporaryDirectory(prefix="alpha-rule-snapshot-") as temporary:
        temporary_root = Path(temporary)
        store = ParquetStore(temporary_root / "source")
        store.write_bars("RULES", frame)
        store.write_provenance(
            "RULES",
            source="synthetic:fixed-rule-costed-v1",
            adapter_version="1",
            parser_version="1",
        )
        expected_root = temporary_root / "snapshots"
        destinations = [expected_root]
        if not path.exists():
            destinations.append(data_dir / "snapshots")
        for destination in destinations:
            create_snapshot(
                store,
                destination,
                snapshot_id,
                ["RULES"],
                source="synthetic:fixed-rule-costed-v1",
                adapter_version="1",
                parser_version="1",
                created_at=datetime.fromisoformat(str(study["cutoff"])),
            )
        expected_digest = snapshot_manifest_hash(expected_root / snapshot_id)
    digest = snapshot_manifest_hash(path)
    if digest != expected_digest:
        raise DataError("costed synthetic snapshot differs from its canonical fixed lineage")
    if not ParquetStore(path).read_bars("RULES").equals(frame):
        raise DataError("costed synthetic snapshot differs from disclosed warmup/execution rows")
    return snapshot_id, digest


def _same_json(actual: object, expected: object) -> bool:
    try:
        return canonical(actual) == canonical(expected)
    except (TypeError, ValueError):
        return False


def _projection_manifest(
    *,
    parent_run_id: str,
    trial_id: str,
    role: str,
    raw: object,
    replay: BacktestResult,
    snapshot_id: str,
    snapshot_hash: str,
    execution_fingerprint: str,
    source_fingerprint: str,
) -> dict[str, Any]:
    """One closed semantic manifest for both publication and mechanical verification."""
    identity = {
        "schema": "SyntheticRuleProjectionV1",
        "parent_run_id": parent_run_id,
        "trial_id": trial_id,
        "role": role,
        "result_sha256": sha(raw),
        "snapshot_hash": snapshot_hash,
    }
    return {
        **identity,
        "run_id": sha(identity)[:16],
        "run_identity_version": 3,
        "command": "research_rule_projection_v1",
        "kind": "research",
        "scope": "research_only",
        "symbol": "RULES",
        "snapshot_id": snapshot_id,
        "snapshot_hash": snapshot_hash,
        "research_cutoff": "2000-01-08T00:00:00+00:00",
        "scientific_acceptance": "not_admitted",
        "synthetic": True,
        "real_market_evidence": False,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "execution_fingerprint": execution_fingerprint,
        "strategy_fingerprint": None,
        "source_fingerprint": source_fingerprint,
        "orders": replay.orders,
        "fills": replay.fills,
        "rejected": replay.rejected,
        "n_trades": len(replay.trades),
        "starting_equity": replay.starting_equity,
        "final_equity": replay.final_equity,
        "watermark": "SYNTHETIC ENGINEERING ONLY",
        "params": fixed_costed_study().to_dict()["economics"],
        "control_relationship": "predeclared flat control; passive engine benchmark is separate",
    }


def publish_projections(
    data_dir: Path, parent_run_id: str, receipt: dict[str, Any], *, source_fingerprint: str
) -> dict[str, object]:
    economics = validate_costed_result(receipt.get("economics"))
    snapshot_id, snapshot_hash = _snapshot(data_dir)
    admission = receipt["admission"]
    result = {}
    for role in ("baseline", "control"):
        raw = economics[role]
        replay = TypeAdapter(BacktestResult).validate_python(raw)
        manifest = _projection_manifest(
            parent_run_id=parent_run_id,
            trial_id=admission["trial_id"],
            role=role,
            raw=raw,
            replay=replay,
            snapshot_id=snapshot_id,
            snapshot_hash=snapshot_hash,
            execution_fingerprint=admission["spec_sha256"],
            source_fingerprint=source_fingerprint,
        )
        run_id = str(manifest["run_id"])
        rdir = _artifacts.run_dir(data_dir, run_id)

        def write_raw(path: Path, text: str = canonical(raw)) -> None:
            path.write_text(text)

        _artifacts.publish_artifact(rdir / "raw_result.json", write_raw)
        _artifacts.write_run_sidecars(
            rdir,
            equity=replay.equity_curve,
            trades=replay.trades,
            trace_result=replay,
            periods_per_year=252,
        )
        _artifacts.write_manifest(rdir, manifest)
        result[role] = {
            "run_id": run_id,
            "manifest_sha256": hashlib.sha256((rdir / "manifest.json").read_bytes()).hexdigest(),
        }
    return {
        "schema": "SyntheticRuleProjectionSelectorsV1",
        "parent_run_id": parent_run_id,
        "trial_id": admission["trial_id"],
        "snapshot_id": snapshot_id,
        "snapshot_hash": snapshot_hash,
        "roles": result,
        "scientific_acceptance": "not_admitted",
    }


def validate_projections(
    data_dir: Path,
    selectors: object,
    receipt: dict[str, Any],
    *,
    parent_run_id: str,
    source_fingerprint: str,
) -> None:
    """Verify projections against the already verified parent and captured native receipt."""
    if not isinstance(selectors, dict) or set(selectors) != {
        "schema",
        "parent_run_id",
        "trial_id",
        "snapshot_id",
        "snapshot_hash",
        "roles",
        "scientific_acceptance",
    }:
        raise DataError("costed result requires its exact projection selectors")
    snapshot_id, snapshot_hash = _snapshot(data_dir, create=False)
    expected_selector_identity = {
        "schema": "SyntheticRuleProjectionSelectorsV1",
        "parent_run_id": parent_run_id,
        "trial_id": receipt["admission"]["trial_id"],
        "snapshot_id": snapshot_id,
        "snapshot_hash": snapshot_hash,
        "scientific_acceptance": "not_admitted",
    }
    if not _same_json(
        {key: value for key, value in selectors.items() if key != "roles"},
        expected_selector_identity,
    ):
        raise DataError("costed projection selector identity changed")
    roles = selectors["roles"]
    if not isinstance(roles, dict) or set(roles) != {"baseline", "control"}:
        raise DataError("costed projection roles changed")
    economics = validate_costed_result(receipt.get("economics"))
    for role, reference in roles.items():
        replay = TypeAdapter(BacktestResult).validate_python(economics[role])
        expected_manifest = _projection_manifest(
            parent_run_id=parent_run_id,
            trial_id=receipt["admission"]["trial_id"],
            role=role,
            raw=economics[role],
            replay=replay,
            snapshot_id=snapshot_id,
            snapshot_hash=snapshot_hash,
            execution_fingerprint=receipt["admission"]["spec_sha256"],
            source_fingerprint=source_fingerprint,
        )
        if (
            not isinstance(reference, dict)
            or set(reference) != {"run_id", "manifest_sha256"}
            or reference["run_id"] != expected_manifest["run_id"]
            or type(reference["manifest_sha256"]) is not str
        ):
            raise DataError("costed projection reference identity or shape changed")
        rdir = _artifacts.find_run_dir(data_dir, str(expected_manifest["run_id"]))
        if (
            rdir is None
            or hashlib.sha256((rdir / "manifest.json").read_bytes()).hexdigest()
            != reference["manifest_sha256"]
        ):
            raise DataError("costed projection manifest reference changed")
        manifest = _artifacts.read_manifest(rdir)
        expected_manifest.update(
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
            }
        )
        if not _same_json(
            {key: value for key, value in manifest.items() if key != "artifacts"}, expected_manifest
        ):
            raise DataError("costed projection semantic manifest differs from its native trial")
        if (rdir / "raw_result.json").read_text() != canonical(economics[role]):
            raise DataError("costed projection differs from its single native trial")

        with tempfile.TemporaryDirectory(prefix="alpha-rule-projection-verify-") as temporary:
            expected = Path(temporary)
            _artifacts.write_run_sidecars(
                expected,
                equity=replay.equity_curve,
                trades=replay.trades,
                trace_result=replay,
                periods_per_year=252,
            )
            for artifact in expected.iterdir():
                if (rdir / artifact.name).read_bytes() != artifact.read_bytes():
                    raise DataError(
                        "canonical projection sidecar differs from raw numerical result"
                    )
