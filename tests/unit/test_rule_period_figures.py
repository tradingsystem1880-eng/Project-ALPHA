"""Rule report periods, figures and buy-and-hold must reconcile to the engine."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_cli.figures import build_figure_spec
from alpha_cli.spine.run import run_idea
from alpha_cli.spine.spec import load_spec
from alpha_data.store import ParquetStore
from alpha_research.figures import LineMark, RuleMark
from tests.fixtures.cli_fixtures import seed_store


@pytest.fixture(scope="module")
def stored_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    home = tmp_path_factory.mktemp("periods")
    seed_store(home, symbol="SPY", n=150)
    ParquetStore(home / "store").write_provenance(
        "SPY", source="fixture", adapter_version="1", parser_version="1"
    )
    idea = load_spec(None, rule="ma_cross", param=["fast=5", "slow=20"], asset=["SPY"])
    result = run_idea(idea, home=home, quick=True)["results"][0]
    assert result["error"] is None, result["error"]
    rdir = Path(result["run_dir"])
    return rdir, json.loads((rdir / "manifest.json").read_bytes())


def test_rule_periods_match_rendered_equity(stored_run: tuple[Path, dict[str, Any]]) -> None:
    rdir, manifest = stored_run
    spine = manifest["spine"]
    periods = spine["periods"]
    assert "benchmark-price-only" in spine["labels"]
    assert (
        periods["tradable"]["first_ts"]
        == (
            datetime.fromisoformat(spine["data_period"]["first_ts"]) + timedelta(days=20)
        ).isoformat()
    )
    assert periods["scored"]["first_ts"] == spine["traded_period"]["first_ts"]
    assert periods["tradable"]["first_ts"] < periods["scored"]["first_ts"]
    for period, prefix in (("tradable", "tradable_"), ("scored", "")):
        row = periods[period]
        for figure in ("equity_underwater", "equity_vs_passive"):
            spec = build_figure_spec(
                prefix + figure,
                run_id=rdir.name,
                rdir=rdir,
                data_dir=rdir.parent.parent,
                manifest=manifest,
            )
            line = spec.panels[0].marks[1]
            assert isinstance(line, LineMark)
            assert line.y[-1] - 1 == pytest.approx(row["strategy"]["total_return"])
            assert datetime.fromtimestamp(line.x[0], UTC).isoformat() == row["first_ts"]
            assert datetime.fromtimestamp(line.x[-1], UTC).isoformat() == row["last_ts"]
            if figure == "equity_underwater":
                assert f"{row['strategy']['max_drawdown']:.1%}" in spec.plain_language_answer
            else:
                passive = spec.panels[0].marks[0]
                assert isinstance(passive, LineMark)
                assert passive.y[-1] - 1 == pytest.approx(row["benchmark"]["total_return"])
                assert all("price only, no dividends" in (m.label or "") for m in (passive, line))


def test_excess_series_matches_caption(tmp_path: Path) -> None:
    dates = [datetime(2020, 1, day, tzinfo=UTC) for day in (1, 2, 3)]
    pl.DataFrame(
        {
            "ts": dates,
            "strategy_equity": [1.0, 1.5, 1.25],
            "benchmark_equity": [1.0, 1.1, 1.0],
            "available": [True] * 3,
        }
    ).write_parquet(tmp_path / "benchmark_comparison.parquet")
    spec = build_figure_spec(
        "equity_vs_passive",
        run_id="fixture",
        rdir=tmp_path,
        manifest={
            "spine": {
                "periods": {
                    "scored": {
                        "first_ts": dates[0].isoformat(),
                        "last_ts": dates[-1].isoformat(),
                        "period": "scored",
                        "price_basis": "price only, no dividends",
                    }
                }
            }
        },
        data_dir=tmp_path,
    )
    excess = spec.panels[1].marks[0]
    assert isinstance(excess, LineMark)
    assert excess.y == pytest.approx((0, 1.5 / 1.1 - 1, 0.25))
    assert excess.end_label is not None
    assert excess.end_label.text == f"{excess.y[-1]:.1%}"
    assert excess.end_label.text in spec.plain_language_answer


@pytest.mark.parametrize("fractional_tick", [0.0, 0.003])
def test_buy_and_hold_dividend_cash_matches_invested_engine(fractional_tick: float) -> None:
    from alpha_backtest.engine import run_backtest
    from alpha_backtest.feed import daily_bar_type, to_execution_feed
    from alpha_backtest.instruments import equity_instrument
    from alpha_cli.spine import diagnostics
    from alpha_core import ActionType, CorporateAction
    from tests.fixtures.nautilus_fixtures import BuyAndHold, ladder_bars

    bars = ladder_bars("AAPL")
    bars[2] = bars[2].model_copy(update={"open": 118.75})  # Ex-dividend opening drop.
    bars[-1] = bars[-1].model_copy(update={"open": float(bars[-1].open) + fractional_tick})
    actions = [
        CorporateAction(
            symbol="AAPL",
            action_type=ActionType.DIVIDEND,
            ex_date=date(2024, 1, ex),
            pay_date=date(2024, 1, 6),
            amount=amount,
        )
        for ex, amount in ((2, 8.0), (4, 1.25))
    ]
    inst = equity_instrument("AAPL")
    full = run_backtest(
        inst,
        to_execution_feed(bars, daily_bar_type("AAPL")),
        BuyAndHold(inst.id),
        starting_cash=10_000,
        fee_bps=0,
        dividends=actions,
    )
    benchmark = diagnostics.buy_and_hold(bars, actions)
    assert benchmark == pytest.approx([v / 10_000 for _, v in full.equity_curve], abs=1e-9, rel=0)
    assert benchmark[-1] == pytest.approx(1.4125, abs=1e-9, rel=0)


def test_new_rule_figure_variants_are_white_and_have_their_own_keys(
    stored_run: tuple[Path, dict[str, Any]],
) -> None:
    from PIL import Image

    from alpha_cli.figures_cmds import _render_one

    rdir, manifest = stored_run
    keys = []
    for variant in ("plain", "annotated"):
        figure = _render_one(
            "equity_underwater",
            run_id=rdir.name,
            rdir=rdir,
            manifest=manifest,
            data_dir=rdir.parent.parent,
            fmt="png",
            force=False,
            variant=variant,
        )
        keys.append(figure["cache_key"])
        with Image.open(figure["path"]) as png:
            assert png.convert("RGB").getpixel((0, 0)) == (255, 255, 255)
    assert keys[0] != keys[1]


def test_citable_numbers_declare_dates_and_basis(stored_run: tuple[Path, dict[str, Any]]) -> None:
    from alpha_cli.spine.facts import build_facts

    rdir, manifest = stored_run
    facts = {fact["metric"]: fact for fact in build_facts(rdir)}
    for metric, name in (
        ("full_sample_cagr", "full_history"),
        ("benchmark_sharpe", "full_history"),
        ("oos_sharpe", "scored"),
        ("tradable_max_drawdown", "tradable"),
        ("scored_benchmark_total_return", "scored"),
    ):
        row = manifest["spine"]["periods"][name]
        fact = facts[metric]
        assert fact["period"] == name
        assert fact["first_ts"] == row["first_ts"]
        assert fact["last_ts"] == row["last_ts"]
        assert fact["price_basis"] == row["price_basis"]


def test_run_publishes_four_light_summary_figures(stored_run: tuple[Path, dict[str, Any]]) -> None:
    rdir, _ = stored_run
    cache = rdir.parent.parent / "figures" / rdir.name
    assert {p.name.split(".")[0] for p in cache.glob("*.svg")} == {
        "tradable_equity_vs_passive",
        "tradable_equity_underwater",
        "equity_vs_passive",
        "equity_underwater",
    }


def test_rule_without_diagnostics_cites_stored_dividend_benchmark(tmp_path: Path) -> None:
    from alpha_core import ActionType, CorporateAction

    seed_store(tmp_path, symbol="SPY", n=150)
    store = ParquetStore(tmp_path / "store")
    store.write_provenance("SPY", source="fixture", adapter_version="1", parser_version="1")
    action = CorporateAction(
        symbol="SPY",
        action_type=ActionType.DIVIDEND,
        ex_date=date(2020, 3, 1),
        pay_date=date(2020, 3, 5),
        amount=1.75,
    )
    store.write_actions("SPY", [action])
    idea = load_spec(None, rule="ma_cross", param=["fast=5", "slow=20"], asset=["SPY"])
    result = run_idea(idea, home=tmp_path, quick=True, no_diagnose=True)["results"][0]
    assert result["error"] is None, result["error"]
    facts = {f["metric"]: f for f in result["facts"]}
    assert facts["benchmark_sharpe"]["value"] == result["benchmark_sharpe"]
    assert facts["benchmark_sharpe"]["price_basis"] == "with dividends"
    assert "benchmark-price-only" not in result["labels"]
    rdir = Path(result["run_dir"])
    assert not (rdir / "diagnostics.json").exists()
    frame = pl.read_parquet(rdir / "benchmark_comparison.parquet")
    assert set(frame["benchmark_kind"]) == {"passive_open_to_open_with_dividends"}
    assert frame["benchmark_equity"][-1] - 1 == pytest.approx(
        facts["scored_benchmark_total_return"]["value"]
    )


def test_web_reads_exact_prebuilt_rule_figures(stored_run: tuple[Path, dict[str, Any]]) -> None:
    from alpha_web import _figures

    rdir, _ = stored_run
    home = rdir.parent.parent
    for name in ("tradable_equity_vs_passive", "equity_vs_passive"):
        image, sidecar, key = _figures._cache_entry(rdir.name, name, "svg", home)
        assert image.is_file() and sidecar.is_file()
        assert _figures.metadata(rdir.name, name, fmt="svg", data_dir=home)["cache_key"] == key


def test_rule_drawdown_preserves_full_resolution_extreme(tmp_path: Path) -> None:
    from alpha_cli.figures import _sources

    n = 6000
    sampled = set(_sources.sample(n))
    hidden = next(i for i in range(n) if i not in sampled)
    dates = [datetime(2000, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(n)]
    equity = [1.0] * n
    equity[hidden] = 0.25
    pl.DataFrame({"ts": dates, "equity": equity}).write_parquet(tmp_path / "equity_curve.parquet")
    record = {
        "period": "scored",
        "first_ts": dates[0].isoformat(),
        "last_ts": dates[-1].isoformat(),
        "price_basis": "price only, no dividends",
    }
    chart = build_figure_spec(
        "equity_underwater",
        run_id="fixture",
        rdir=tmp_path,
        data_dir=tmp_path,
        manifest={"spine": {"periods": {"scored": record}}},
    )
    under = chart.panels[1].marks[0]
    assert isinstance(under, LineMark)
    assert min(under.y) == -0.75
    worst = next(mark for mark in chart.panels[1].marks if isinstance(mark, RuleMark))
    assert worst.position == min(under.y)
    assert worst.annotate and worst.annotate.text == "worst -75.0%"
    assert "-75.0%" in chart.plain_language_answer
    assert dates[hidden].date().isoformat() in chart.plain_language_answer


def test_tradable_numbers_match_a_hand_calculation(
    stored_run: tuple[Path, dict[str, Any]],
) -> None:
    """Recompute each tradable fact from the store's opens and the engine equity, by hand."""
    rdir, manifest = stored_run
    row = manifest["spine"]["periods"]["tradable"]
    ppy = manifest["spine"]["annualisation"]["periods_per_year"]
    bars = ParquetStore(rdir.parent.parent / "store").read_bars("SPY")
    first, last = (datetime.fromisoformat(row[key]) for key in ("first_ts", "last_ts"))
    window = bars.filter((pl.col("ts") >= first) & (pl.col("ts") <= last))
    opens = [round(value, 2) for value in window["open"].to_list()]
    equity = pl.read_parquet(rdir / "equity_curve.parquet")  # scored only; tradable is separate
    assert equity.height < window.height
    tradable = pl.read_parquet(rdir / "tradable_comparison.parquet")
    assert tradable["ts"].to_list() == window["ts"].to_list()
    values = tradable["strategy_equity"].to_list()
    peak, worst = values[0], 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    growth = values[-1] / values[0]
    hold = opens[-1] / opens[0]  # no dividends recorded for this fixture
    assert row["strategy"]["total_return"] == pytest.approx(growth - 1, abs=1e-12)
    assert row["strategy"]["cagr"] == pytest.approx(growth ** (ppy / (len(values) - 1)) - 1)
    assert row["strategy"]["max_drawdown"] == pytest.approx(worst, abs=1e-12)
    assert row["benchmark"]["total_return"] == pytest.approx(hold - 1, abs=1e-12)
    assert row["relative_return"] == pytest.approx(growth / hold - 1, abs=1e-12)


def test_runs_without_period_records_use_the_same_ratio(tmp_path: Path) -> None:
    """Old runs and plain validation runs: one excess definition, labels from all 8,284 bars."""
    from alpha_cli.figures import _sources

    n = 8284
    dates = [datetime(1993, 1, 29, tzinfo=UTC) + timedelta(days=i) for i in range(n)]
    strategy = [1.0 + 0.002 * i for i in range(n)]
    passive = [1.0 + 0.003 * i for i in range(n)]
    hidden = next(i for i in range(1, n - 1) if i not in set(_sources.sample(n)))
    strategy[hidden] = 0.5  # one unplotted session holds the worst drop
    pl.DataFrame(
        {
            "ts": dates,
            "strategy_equity": strategy,
            "benchmark_equity": passive,
            "available": [True] * n,
            "unavailable_reason": [None] * n,
            "benchmark_kind": ["passive_open_to_open_price_only"] * n,
        }
    ).write_parquet(tmp_path / "benchmark_comparison.parquet")
    pl.DataFrame({"ts": dates, "equity": strategy}).write_parquet(tmp_path / "equity_curve.parquet")
    figures = {
        name: build_figure_spec(
            name, run_id="fixture", rdir=tmp_path, manifest={}, data_dir=tmp_path
        )
        for name in ("equity_vs_passive", "equity_underwater")
    }
    excess = figures["equity_vs_passive"].panels[1].marks[0]
    assert isinstance(excess, LineMark) and excess.end_label is not None
    expected = strategy[-1] / passive[-1] - 1
    assert excess.y[-1] == pytest.approx(expected, abs=1e-12)
    assert excess.end_label.text == f"{expected:.1%}"
    assert f"{abs(expected):.1%} behind" in figures["equity_vs_passive"].plain_language_answer
    passive_line = figures["equity_vs_passive"].panels[0].marks[0]
    assert isinstance(passive_line, LineMark)
    assert passive_line.label == "Buy and hold (price only)"
    under = figures["equity_underwater"]
    worst = strategy[hidden] / max(strategy[:hidden]) - 1
    assert f"{worst:.1%}" in under.plain_language_answer
    rule = next(m for m in under.panels[1].marks if isinstance(m, RuleMark))
    assert rule.position == pytest.approx(worst)
