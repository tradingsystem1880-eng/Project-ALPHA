"""Direct artificial worker economics, independent of native/market admission."""

from __future__ import annotations

import copy
import json
import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


def _study() -> dict[str, Any]:
    # Twenty past closes prime history without creating a target. The subsequent
    # 12,15,5,11,5,5 path yields long,long,flat,long,flat,flat against lag20=10.
    rows = [
        [
            (datetime(2000, 1, 1, tzinfo=UTC) + timedelta(days=i)).isoformat(),
            float(p),
            float(p + 1),
            float(p - 1),
            float(p),
            10000.0,
        ]
        for i, p in enumerate([10] * 20 + [12, 15, 5, 11, 5, 5])
    ]
    query = {
        "rows": [
            dict(
                zip(("open_time", "open", "high", "low", "close", "base_volume"), row, strict=True)
            )
            for row in rows
        ]
    }
    return {
        "schema": "FrozenDailyRuleStudyV1",
        "symbol": "BTC/USDT",
        "data_origin": "artificial_fixture",
        "query_document": json.dumps(query),
        "bars": rows,
        "discovery_end_exclusive": "2000-01-27T00:00:00+00:00",
        "warmup_bars": 20,
        "rules_spec": '{"history":21,"long_when":[{"left":{"source":"close"},"op":">",'
        '"right":{"source":"close","lag":20}}],"name":"worker-fixture",'
        '"short_when":[],"version":1}',
        "economics": {
            "price_precision": 2,
            "quantity_precision": 6,
            "quantity_increment_btc": 0.000001,
            "fixed_quantity_btc": 0.05,
            "spread_bps_full": 0,
            "slippage_bps_per_side": 0,
            "starting_cash": 10000.0,
            "fee_bps_per_side": 10,
        },
        "claim_scope": "exploratory_reconstructed_discovery_history",
    }


def _execute(study: dict[str, Any]) -> dict[str, Any]:
    namespace = runpy.run_path(str(Path(__file__).parents[2] / "workers/rdagent/costed_probe.py"))
    result = namespace["execute"](study)
    assert isinstance(result, dict)
    return result


def test_daily_worker_uses_primed_fixed_units_actual_cash_and_buy_hold_control() -> None:
    result = _execute(_study())
    assert result["schema"] == "DailyRuleReplayResultV1"
    assert result["real_market_evidence"] is False
    assert result["data_origin"] == "artificial_fixture"
    assert result["scientific_acceptance"] == "not_admitted"
    assert [fill["ts"] for fill in result["baseline"]["fill_trace"]] == [
        "2000-01-22T00:00:00.000001+00:00",
        "2000-01-24T00:00:00.000001+00:00",
        "2000-01-25T00:00:00.000001+00:00",
        "2000-01-26T00:00:00.000001+00:00",
    ]
    assert result["baseline"]["equity_curve"][-1][1] == pytest.approx(9999.7982, abs=1e-8)
    assert result["control"]["fills"] == 1
    assert result["control"]["equity_curve"][-1][1] == pytest.approx(9999.49925, abs=1e-8)
    fills = [row for row in result["accounting"]["baseline"] if row["event"] == "fill"]
    assert [row["cash"] for row in fills] == pytest.approx(
        [9999.24925, 9999.7987, 9999.54845, 9999.7982], abs=1e-8
    )
    assert [row["position_units"] for row in fills] == pytest.approx([0.05, 0, 0.05, 0])
    assert fills[-1]["fees_total"] == pytest.approx(0.0018)


def test_rejected_control_publishes_zero_activity_inconclusive_without_later_entry() -> None:
    study = _study()
    study["economics"]["starting_cash"] = 0.75
    result = _execute(study)
    assert result["outcome"] == "accounting_rejection_inconclusive"
    assert result["control"]["fills"] == 0
    assert result["control"]["orders"] == 0
    assert result["control"]["rejected"] == 1
    assert len(result["control"]["execution_rejections"]) == 1
    assert all(row["cash"] == pytest.approx(0.75) for row in result["accounting"]["control"])
    assert all(row["position_units"] == pytest.approx(0) for row in result["accounting"]["control"])


@pytest.mark.parametrize("mutation", ["bars", "origin", "schema"])
def test_worker_rejects_changed_pinned_rows_origin_or_unknown_schema(mutation: str) -> None:
    study = copy.deepcopy(_study())
    if mutation == "bars":
        study["bars"][20][4] = 999
    elif mutation == "origin":
        study["data_origin"] = "real"
    else:
        study["schema"] = "UnknownStudy"
    with pytest.raises(ValueError, match="unsupported|admitted"):
        _execute(study)
