"""Differential oracle: the equity screen's reported numbers versus pandas and SciPy.

``alpha scan hypotheses`` (``alpha_cli._hypothesis_scan.run_hypotheses``) is recomputed here from
the frozen snapshot's bars with pandas rolling windows and ``scipy.stats.spearmanr`` only, never
``alpha_research`` or ``alpha_cli`` helpers: the five documented price signals, forward returns,
per-date Spearman IC, its mean and plain t, the top-minus-bottom quantile spread, the bucket
turnover between dates one row and one horizon apart, and the cost-adjusted spread.

Not covered: the crypto lane, universe memberships and delisting returns (unit tests), and
corporate actions (the synthetic bars have none; a real-data run is in the task record).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from alpha_cli._hypothesis_scan import EQUITY_SIGNALS, run_hypotheses
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore
from tests.fixtures.cli_fixtures import seed_store

pytestmark = pytest.mark.oracle

_NAMES = ("A", "B", "C", "D", "E", "F", "G")
_MIN, _Q, _COST = 5, 5, 7.5


def _signal(name: str, prices: pd.DataFrame) -> pd.DataFrame:
    if name == "mom_12_1":
        return prices.shift(21) / prices.shift(252) - 1
    if name == "mom_6_1":
        return prices.shift(21) / prices.shift(126) - 1
    if name == "rev_1m":
        return -(prices / prices.shift(21) - 1)
    if name == "vol_63":
        return prices.pct_change(fill_method=None).rolling(63).std(ddof=1)
    high, low = prices.rolling(252).max(), prices.rolling(252).min()
    return ((prices - low) / (high - low)).where(high > low)


def _turnover(signal: np.ndarray, lag: int) -> float:
    fractions = []
    for t in range(signal.shape[0] - lag):
        both = np.isfinite(signal[t]) & np.isfinite(signal[t + lag])
        if both.sum() < _MIN:
            continue
        names = np.flatnonzero(both)
        width = len(names) // _Q
        first = names[np.argsort(signal[t][both], kind="stable")]
        second = names[np.argsort(signal[t + lag][both], kind="stable")]
        leavers = len(set(first[:width]) - set(second[:width]))
        leavers += len(set(first[-width:]) - set(second[-width:]))
        fractions.append(leavers / (2 * width))
    return float(np.mean(fractions))


def test_screen_rows_match_an_independent_pandas_scipy_recomputation(tmp_path: Path) -> None:
    for index, name in enumerate(_NAMES):
        seed_store(
            tmp_path, symbol=name, n=330, seed=index,
            sigma=0.01 + 0.003 * index, drift=0.0005 * (index - 3),
        )  # fmt: skip
    create_snapshot(
        ParquetStore(tmp_path / "store"), tmp_path / "snapshots", "oracle", list(_NAMES),
        source="fixture", adapter_version="1", parser_version="1",
        created_at=datetime(2021, 1, 1, tzinfo=UTC),
    )  # fmt: skip
    result = run_hypotheses(
        tmp_path,
        {
            "lane": "equity", "symbols": list(_NAMES), "universe": None, "snapshot": "oracle",
            "as_of": "2020-12-31", "signals": list(EQUITY_SIGNALS), "horizons": [1, 5, 21],
            "min_names": _MIN, "quantiles": _Q, "cost_bps": _COST, "category": "linear",
        },
    )  # fmt: skip
    prices = pd.DataFrame(
        {
            name: pd.read_parquet(
                tmp_path / "snapshots" / "oracle" / "bars" / f"{name}.parquet"
            ).set_index("ts")["close"]
            for name in _NAMES
        }
    ).sort_index()
    assert result["dates"] == [ts.date().isoformat() for ts in prices.index]
    assert len(result["results"]) == 15
    for row in result["results"]:
        signal = _signal(row["signal"], prices).to_numpy()
        horizon = row["horizon"]
        outcome = (prices.shift(-horizon) / prices - 1).to_numpy()
        ics, spreads = [], []
        for t in range(len(prices)):
            both = np.isfinite(signal[t]) & np.isfinite(outcome[t])
            if both.sum() < _MIN:
                continue
            ics.append(stats.spearmanr(signal[t][both], outcome[t][both]).statistic)
            ordered = outcome[t][both][np.argsort(signal[t][both], kind="stable")]
            width = int(both.sum()) // _Q
            spreads.append((ordered[-width:].mean(), ordered[:width].mean()))
        ic = np.asarray(ics)
        t_stat = ic.mean() / ic.std(ddof=1) * np.sqrt(ic.size)
        spread = float(np.mean([top for top, _ in spreads]) - np.mean([low for _, low in spreads]))
        lagged = _turnover(signal, horizon)
        assert row["ic"]["n_dates"] == ic.size
        assert row["ic"]["mean"] == pytest.approx(ic.mean(), abs=1e-12)
        assert row["ic"]["t_stat"] == pytest.approx(t_stat, rel=1e-10, abs=1e-12)
        assert row["quantiles"]["spread"] == pytest.approx(spread, abs=1e-12)
        assert row["turnover"] == pytest.approx(_turnover(signal, 1), abs=1e-12)
        assert row["horizon_turnover"] == pytest.approx(lagged, abs=1e-12)
        assert row["cost_adjusted_spread"] == pytest.approx(
            spread - 4 * lagged * _COST / 1e4, abs=1e-12
        )
