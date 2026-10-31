"""Fixed costed synthetic replay using the canonical numerical engine, without calculators."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel


def _json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json(item) for item in value]
    return value


def execute(study: dict[str, Any]) -> dict[str, object]:
    from alpha_backtest.engine import run_backtest
    from alpha_backtest.feed import daily_bar_type, to_execution_feed
    from alpha_backtest.instruments import crypto_instrument, equity_instrument
    from alpha_backtest.results import AccountingTrace
    from alpha_core import Bar
    from alpha_strategies.rule_strategy import RuleStrategy
    from alpha_strategies.rules import rule_spec_from_json

    daily = study.get("schema") == "FrozenDailyRuleStudyV1"
    if not daily and study.get("schema") != "FrozenRuleCostedReplaySyntheticV1":
        raise ValueError("unsupported canonical costed replay schema")
    if daily:
        query = json.loads(study["query_document"])
        expected_bars = [
            [
                row["open_time"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["base_volume"],
            ]
            for row in query["rows"]
        ]
        if study["bars"] != expected_bars or study["data_origin"] not in {
            "artificial_fixture",
            "captured_provider_history",
        }:
            raise ValueError("daily replay rows/origin differ from the admitted study")
    bars = [
        Bar(
            symbol=study["symbol"],
            ts=datetime.fromisoformat(row[0]),
            open=row[1],
            high=row[2],
            low=row[3],
            close=row[4],
            volume=row[5],
        )
        for row in study["bars"]
    ]
    cutoff = datetime.fromisoformat(study["discovery_end_exclusive"] if daily else study["cutoff"])
    if any(bar.ts >= cutoff for bar in bars):
        raise ValueError("costed replay bars exceed fixed cutoff")
    economics = study["economics"]
    result = {}
    accounting_result = {}
    control_spec = (
        '{"history":21,"long_when":[{"left":{"source":"close"},"op":">",'
        '"right":{"value":0}}],"name":"btc-discovery-buy-hold-control-frozen",'
        '"short_when":[],"version":1}'
        if daily
        else study["control_spec"]
    )
    for role, spec in (("baseline", study["rules_spec"]), ("control", control_spec)):
        instrument = (
            crypto_instrument(
                study["symbol"],
                price_precision=economics["price_precision"],
                size_precision=economics["quantity_precision"],
                size_increment=economics["quantity_increment_btc"],
            )
            if daily
            else equity_instrument(study["symbol"])
        )
        bar_type = daily_bar_type(study["symbol"])
        sizing = (
            {
                "fixed_quantity": economics["fixed_quantity_btc"],
                "allow_short": False,
                "fixed_entry_once": role == "control",
            }
            if daily
            else {
                key: economics[key]
                for key in (
                    "vol_window",
                    "target_vol",
                    "capital",
                    "max_leverage",
                    "rebalance_every",
                    "periods_per_year",
                    "allow_short",
                    "size_on_equity",
                    "halt_drawdown",
                )
            }
        )
        strategy = RuleStrategy(
            instrument_id=instrument.id,
            bar_type=bar_type,
            spec=rule_spec_from_json(spec),
            **sizing,
        )
        strategy.prime_history(bars[: study["warmup_bars"]])
        accounting: list[AccountingTrace] = []
        replay = run_backtest(
            instrument,
            to_execution_feed(
                bars[study["warmup_bars"] :],
                bar_type,
                price_precision=economics["price_precision"],
                size_precision=economics["quantity_precision"]
                if daily
                else economics["size_precision"],
                slippage_bps=(economics["spread_bps_full"] / 2 + economics["slippage_bps_per_side"])
                if daily
                else economics["slippage_bps"],
                timing="utc_day_end_next_open" if daily else "session_close_23h",
            ),
            strategy,
            starting_cash=economics["starting_cash"],
            fee_bps=economics["fee_bps_per_side"] if daily else economics["fee_bps"],
            accounting_trace=accounting if daily else None,
        )
        result[role] = _json(dataclasses.asdict(replay))
        if daily:
            accounting_result[role] = _json([dataclasses.asdict(row) for row in accounting])
    if daily:
        return {
            "schema": "DailyRuleReplayResultV1",
            "baseline": result["baseline"],
            "control": result["control"],
            "accounting": accounting_result,
            "scientific_acceptance": "not_admitted",
            "outcome": "accounting_rejection_inconclusive"
            if any(result[role]["rejected"] > 0 for role in ("baseline", "control"))
            else "exploratory_complete",
            "real_market_evidence": study["data_origin"] == "captured_provider_history",
            "data_origin": study["data_origin"],
            "claim_scope": study["claim_scope"],
        }
    return {
        "schema": "SyntheticCostedReplayResultV1",
        "baseline": result["baseline"],
        "control": result["control"],
        "scientific_acceptance": "not_admitted",
        "outcome": "synthetic_engineering_complete",
        "real_market_evidence": False,
    }
