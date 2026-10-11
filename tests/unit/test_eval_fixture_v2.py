"""Versioned fixture accounting must reconcile across trading sessions and month boundaries."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

MODULE = Path(__file__).resolve().parents[2] / "tools/alpha-eval/worlds/results_v2.py"


@pytest.fixture(autouse=True)
def world_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(MODULE.parent))


def load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("results_v2", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def test_accounting_uses_sessions_and_actual_month_end_equity(tmp_path: Path) -> None:
    builder = load_builder()
    builder.build_results_bundle(tmp_path, {"months": 8}, 12)
    trades = read(tmp_path / "trades.csv")
    daily = read(tmp_path / "daily_equity.csv")
    months = read(tmp_path / "monthly_returns.csv")
    sessions = {r["date"] for r in daily}
    for t in trades:
        assert t["entry_date"] in sessions and t["exit_date"] in sessions
        assert len([r for r in daily if t["entry_date"] < r["date"] <= t["exit_date"]]) == int(
            t["holding_sessions"]
        )
    net = sum(float(t["pnl_bps_net"]) * float(t["notional_initial_equity"]) / 10000 for t in trades)
    assert float(daily[-1]["equity"]) == pytest.approx(1 + net, abs=1e-10)
    assert np.prod([1 + float(m["net_return"]) for m in months]) == pytest.approx(
        1 + net, abs=1e-10
    )
    assert sum(float(r["net_pnl"]) for r in daily) == pytest.approx(net, abs=1e-10)
    assert any(t["entry_date"][:7] != t["exit_date"][:7] for t in trades)
    assert "synthetic" in (tmp_path / "summary.md").read_text().lower()


def test_calendar_holidays_and_reproducibility(tmp_path: Path) -> None:
    builder = load_builder()
    a, b = tmp_path / "a", tmp_path / "b"
    builder.build_results_bundle(a, {"months": 2}, 5)
    builder.build_results_bundle(b, {"months": 2}, 5)
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {
        p.name: p.read_bytes() for p in b.iterdir()
    }
    assert "2019-01-01" not in {r["date"] for r in read(a / "daily_equity.csv")}
    assert "2019-01-21" not in {r["date"] for r in read(a / "daily_equity.csv")}


def test_invalid_capital_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="weight"):
        load_builder().build_results_bundle(tmp_path, {"weight": float("nan")}, 1)
