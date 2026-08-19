"""Bounded research-only data audits (spec §8.3, ADR-0023).

A data audit DESCRIBES a registered research dataset — coverage, gaps, distributions,
seasonality, causal regime tags, effective sample — and publishes the result as an
immutable EXPLORATORY run. It estimates no hypothesis effect and is admissible only to
the Evidence Hub's data dimension. Loading is fail-closed: the dataset's registered
origin hash must still match the bytes on disk, or the audit refuses to run.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Final

import polars as pl

from alpha_cli import _artifacts
from alpha_core import DataError
from alpha_data.pit import PointInTimeReader
from alpha_data.snapshot import verify_snapshot
from alpha_data.store import ParquetStore
from alpha_research import (
    AR1_EFFECTIVE_SAMPLE_SIZE_METHOD_VERSION,
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
    autocorrelation,
    coverage_summary,
    effective_sample_size,
    render_research_line_chart,
    return_distribution,
    seasonality_by_weekday,
    volatility_regime_tags,
)

_PROJECT_ID: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_MINIMUM_USABLE_SAMPLE: Final = 30
_REGIME_WINDOW: Final = 10


def _sha(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _publish_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False), encoding="utf-8"
    )


def _parse_bound(value: object, label: str, *, end_of_day: bool) -> datetime:
    if not isinstance(value, str) or not value:
        raise DataError(f"research data audit requires a {label} timestamp")
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError as exc:
        raise DataError(f"research data audit {label} must be an ISO date") from exc
    # The start bound opens its calendar day (a midnight-stamped daily bar on the start
    # date belongs to the range); the end bound is an inclusive as-of day cutoff.
    bound_time = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(parsed, bound_time, tzinfo=UTC)


def _verified_root(data_dir: Path, ref: Mapping[str, object]) -> Path:
    """Resolve the dataset's store root, refusing if registered bytes have drifted."""
    origin = ref.get("origin")
    if not isinstance(origin, Mapping):
        raise DataError("research dataset ref has no origin binding")
    kind = ref.get("dataset_kind")
    if kind == "snapshot":
        snapshot_id = str(origin.get("snapshot_id"))
        root = data_dir / "snapshots" / snapshot_id
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise DataError(f"registered snapshot {snapshot_id!r} is missing its manifest")
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if digest != origin.get("manifest_sha256"):
            raise DataError(
                f"snapshot {snapshot_id!r} no longer matches its registered manifest hash; "
                "re-register the dataset before auditing"
            )
        # The manifest hash alone does not cover the payload files: re-hash every
        # snapshot file so drifted or corrupted bytes fail closed as a typed error
        # instead of leaking an untyped parquet parse failure downstream.
        verify_snapshot(root)
        return root
    if kind == "store_slice":
        root = data_dir / "store"
        store = ParquetStore(root)
        provenance_path = store._provenance_path(  # noqa: SLF001 - CLI/store projection seam
            str(ref.get("instrument"))
        )
        if not provenance_path.is_file():
            raise DataError("registered store slice has no provenance sidecar on disk")
        digest = hashlib.sha256(provenance_path.read_bytes()).hexdigest()
        if digest != origin.get("provenance_sha256"):
            raise DataError(
                "store provenance no longer matches the registered hash; the canonical "
                "store changed — re-register the dataset before auditing"
            )
        return root
    raise DataError(
        f"research data audits for {kind!r} datasets arrive with the qualified-loading lane"
    )


def load_registered_dataset_frame(data_dir: Path, *, ref: Mapping[str, object]) -> Any:
    """Load a registered dataset's exact PIT slice after fail-closed origin verification."""
    ref_id = str(ref.get("ref_id", ""))
    if not ref_id.startswith("rd_"):
        raise DataError("registered dataset loading requires a research dataset ref")
    instrument = str(ref.get("instrument", ""))
    start_at = _parse_bound(ref.get("start_ts"), "start_ts", end_of_day=False)
    end_at = _parse_bound(ref.get("end_ts"), "end_ts", end_of_day=True)
    if end_at < start_at:
        raise DataError("registered dataset range must end at or after its start")
    origin = ref.get("origin")
    if isinstance(origin, Mapping) and origin.get("snapshot_schema") == "CryptoSnapshotV1":
        snapshot_id = str(origin.get("snapshot_id", ""))
        manifest_path = Path(data_dir) / "crypto" / "snapshots" / f"{snapshot_id}.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise DataError(f"registered crypto snapshot {snapshot_id!r} is missing its manifest")
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != origin.get("manifest_sha256"):
            raise DataError("crypto snapshot no longer matches its registered manifest hash")
        from alpha_cli.crypto_data_cmds import (  # noqa: PLC0415 - optional crypto audit lane
            crypto_crowding_observations,
        )

        observations = crypto_crowding_observations(snapshot_id)
        return pl.DataFrame(
            {
                "ts": [row.funding_time for row in observations],
                "funding_rate": [row.funding_rate for row in observations],
            },
            schema={"ts": pl.Datetime(time_zone="UTC"), "funding_rate": pl.Float64},
        ).filter(pl.col("ts").is_between(start_at, end_at, closed="both"))
    root = _verified_root(Path(data_dir), ref)
    store = ParquetStore(root)
    reader = PointInTimeReader(store, {instrument: store.read_actions(instrument)})
    frame = reader.as_of(instrument, end_at)
    return frame.filter(frame["ts"] >= start_at)


def run_data_audit(data_dir: Path, *, project_id: str, ref: Mapping[str, object]) -> dict[str, Any]:
    """Audit one registered dataset and publish the immutable EXPLORATORY run."""
    if _PROJECT_ID.fullmatch(project_id) is None:
        raise DataError("research data audit requires a canonical project_id")
    ref_id = str(ref.get("ref_id", ""))
    if not ref_id.startswith("rd_"):
        raise DataError("research data audit requires a registered dataset ref")
    instrument = str(ref.get("instrument", ""))
    frame = load_registered_dataset_frame(Path(data_dir), ref=ref)
    if frame.height == 0:
        raise DataError(
            f"registered dataset {ref_id!r} holds no observations for {instrument!r} in its range"
        )
    timestamps = list(frame["ts"])
    crypto_snapshot = "funding_rate" in frame.columns
    value_column = "funding_rate" if crypto_snapshot else "close"
    values = [float(value) for value in frame[value_column]]

    interval_seconds = 8 * 3_600.0 if crypto_snapshot else 86_400.0
    duration = ref.get("bar_duration_minutes")
    if isinstance(duration, int) and not isinstance(duration, bool) and duration > 0:
        interval_seconds = duration * 60.0
    coverage = coverage_summary(timestamps, expected_interval_seconds=interval_seconds)
    notes: list[str] = []
    blocking: list[str] = []
    limiting: list[str] = []
    if int(coverage["n"]) < _MINIMUM_USABLE_SAMPLE:  # type: ignore[call-overload]
        blocking.append(
            f"insufficient sample: n={coverage['n']} < {_MINIMUM_USABLE_SAMPLE} observations"
        )
    if int(coverage["duplicate_count"]) > 0:  # type: ignore[call-overload]
        blocking.append(f"{coverage['duplicate_count']} duplicate timestamps")
    if int(coverage["disorder_count"]) > 0:  # type: ignore[call-overload]
        blocking.append(f"{coverage['disorder_count']} out-of-order timestamps")
    if int(coverage["gap_count"]) > 0:  # type: ignore[call-overload]
        limiting.append(f"{coverage['gap_count']} calendar gaps beyond twice the cadence")

    descriptives: dict[str, object] = {"coverage": coverage}
    if len(values) >= 2:
        if crypto_snapshot:
            distribution = {
                "n": len(values),
                "mean": sum(values) / len(values),
                "minimum": min(values),
                "maximum": max(values),
            }
            descriptives["funding_rate_distribution"] = distribution
            n_observations = len(values)
        else:
            distribution = return_distribution(values)
            descriptives["return_distribution"] = distribution
            n_observations = int(distribution["n"])
        if n_observations >= 3:
            autocorrelation_values = (
                values
                if crypto_snapshot
                else [b / a - 1.0 for a, b in zip(values, values[1:], strict=False)]
            )
            rows = autocorrelation(
                autocorrelation_values,
                lags=(1,),
            )
            rho = float(rows[0]["autocorrelation"])
            descriptives["autocorrelation"] = rows
            descriptives["effective_sample_size"] = effective_sample_size(n_observations, rho)
            descriptives["effective_sample_size_method_version"] = (
                AR1_EFFECTIVE_SAMPLE_SIZE_METHOD_VERSION
            )
        if crypto_snapshot:
            descriptives["seasonality_by_weekday"] = seasonality_by_weekday(timestamps, values)
            notes.append(
                "funding-rate levels audited; no price return or hypothesis effect estimated"
            )
        else:
            returns = [b / a - 1.0 for a, b in zip(values, values[1:], strict=False)]
            descriptives["seasonality_by_weekday"] = seasonality_by_weekday(timestamps[1:], returns)
            if len(returns) >= _REGIME_WINDOW + 2:
                tags = volatility_regime_tags(returns, window=_REGIME_WINDOW)
                descriptives["volatility_regime_counts"] = {
                    tag: tags.count(tag) for tag in ("warmup", "low", "mid", "high")
                }
            else:
                notes.append("volatility regime tagging skipped: sample below the trailing window")
    else:
        notes.append("distributional descriptives skipped: fewer than two bars")

    summary = {
        "audit_schema": "ResearchDataAuditV1",
        "method_version": AR1_EFFECTIVE_SAMPLE_SIZE_METHOD_VERSION,
        "blocking_count": len(blocking),
        "limiting_count": len(limiting),
        "notes": [*blocking, *limiting, *notes],
    }
    dataset_hash = _sha(
        {
            "timestamps": [stamp.isoformat() for stamp in timestamps],
            value_column: values,
        }
    )
    origin_value = ref.get("origin")
    run_identity = {
        "command": "research_data_audit",
        "project_id": project_id,
        "ref_id": ref_id,
        "origin": dict(origin_value) if isinstance(origin_value, Mapping) else {},
        "dataset_hash": dataset_hash,
        "method_version": AR1_EFFECTIVE_SAMPLE_SIZE_METHOD_VERSION,
    }
    run_id = _sha(run_identity)[:16]
    run_dir = _artifacts.run_dir(Path(data_dir), run_id)
    chart = ResearchChartData(
        chart_id="data-audit-closes",
        title=f"Data audit: {instrument} {value_column.replace('_', ' ')} coverage",
        x_label="Bar timestamp (UTC)",
        y_label="Funding rate" if crypto_snapshot else "Close",
        evidence_phase="exploratory",
        dataset_sha256=dataset_hash,
        protocol_sha256=_sha(dict(summary)),
        question="Is this registered dataset complete and healthy enough for research?",
        plain_language_answer=(
            "Blocked by the findings above."
            if blocking
            else "No blocking findings; limitations, if any, are listed."
        ),
        sample_size=len(values),
        effective_sample_size=float(
            descriptives.get("effective_sample_size", len(values))  # type: ignore[arg-type]
        ),
        uncertainty="Descriptive audit; no hypothesis effect is estimated.",
        caveat="A data audit validates data, never a market claim.",
        run_id=run_id,
        artifact_id="data-audit-close-series",
        artifact_sha256=_sha(values),
        series=(
            ResearchChartSeries(
                series_id="close",
                label=f"{instrument} {value_column.replace('_', ' ')}",
                unit="rate" if crypto_snapshot else "price",
                points=tuple(
                    ResearchChartPoint(ts=stamp, value=value)
                    for stamp, value in zip(timestamps, values, strict=True)
                ),
            ),
        ),
    )
    _publish_json(run_dir / "descriptives.json", descriptives)
    _publish_json(run_dir / "audit-summary.json", summary)
    _publish_json(run_dir / "chart-data.json", chart.to_dict())
    (run_dir / "coverage.png").write_bytes(render_research_line_chart(chart))
    (run_dir / "report.md").write_text(
        "# Research Data Audit\n\n"
        "**EXPLORATORY — DESCRIBES DATA, NEVER A MARKET CLAIM**\n\n"
        f"Dataset `{ref_id}` ({instrument}): {len(values)} observations audited. "
        f"Blocking findings: {len(blocking)}. Limiting findings: {len(limiting)}.\n",
        encoding="utf-8",
    )
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "research_data_audit",
        "kind": "research",
        "project_id": project_id,
        "dataset_ref_id": ref_id,
        "dataset_kind": ref.get("dataset_kind"),
        "instrument": instrument,
        "watermark": "EXPLORATORY",
        "real_market_evidence": False,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "research_only": True,
        "research_data_audit_method_version": AR1_EFFECTIVE_SAMPLE_SIZE_METHOD_VERSION,
        "audit_summary": summary,
        "snapshot_id": origin_value.get("snapshot_id")
        if crypto_snapshot and isinstance(origin_value, Mapping)
        else None,
        "snapshot_hash": origin_value.get("manifest_sha256")
        if crypto_snapshot and isinstance(origin_value, Mapping)
        else None,
        "execution_fingerprint": _sha(run_identity),
        "strategy_fingerprint": None,
        "source_fingerprint": dataset_hash,
        "dataset_hash": dataset_hash,
    }
    _artifacts.write_manifest(run_dir, manifest)
    return {"manifest": _artifacts.read_manifest(run_dir), "summary": summary}


__all__ = ["load_registered_dataset_frame", "run_data_audit"]
