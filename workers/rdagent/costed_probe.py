"""Fixed costed synthetic replay using the canonical numerical engine, without calculators."""

from __future__ import annotations

import dataclasses
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
    from alpha_backtest.instruments import equity_instrument
    from alpha_core import Bar
    from alpha_strategies.rule_strategy import RuleStrategy
    from alpha_strategies.rules import rule_spec_from_json

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
    cutoff = datetime.fromisoformat(study["cutoff"])
    if any(bar.ts >= cutoff for bar in bars):
        raise ValueError("costed replay bars exceed fixed cutoff")
    economics = study["economics"]
    result = {}
    for role, spec in (("baseline", study["rules_spec"]), ("control", study["control_spec"])):
        instrument = equity_instrument(study["symbol"])
        bar_type = daily_bar_type(study["symbol"])
        strategy = RuleStrategy(
            instrument_id=instrument.id,
            bar_type=bar_type,
            spec=rule_spec_from_json(spec),
            vol_window=economics["vol_window"],
            target_vol=economics["target_vol"],
            capital=economics["capital"],
            max_leverage=economics["max_leverage"],
            rebalance_every=economics["rebalance_every"],
            periods_per_year=economics["periods_per_year"],
            allow_short=economics["allow_short"],
            size_on_equity=economics["size_on_equity"],
            halt_drawdown=economics["halt_drawdown"],
        )
        strategy.prime_history(bars[: study["warmup_bars"]])
        replay = run_backtest(
            instrument,
            to_execution_feed(
                bars[study["warmup_bars"] :],
                bar_type,
                price_precision=economics["price_precision"],
                size_precision=economics["size_precision"],
                slippage_bps=economics["slippage_bps"],
            ),
            strategy,
            starting_cash=economics["starting_cash"],
            fee_bps=economics["fee_bps"],
        )
        result[role] = _json(dataclasses.asdict(replay))
    return {
        "schema": "SyntheticCostedReplayResultV1",
        "baseline": result["baseline"],
        "control": result["control"],
        "scientific_acceptance": "not_admitted",
        "outcome": "synthetic_engineering_complete",
        "real_market_evidence": False,
    }
