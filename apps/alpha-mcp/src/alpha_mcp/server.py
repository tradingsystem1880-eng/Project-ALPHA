"""FastMCP server exposing Project ALPHA's research loop as conversational tools.

Action tools shell out to the installed ``alpha`` CLI (via :mod:`alpha_mcp._invoke`) and return
the byte-stable manifest the run produced; read tools (``get_run`` / ``list_runs`` /
``list_strategies``) read the store directly. Every tool reads ``ALPHA_DATA_DIR`` through
``AlphaSettings`` so the server, its subprocesses, and the CLI all share one store.

Compact, complete surface: the common knobs are typed, and an ``options`` dict maps any other CLI
flag (``{"lookback": "5", "fee-bps": "0"}`` -> ``--lookback 5 --fee-bps 0``) while ``params`` maps
strategy-specific ``--param name=value`` pairs. Run ``alpha <command> --help`` for the full flags.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from alpha_cli._strategies import known_strategies
from alpha_core.config import AlphaSettings
from alpha_mcp import _invoke, _runs

mcp = FastMCP("alpha")


def _data_dir() -> Path:
    return AlphaSettings().data_dir


def _option_flags(options: dict[str, str] | None) -> list[str]:
    """Map ``{name: value}`` to ``--name value`` flags (empty value -> a bare boolean flag)."""
    out: list[str] = []
    for name, value in (options or {}).items():
        out.append("--" + name.replace("_", "-"))
        if value != "":
            out.append(str(value))
    return out


def _param_flags(params: dict[str, str] | None) -> list[str]:
    """Map ``{name: value}`` to repeated ``--param name=value`` (strategy-specific params)."""
    return [tok for name, value in (params or {}).items() for tok in ("--param", f"{name}={value}")]


# --- action tools (subprocess the CLI, return the run's manifest) ----------------------------


@mcp.tool()
def data_pull(
    symbol: str, source: str = "yfinance", start: str | None = None, end: str | None = None
) -> dict[str, Any]:
    """Fetch + store raw OHLCV bars + actions for SYMBOL (source: yfinance|ccxt|stooq)."""
    args = ["data", "pull", symbol, "--source", source]
    if start is not None:
        args += ["--start", start]
    if end is not None:
        args += ["--end", end]
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type=None)


@mcp.tool()
def backtest_run(
    symbol: str,
    strategy: str = "ts_momentum",
    params: dict[str, str] | None = None,
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Backtest one fixed-parameter strategy on SYMBOL and return the run manifest."""
    args = ["backtest", "run", symbol, "--strategy", strategy]
    args += _param_flags(params) + _option_flags(options)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="runs")


@mcp.tool()
def backtest_portfolio(
    symbols: list[str],
    strategy: str = "ts_momentum",
    weighting: str = "equal",
    params: dict[str, str] | None = None,
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Backtest a diversified basket of SYMBOLS (weighting: equal|inverse_vol)."""
    args = ["backtest", "portfolio", *symbols, "--strategy", strategy, "--weighting", weighting]
    args += _param_flags(params) + _option_flags(options)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="portfolio")


@mcp.tool()
def backtest_cross_sectional(
    symbols: list[str], options: dict[str, str] | None = None
) -> dict[str, Any]:
    """Cross-sectional relative-strength book over SYMBOLS (long winners / short losers)."""
    args = ["backtest", "cross-sectional", *symbols]
    args += _option_flags(options)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="cross_sectional")


@mcp.tool()
def validate(
    symbol: str,
    strategy: str = "ts_momentum",
    params: dict[str, str] | None = None,
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run the full validation gauntlet on SYMBOL (walk-forward, null, CIs, DSR, CPCV, Verdict)."""
    args = ["validate", symbol, "--strategy", strategy]
    args += _param_flags(params) + _option_flags(options)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="runs")


@mcp.tool()
def optim_grid(
    symbol: str,
    grid: dict[str, list[float]],
    strategy: str = "ts_momentum",
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Sweep a parameter grid on SYMBOL, judged for overfitting (Deflated Sharpe + PBO + SPA).

    ``grid`` maps an axis to its values, e.g. ``{"lookback": [50, 100, 200]}``.
    """
    args = ["optim", "grid", symbol, "--strategy", strategy]
    for name, values in grid.items():
        args += ["--grid", f"{name}=" + ",".join(str(v) for v in values)]
    args += _option_flags(options)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="optim")


@mcp.tool()
def propfirm_run(
    symbol: str | None = None,
    from_run: str | None = None,
    firm: str | None = None,
    params: dict[str, str] | None = None,
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Prop-firm Monte Carlo (firm: topstep|apex|takeprofit). Pass one of SYMBOL / from_run."""
    args = ["propfirm", "run"]
    if symbol is not None:
        args.append(symbol)
    if from_run is not None:
        args += ["--from-run", from_run]
    if firm is not None:
        args += ["--firm", firm]
    args += _param_flags(params) + _option_flags(options)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="propfirm")


@mcp.tool()
def forecast_run(
    symbol: str,
    model: str = "base",
    horizon: int = 30,
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Forecast SYMBOL's next N OHLCV bars with the Kronos foundation model (mini|small|base).

    Weights must be pulled first via ``alpha forecast pull --model <name>`` (network —
    deliberately not exposed as a tool). CPU cost scales hard with model size: mini is
    seconds, base can be minutes per (uncached) forecast.
    """
    args = ["forecast", "run", symbol, "--model", model, "--horizon", str(horizon)]
    args += _option_flags(options)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="forecast")


# --- read tools (no subprocess) --------------------------------------------------------------


@mcp.tool()
def get_run(run_id: str) -> dict[str, Any]:
    """Fetch a stored run's full manifest by its run id."""
    return _runs.get_run(run_id, data_dir=_data_dir())


@mcp.tool()
def list_runs() -> list[dict[str, Any]]:
    """List stored runs as {run_id, command, label} across every run type."""
    return _runs.list_runs(data_dir=_data_dir())


@mcp.tool()
def list_strategies() -> list[str]:
    """List the registered strategy names available to backtest / validate / optim."""
    return list(known_strategies())


def main() -> None:
    """Entry point: run the stdio MCP server (Claude Code / Desktop launch this)."""
    mcp.run()


if __name__ == "__main__":
    main()
