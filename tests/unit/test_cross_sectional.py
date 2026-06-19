"""Cross-sectional momentum panel backtest (``alpha_cli._cross_sectional``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpha_cli._cross_sectional import run_cross_sectional
from alpha_core import DataError
from tests.fixtures.cli_fixtures import seed_store

# four assets with clearly separated trends: A/D up, B/C down (low noise so ranking is decisive)
_UNIVERSE = {"AAA": 0.012, "BBB": -0.004, "CCC": -0.012, "DDD": 0.004}


def _seed(data_dir: Path) -> list[str]:
    for i, (sym, drift) in enumerate(_UNIVERSE.items()):
        seed_store(data_dir, symbol=sym, n=120, seed=i, drift=drift, sigma=0.003)
    return list(_UNIVERSE)


def _run(data_dir: Path, **kw: object):  # type: ignore[no-untyped-def]
    return run_cross_sectional(
        _seed(data_dir),
        data_dir=data_dir,
        lookback=5,
        skip=1,
        vol_window=3,
        rebalance_every=2,
        top_quantile=0.25,  # 0.25 * 4 -> 1 name per leg
        **kw,  # type: ignore[arg-type]
    )


def test_long_short_book_profits_on_separated_trends(tmp_path: Path) -> None:
    res = _run(tmp_path, long_short=True)
    assert res.n_long == 1
    assert res.long_short is True
    assert res.n_periods > 0
    # long the up-trender, short the down-trender → both legs profit
    assert res.metrics["total_return"] > 0.0
    assert res.sharpe_ci.lower <= res.sharpe_ci.point <= res.sharpe_ci.upper


def test_long_only_book_runs(tmp_path: Path) -> None:
    res = _run(tmp_path, long_short=False)
    assert res.long_short is False
    assert res.n_periods > 0


def test_deterministic(tmp_path: Path) -> None:
    a = _run(tmp_path, long_short=True)
    b = _run(tmp_path, long_short=True)
    assert (a.returns == b.returns).all()


def test_fails_loud(tmp_path: Path) -> None:
    _seed(tmp_path)
    with pytest.raises(DataError):
        run_cross_sectional(["AAA"], data_dir=tmp_path, lookback=5, skip=1)  # < 2 symbols
    with pytest.raises(DataError):
        run_cross_sectional(["AAA", "BBB"], data_dir=tmp_path, top_quantile=0.9)  # > 0.5
    with pytest.raises(DataError):
        run_cross_sectional(["AAA", "AAA"], data_dir=tmp_path)  # duplicates
