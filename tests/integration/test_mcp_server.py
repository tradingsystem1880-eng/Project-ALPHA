"""The MCP server's tools drive the real `alpha` CLI end-to-end (offline, no network).

These call the tool functions directly (FastMCP leaves them ordinary callables) against a temp
ALPHA_DATA_DIR seeded with the shared fixture, so a real `alpha` subprocess runs each time —
exercising subprocess invocation, run-id parsing, manifest reads, run-type routing, the
filesystem read tools, and the FastMCP registration.
"""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from alpha_mcp import server
from tests.fixtures.cli_fixtures import seed_store

# small-parameter knobs so the fixture's 60 bars warm up, trade, and cost nothing
_OPTS = {
    "lookback": "5",
    "skip": "1",
    "vol-window": "3",
    "rebalance-every": "2",
    "fee-bps": "0",
    "slippage-bps": "0",
    "starting-cash": "100000",
}


def test_backtest_run_tool_returns_a_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    manifest = server.backtest_run("SPY", options=_OPTS)
    assert manifest["command"] == "backtest_run"
    run_id = manifest["run_id"]

    # the read tools see the same run from disk, no engine
    assert server.get_run(run_id)["run_id"] == run_id
    assert any(r["run_id"] == run_id for r in server.list_runs())


def test_propfirm_from_run_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    bt = server.backtest_run("SPY", options=_OPTS)
    pf = server.propfirm_run(
        from_run=bt["run_id"], firm="topstep", options={"n-paths": "200", "seed": "7"}
    )
    assert pf["command"] == "propfirm"
    assert pf["firm"] == "topstep"


def test_forecast_run_tool_returns_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)

    manifest = server.forecast_run(
        "SPY", options={"model": "fake", "context": "8", "horizon": "4", "samples": "6"}
    )
    assert manifest["command"] == "forecast_run"
    assert manifest["model"]["model_id"] == "fake"
    assert server.get_run(manifest["run_id"])["run_id"] == manifest["run_id"]
    assert any(r["run_id"] == manifest["run_id"] for r in server.list_runs())


def test_failed_run_surfaces_the_cli_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    # no such symbol stored -> the CLI fails loud -> the tool raises with the CLI's message
    with pytest.raises(RuntimeError):
        server.backtest_run("NOPE", options=_OPTS)


def test_list_strategies_includes_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "ts_momentum" in server.list_strategies()


def test_all_expected_tools_are_registered() -> None:
    names = {t.name for t in anyio.run(server.mcp.list_tools)}
    assert names == {
        "data_pull",
        "backtest_run",
        "backtest_portfolio",
        "backtest_cross_sectional",
        "validate",
        "optim_grid",
        "propfirm_run",
        "forecast_run",
        "get_run",
        "list_runs",
        "list_strategies",
    }
