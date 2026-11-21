"""Cost defaults and annualisation by asset class (M71)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_cli.spine import cost_classes as cc
from alpha_cli.spine.reading import build_reading
from alpha_cli.spine.report_readings import costs_line
from alpha_cli.spine.run import assemble_run_spec
from alpha_cli.spine.spec import IdeaSpec
from alpha_cli.spine.stores import resolve_asset
from alpha_cli.toolbox.runner import run
from alpha_data.store import ParquetStore
from alpha_data.timeframe import DAILY, store_dir
from tests.unit.test_spine_tools import RUN
from tests.unit.test_toolbox_run_level_checks import COSTS, stored_run


def _asset(home: Path, symbol: str, source: str, dataset: dict[str, str] | None) -> None:
    path = ParquetStore(store_dir(home, DAILY))._provenance_path(symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, object] = {"source": source}
    if dataset is not None:
        body = {"dataset": {"provider": source, **dataset}}
    path.write_text(json.dumps(body))


def _key(home: Path, symbol: str) -> str | None:
    return cc.asset_class(resolve_asset(symbol, data_dir=home))


@pytest.mark.parametrize(
    ("symbol", "source", "dataset", "expected"),
    [
        ("SPY", "tiingo", {"asset_class": "etf", "venue": "US"}, "us_large_etf"),
        ("AAPL", "tiingo", {"asset_class": "stock", "venue": "US"}, "us_stock"),
        ("BTC/USDT", "binance", {"asset_class": "crypto", "venue": "BINANCE"}, "crypto_spot"),
        ("ETH/USDT", "ccxt:binance", None, "crypto_spot"),
        ("QQQ", "tiingo", None, None),
        ("ES", "vendor", {"asset_class": "future", "venue": "CME"}, None),
        ("VOD", "tiingo", {"asset_class": "stock", "venue": "LSE"}, None),
    ],
)
def test_class_lookup(
    tmp_path: Path, symbol: str, source: str, dataset: dict[str, str] | None, expected: str | None
) -> None:
    _asset(tmp_path, symbol, source, dataset)
    assert _key(tmp_path, symbol) == expected


def test_table_rows_and_unknown_class_is_the_most_cautious() -> None:
    assert set(cc.ROWS) == {"us_large_etf", "us_stock", "crypto_spot", "crypto_perpetual"}
    assert all(row.source for row in cc.ROWS.values())
    row, assumed = cc.class_row(None)
    assert assumed and row is cc.CONSERVATIVE
    assert row.fee_bps + row.slippage_bps == max(
        r.fee_bps + r.slippage_bps for r in cc.ROWS.values()
    )
    stock, assumed = cc.class_row("us_stock")
    assert not assumed
    assert (stock.fee_bps, stock.slippage_bps) == (2.0, 5.0)


def test_cost_lines() -> None:
    stock, _ = cc.class_row("us_stock")
    assert cc.cost_line(2.0, 5.0, stock, False) == (
        "Costs: 2 basis points fee and 5 slippage per side, the default for a US stock."
    )
    assert cc.cost_line(3.0, 4.0, None, False) == (
        "Costs: 3 basis points fee and 4 slippage per side, as the spec states."
    )
    line = cc.cost_line(10.0, 5.0, cc.CONSERVATIVE, True)
    assert "assumed" in line and "most cautious" in line


def _idea(costs: object) -> IdeaSpec:
    return IdeaSpec.model_validate(
        {"assets": ["SPY"], "rule": {"kind": "breakout", "window": 20}, "costs": costs}
    )


def test_class_default_spec_value() -> None:
    chosen = _idea("class-default")
    default = _idea({"fee_bps": 1.0, "slippage_bps": 2.0})
    assert chosen.costs_class_default and not default.costs_class_default
    assert chosen.spec_sha256 != default.spec_sha256
    assert json.loads(chosen.canonical())["costs"]["mode"] == "class-default"
    assert "mode" not in json.loads(default.canonical())["costs"]
    with pytest.raises(ValueError):
        _idea("cheap")


def test_class_default_costs_reach_the_run_spec() -> None:
    row, _ = cc.class_row("us_stock")
    spec = assemble_run_spec(_idea("class-default"), "SPY", 252, 2000, costs=row)
    assert spec.fee_bps == pytest.approx(2.0, rel=1e-9, abs=1e-12)
    assert spec.slippage_bps == pytest.approx(5.0, rel=1e-9, abs=1e-12)


def test_reading_states_costs_and_periods() -> None:
    manifest = {
        "spine": {
            "costs": {
                "line": "Costs: 2 basis points fee and 5 slippage per side, the default.",
                "periods": "Annualised with 252 periods a year (252 trading sessions a year).",
            },
            "annualisation": {"periods_per_year": 252, "basis": "252 trading sessions a year"},
        }
    }
    reading = build_reading(manifest)
    assert reading["costs"]["line"].startswith("Costs: 2 basis points")
    assert (
        reading["costs"]["periods"]
        == "Annualised with 252 periods a year (252 trading sessions a year)."
    )
    assert costs_line({"spine": {**manifest["spine"], "test_id": "t"}}) == reading["costs"]["line"]
    assert costs_line(manifest) is None
    old = build_reading({})
    assert old["costs"]["line"] is None and old["costs"]["reason"]
    assert costs_line({"spine": {"test_id": "t"}}) == "Costs: not recorded for this older run."
    assert costs_line({}) is None


def test_periods_rule_per_class() -> None:
    assert cc.ROWS["us_stock"].periods_per_year == 252
    assert cc.ROWS["us_large_etf"].periods_per_year == 252
    assert cc.ROWS["crypto_spot"].periods_per_year == 365
    assert cc.periods_rule_text("crypto_spot") == "365 days a year"
    assert cc.periods_line(365, "365 days a year") == (
        "Annualised with 365 periods a year (365 days a year)."
    )


def _short_run(home: Path, short: bool) -> None:
    folder = stored_run(home, COSTS)
    start = datetime(2022, 1, 1, tzinfo=UTC)
    sides = ["SELL", "BUY"] if short else ["BUY", "BUY"]
    pl.DataFrame(
        {
            "side": sides,
            "realized_pnl": [10.0, 10.0],
            "realized_return": [0.01, 0.01],
            "entry_ts": [start, start + timedelta(days=100)],
            "exit_ts": [start + timedelta(days=73), start + timedelta(days=110)],
        }
    ).write_parquet(folder / "trades.parquet")


def test_borrow_fact_for_a_run_with_shorts(tmp_path: Path) -> None:
    _asset(tmp_path, "SPY", "tiingo", {"asset_class": "stock", "venue": "US"})
    _short_run(tmp_path, short=True)
    values = run(tmp_path, COSTS, RUN)["values"]
    # One short: 73 days at 50 bp a year on a 1000 notional (10 / 0.01) is 1.0 in currency.
    assert values["borrow_charge"] == pytest.approx(1000 * 0.005 * 73 / 365, rel=1e-9, abs=1e-12)
    assert values["result_after_borrow"] is not None
    assert values["borrow_note"].startswith("A US stock")


def test_borrow_fact_is_absent_for_a_long_only_run(tmp_path: Path) -> None:
    _short_run(tmp_path, short=False)
    result = run(tmp_path, COSTS, RUN)
    assert result["values"]["result_after_borrow"] is None
    assert result["values"]["borrow_charge"] is None
    assert "no short" in result["reasons"]["result_after_borrow"].lower()


def test_follow_refuses_class_default_costs(tmp_path: Path) -> None:
    from alpha_cli.follow_source import frozen_idea
    from alpha_cli.spine.errors import SpineError

    idea = _idea("class-default")
    folder = tmp_path / "runs" / "abcdef0123456789"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text("{}")
    (folder / "spec.json").write_text(
        json.dumps({**idea.model_dump(mode="json"), "spec_sha256": idea.spec_sha256})
    )
    with pytest.raises(SpineError) as raised:
        frozen_idea(tmp_path, "abcdef0123456789", idea.spec_sha256)
    assert raised.value.payload["code"] == "FOLLOW_COSTS_BY_CLASS"
