"""Designed development controls, never market observations or engine-generated backtests."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

CaseKind = Literal["conditional", "indicator_null", "accounting_defect"]


def encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def synthetic_panel(kind: CaseKind) -> dict[str, Any]:
    if kind not in ("conditional", "indicator_null", "accounting_defect"):
        raise ValueError("unknown synthetic control")
    start = date(2020, 1, 1)
    rows: list[dict[str, Any]] = []
    equity = benchmark = 100.0
    for i in range(500):
        # Designed 90-interval loss episode; no seed selection or fitted threshold.
        if i:
            equity *= 0.99 if 181 <= i <= 270 else 1.004
            benchmark *= 0.995 if 181 <= i <= 270 else 1.002
        ts = (start + timedelta(days=i)).isoformat()
        rows.append(
            dict(
                ts=ts,
                available_at=ts,
                equity=equity,
                cash=equity,
                marked_position=0.0,
                benchmark=benchmark,
                risk_indicator=int(180 <= i < 270) if kind != "indicator_null" else i % 2,
            )
        )
    if kind == "accounting_defect":
        rows[220]["cash"] += 10.0
    return dict(
        schema_version=1,
        synthetic=True,
        mode="retrospective_diagnosis",
        cutoff=rows[-1]["ts"],
        rows=rows,
        sources=[
            dict(
                source_id="context-001",
                text="Synthetic scenario note: liquidity conditions "
                "changed. This is designed context, not a real historical event or causal proof.",
                event_date=rows[180]["ts"],
                publication_date=rows[181]["ts"],
                available_date=rows[181]["ts"],
                retrieved_date=rows[-1]["ts"],
            )
        ],
    )


def export_panel(panel: dict[str, Any], target: Path, cutoff: str) -> dict[str, str]:
    """Trusted synthetic-only exporter. Parent identity remains evaluator-side, not model input."""
    day = date.fromisoformat(cutoff)
    if day.isoformat() != cutoff or panel.get("synthetic") is not True:
        raise ValueError("only canonical dates and synthetic panels are supported")
    if target.exists():
        raise FileExistsError(target)
    exported = {
        **panel,
        "cutoff": cutoff,
        "rows": [
            r
            for r in panel["rows"]
            if date.fromisoformat(r["ts"]) <= day and date.fromisoformat(r["available_at"]) <= day
        ],
        "sources": [
            s
            for s in panel["sources"]
            if date.fromisoformat(s["event_date"]) <= day
            and date.fromisoformat(s["available_date"]) <= day
        ],
    }
    provenance = panel.get("indicator_provenance")
    if (
        provenance
        and provenance.get("available_date")
        and date.fromisoformat(provenance["available_date"]) > day
    ):
        exported["indicator_provenance"] = dict(
            kind="unavailable", available_date=None, definition="Unavailable at export cutoff."
        )
        exported["rows"] = [{**row, "risk_indicator": None} for row in exported["rows"]]
    raw = encode(exported)
    fingerprint = digest(raw)
    target.mkdir(parents=True, exist_ok=False)
    (target / "panel.json").write_bytes(raw)
    (target / "manifest.json").write_bytes(encode(dict(schema_version=1, panel_sha256=fingerprint)))
    return dict(parent_sha256=digest(encode(panel)), panel_sha256=fingerprint)
