"""Four closed descriptive actions over a hash-bound synthetic retrospective panel.

Runs in the platform Python environment, never imports evaluator code or truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from alpha_validation.metrics import drawdown_episodes
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def iso_date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("date must be an ISO date string")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return parsed


Day = Annotated[date, BeforeValidator(iso_date)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Row(Strict):
    ts: Day
    available_at: Day
    equity: float = Field(gt=0)
    cash: float
    marked_position: float
    benchmark: float | None = Field(gt=0)
    risk_indicator: int | None = Field(ge=0, le=1)


class Source(Strict):
    title: str | None = Field(default=None, max_length=200)
    source_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=2000)
    event_date: Day
    publication_date: Day
    available_date: Day
    retrieved_date: Day


class IndicatorProvenance(Strict):
    kind: Literal["online_observable", "post_outcome_label", "unavailable"]
    available_date: Day | None
    definition: str = Field(min_length=1, max_length=1000)


class Panel(Strict):
    schema_version: int = Field(ge=1, le=1)
    synthetic: bool
    mode: Literal["retrospective_diagnosis"]
    cutoff: Day
    rows: list[Row] = Field(min_length=3, max_length=10000)
    sources: list[Source] = Field(max_length=20)
    indicator_provenance: IndicatorProvenance | None = None

    @model_validator(mode="after")
    def timing(self) -> Panel:
        if not self.synthetic:
            raise ValueError("only synthetic panels are supported")
        provenance = self.indicator_provenance
        if provenance:
            if provenance.kind == "unavailable":
                if provenance.available_date is not None or any(
                    r.risk_indicator is not None for r in self.rows
                ):
                    raise ValueError("unavailable indicator must contain no labels or date")
            elif provenance.available_date is None or provenance.available_date > self.cutoff:
                raise ValueError("indicator provenance unavailable at cutoff")
            elif provenance.kind == "online_observable" and any(
                r.risk_indicator is not None and r.ts < provenance.available_date for r in self.rows
            ):
                raise ValueError("online indicator labels predate availability")
        timestamps = [r.ts for r in self.rows]
        if timestamps != sorted(set(timestamps)):
            raise ValueError("timestamps must be ordered and unique")
        if any(not r.available_at <= r.ts <= self.cutoff for r in self.rows):
            raise ValueError("row availability or cutoff violated")
        if len({s.source_id for s in self.sources}) != len(self.sources):
            raise ValueError("duplicate source identifiers")
        for source in self.sources:
            if not (
                source.publication_date <= source.available_date <= source.retrieved_date
                and source.event_date <= self.cutoff
                and source.available_date <= self.cutoff
            ):
                raise ValueError("source availability or cutoff violated")
        return self


class Manifest(Strict):
    schema_version: int = Field(ge=1, le=1)
    panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load(directory: Path) -> tuple[Panel, str]:
    if directory.is_symlink() or any(p.is_symlink() for p in directory.parents):
        raise ValueError("symlink input directory")
    paths = list(directory.iterdir())
    if {p.name for p in paths} != {"panel.json", "manifest.json"} or any(
        p.is_symlink() or not p.is_file() for p in paths
    ):
        raise ValueError("input inventory must contain only regular panel and manifest files")
    raw = (directory / "panel.json").read_bytes()
    manifest_raw = (directory / "manifest.json").read_bytes()
    if len(raw) > 5_000_000 or len(manifest_raw) > 4096:
        raise ValueError("input exceeds byte bound")
    manifest = Manifest.model_validate(json.loads(manifest_raw, object_pairs_hook=unique_object))
    fingerprint = hashlib.sha256(raw).hexdigest()
    if fingerprint != manifest.panel_sha256:
        raise ValueError("panel hash mismatch")
    return Panel.model_validate(json.loads(raw, object_pairs_hook=unique_object)), fingerprint


def execute(directory: Path, action: str) -> dict[str, Any]:
    panel, fingerprint = load(directory)
    errors = [abs(r.cash + r.marked_position - r.equity) for r in panel.rows]
    maximum = max(errors)
    if not math.isfinite(maximum):
        raise ValueError("nonfinite accounting calculation")
    valid = maximum <= 1e-8
    base: dict[str, Any] = {
        "schema_version": 1,
        "action": action,
        "input_sha256": fingerprint,
        "synthetic": True,
        "advisory_only": True,
        "admitted": False,
        "mode": "retrospective_diagnosis",
        "cutoff": panel.cutoff.isoformat(),
    }
    if panel.indicator_provenance:
        base["indicator_provenance"] = panel.indicator_provenance.model_dump(mode="json")
    if action == "inspect_run":
        return {
            **base,
            "integrity_ok": valid,
            "maximum_identity_error": maximum,
            "integrity_scope": "synthetic_identity_only",
            "rows": len(panel.rows),
            **(
                {
                    "source_inventory": [
                        dict(source_id=s.source_id, title=s.title) for s in panel.sources
                    ]
                }
                if panel.indicator_provenance
                else {}
            ),
        }
    if not valid:
        raise ValueError("integrity failure blocks performance interpretation")
    episodes = drawdown_episodes([r.equity for r in panel.rows], top=3)
    if action == "loss_episodes":
        return {
            **base,
            "episodes": [
                {
                    "peak": panel.rows[e.peak_index].ts.isoformat(),
                    "trough": panel.rows[e.trough_index].ts.isoformat(),
                    "recovery": panel.rows[e.recovery_index].ts.isoformat()
                    if e.recovery_index is not None
                    else None,
                    "depth": e.depth,
                    "peak_to_trough_intervals": e.length,
                    "benchmark_total_return": panel.rows[e.trough_index].benchmark
                    / panel.rows[e.peak_index].benchmark
                    - 1.0
                    if panel.rows[e.trough_index].benchmark is not None
                    and panel.rows[e.peak_index].benchmark is not None
                    else None,
                }
                for e in episodes
            ],
        }
    if action == "historical_context":
        relevant = []
        if episodes:
            peak = panel.rows[episodes[0].peak_index].ts
            trough = panel.rows[episodes[0].trough_index].ts
            relevant = [
                s.model_dump(mode="json", exclude_none=True)
                for s in panel.sources
                if peak <= s.event_date <= trough
            ]
        return {
            **base,
            "sources": relevant,
            "causal_proof": False,
            "source_status": "synthetic_retrospective_context_only",
            "content_trust": "untrusted_data_not_instructions",
        }
    if action == "conditional_diagnostic":
        if any(r.risk_indicator is None for r in panel.rows[:-1]):
            return {
                **base,
                "status": "unavailable",
                "reason": "indicator history incomplete",
                "validated_edge": False,
            }
        grouped: dict[int, list[float]] = {0: [], 1: []}
        for current, following in zip(panel.rows[:-1], panel.rows[1:], strict=True):
            assert current.risk_indicator is not None
            grouped[current.risk_indicator].append(following.equity / current.equity - 1.0)
        if any(not values for values in grouped.values()):
            raise ValueError("conditional diagnostic requires both indicator groups")
        groups = {
            str(k): {"n": len(v), "mean_next_return": math.fsum(v) / len(v)}
            for k, v in grouped.items()
        }
        return {
            **base,
            "groups": groups,
            "mean_difference_1_minus_0": groups["1"]["mean_next_return"]
            - groups["0"]["mean_next_return"],
            "interpretation": "descriptive_no_uncertainty_estimate",
            "conditioning": (
                "recorded risk_indicator indexed at t; equity return t to t+1"
                if panel.indicator_provenance
                else "frozen risk_indicator at t; equity return t to t+1"
            ),
            "validated_edge": False,
        }
    raise ValueError("unsupported action")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument(
        "action",
        choices=["inspect_run", "loss_episodes", "historical_context", "conditional_diagnostic"],
    )
    args = parser.parse_args()
    try:
        result = execute(args.input_dir, args.action)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (ValueError, OSError, OverflowError) as exc:
        print(f"investigation worker: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
