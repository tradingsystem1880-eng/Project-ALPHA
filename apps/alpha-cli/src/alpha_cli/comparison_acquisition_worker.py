"""Private acquisition worker; provider credentials never enter Codex's model process."""

from __future__ import annotations

import json
import signal
import sys
from pathlib import Path
from typing import Any

from alpha_cli.comparison_acquisition import AcquisitionPlan, _read, _write
from alpha_core import DataError
from alpha_data.adapters.base import FetchResult
from alpha_data.adapters.tiingo_adapter import TiingoAdapter
from alpha_data.pipeline import stage_and_promote
from alpha_data.store import ParquetStore


def _fetch(plan: AcquisitionPlan, index: int, limit: int) -> FetchResult:
    item = plan.series[index]
    return TiingoAdapter(
        canonical_symbol=item.symbol,
        asset_class=item.asset_class,
        venue=item.venue,
        calendar=item.calendar,
        currency=item.currency,
    ).fetch(item.symbol, plan.start, plan.end, max_response_bytes=limit)


def perform_request(root: Path, index: int) -> dict[str, Any]:
    request = _read(root / "request.json")
    plan = AcquisitionPlan.model_validate_json(json.dumps(request["plan"]))
    if not 0 <= index < len(plan.series):
        raise DataError("acquisition request index outside reserved batch")
    result = _fetch(plan, index, request["max_response_bytes"])
    item = plan.series[index]
    if result.symbol != item.symbol:
        raise DataError("provider changed acquisition symbol")
    outcome = stage_and_promote(
        ParquetStore(root / "data/store"), result, authoritative_source="tiingo"
    )
    dates = {ts.date().isoformat() for ts in result.bars["ts"].to_list()}
    if not set(request["required_dates"]) <= dates:
        raise DataError("provider data missing exact parent drawdown endpoint dates")
    if any(ts.time().isoformat() != "00:00:00" for ts in result.bars["ts"].to_list()):
        raise DataError("comparison acquisition requires UTC daily session labels")
    return dict(
        status="succeeded",
        symbol=item.symbol,
        receipt_id=outcome.receipt_id,
        quality_path=str(outcome.quality_path.relative_to(root)),
    )


def main() -> None:
    # The child also expires if its supervising process dies.
    signal.alarm(90)
    root, index = Path(sys.argv[1]), int(sys.argv[2])
    try:
        result = perform_request(root, index)
    except (DataError, ValueError, OSError) as exc:
        result = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": "provider request or qualification failed",
        }
    _write(root / f"attempt-{index}.json", result)
    signal.alarm(0)


if __name__ == "__main__":
    main()
