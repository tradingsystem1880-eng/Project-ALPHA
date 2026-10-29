"""One explicit synthetic costed replay request; never a real study default."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import TypeAdapter, ValidationError

from alpha_backtest.results import BacktestResult
from alpha_cli._native_rule_study import _CONTROL, _RULE
from alpha_core import DataError


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def economics_document() -> dict[str, object]:
    start = datetime(2000, 1, 1, tzinfo=UTC)
    bars = [
        [
            (start + timedelta(days=i)).isoformat(),
            float(price),
            float(price + 1),
            float(price - 1),
            float(price),
            10000.0,
        ]
        for i, price in enumerate((6, 8, 12, 10, 16, 8, 8))
    ]
    data_hash = hashlib.sha256(canonical(bars).encode()).hexdigest()
    return {
        "schema": "FrozenRuleCostedReplaySyntheticV1",
        "capability": "frozen_rule_costed_replay_v1",
        "rules_spec": _RULE,
        "control_spec": _CONTROL,
        "bars": bars,
        "warmup_bars": 1,
        "cutoff": "2000-01-08T00:00:00+00:00",
        "provider": "synthetic",
        "symbol": "RULES",
        "venue": "SIM",
        "timeframe": "1d",
        "timezone": "UTC",
        "timestamp_semantics": "session_open_close_at_plus_23h",
        "data_sha256": data_hash,
        "price_unit": "USD",
        "signal_unit": "position",
        "horizon_bars": 1,
        "economics": {
            "starting_cash": 12000.0,
            "capital": 12000.0,
            "currency": "USD",
            "account_type": "CASH",
            "vol_window": 2,
            "target_vol": 1.0,
            "max_leverage": 0.1,
            "rebalance_every": 1,
            "periods_per_year": 252,
            "allow_short": False,
            "size_on_equity": False,
            "halt_drawdown": None,
            "fee_bps": 10.0,
            "slippage_bps": 100.0,
            "price_precision": 2,
            "size_precision": 0,
            "fill_timing": "next_session_open",
            "terminal_liquidation": False,
            "dividends": [],
        },
        "required_outputs": [
            "decision_trace",
            "orders",
            "fills",
            "portfolio_state",
            "trades",
            "equity_curve",
            "baseline_control_comparison",
        ],
        "outcome_policy": "synthetic_engineering_only_no_market_inference",
        "scientific_acceptance": "not_admitted",
        "authority": "none",
    }


@dataclass(frozen=True, slots=True)
class CostedRuleStudy:
    document: str

    def __post_init__(self) -> None:
        if self.document != canonical(economics_document()):
            raise DataError("fixed costed rule study data/cutoff/economics/version changed")

    def to_dict(self) -> dict[str, object]:
        return json.loads(self.document)  # type: ignore[no-any-return]

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.document.encode()).hexdigest()


def fixed_costed_study() -> CostedRuleStudy:
    return CostedRuleStudy(canonical(economics_document()))


def validate_costed_result(value: object) -> dict[str, object]:
    """Check independent fixed economics references; never derive scientific outcomes."""
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "baseline",
        "control",
        "scientific_acceptance",
        "outcome",
        "real_market_evidence",
    }:
        raise DataError("costed result shape changed")
    if (
        value["schema"] != "SyntheticCostedReplayResultV1"
        or value["scientific_acceptance"] != "not_admitted"
        or value["outcome"] != "synthetic_engineering_complete"
        or value["real_market_evidence"] is not False
    ):
        raise DataError("costed result cannot confer scientific authority")
    baseline = value["baseline"]
    control = value["control"]
    if not isinstance(baseline, dict) or not isinstance(control, dict):
        raise DataError("costed result requires baseline and control")
    fills = baseline.get("fill_trace")
    expected = [
        ("2000-01-04T00:00:00+00:00", "BUY", 100.0, 10.10),
        ("2000-01-05T00:00:00+00:00", "SELL", 100.0, 15.84),
        ("2000-01-06T00:00:00+00:00", "BUY", 75.0, 8.08),
        ("2000-01-07T00:00:00+00:00", "SELL", 75.0, 7.92),
    ]
    if not isinstance(fills, list) or len(fills) != 4:
        raise DataError("costed baseline must contain the four independently specified fills")
    for index, (fill, reference) in enumerate(zip(fills, expected, strict=True), 1):
        wanted = {
            "sequence_id": index,
            "order_sequence_id": index,
            "ts": reference[0],
            "instrument_id": "RULES.SIM",
            "side": reference[1],
            "quantity": reference[2],
            "price": reference[3],
        }
        if (
            not isinstance(fill, dict)
            or any(type(fill.get(key)) is not int for key in ("sequence_id", "order_sequence_id"))
            or fill != wanted
        ):
            raise DataError("canonical fill differs from independent next-open economics reference")
    for role, result, final, count in (
        ("baseline", baseline, 12558.21, 4),
        ("control", control, 12000.0, 0),
    ):
        curve = result.get("equity_curve")
        trades = result.get("trades")
        if (
            any(type(result.get(key)) is not int for key in ("fills", "orders", "rejected"))
            or result.get("fills") != count
            or result.get("orders") != count
            or result.get("rejected") != 0
            or not isinstance(curve, list)
            or len(curve) != 6
            or any(
                not isinstance(row, list)
                or len(row) != 2
                or not isinstance(row[0], str)
                or type(row[1]) not in (int, float)
                or abs(row[1]) > sys.float_info.max
                or not math.isfinite(row[1])
                for row in curve
            )
            or curve[-1] != ["2000-01-07T00:00:00+00:00", final]
            or not isinstance(trades, list)
            or len(trades) != (2 if count else 0)
        ):
            raise DataError(f"costed {role} accounting differs from the independent cash reference")
        try:
            TypeAdapter(BacktestResult).validate_python(result)
        except ValidationError as error:
            raise DataError(
                f"costed {role} result does not match the canonical backtest schema"
            ) from error
    if control.get("fill_trace") != [] or any(row[1] != 12000.0 for row in control["equity_curve"]):
        raise DataError("predeclared flat control is not flat")
    return value
