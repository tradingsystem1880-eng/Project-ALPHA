"""FastMCP server exposing Project ALPHA's research loop as conversational tools.

Action tools shell out to the installed ``alpha`` CLI (via :mod:`alpha_mcp._invoke`) and return
the byte-stable manifest the run produced. Run/catalog reads use public lightweight CLI seams;
Workstation v3 project, job, evidence, and AgentBrief reads/actions use explicit bounded CLI JSON
commands. Every tool reads ``ALPHA_DATA_DIR`` through ``AlphaSettings`` so the server, its
subprocesses, and the CLI all share one store.

Compact, complete surface: the common knobs are typed, and retained ``options`` dictionaries map
only a closed, per-tool deprecated compatibility vocabulary (for example,
``{"lookback": "5", "fee-bps": "0"}`` -> ``--lookback 5 --fee-bps 0``). ``params`` maps only
declared strategy-specific ``--param name=value`` pairs.
"""

from __future__ import annotations

import math
import re
from datetime import date
from pathlib import Path
from typing import Any, Final, Literal, cast

from mcp.server.fastmcp import FastMCP

from alpha_cli import run_projection
from alpha_cli.catalog import known_strategies
from alpha_cli.catalog import strategy_params as catalog_strategy_params
from alpha_cli.run_store import valid_run_id
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_mcp import _control, _invoke, _runs, _types

mcp = FastMCP("alpha")

_MAX_OPTIONS: Final = 32
_MAX_OPTION_VALUE_LENGTH: Final = 256
_MAX_PARAMS: Final = 16
_MAX_PARAM_VALUE_LENGTH: Final = 128
_MAX_SYMBOLS: Final = 100
_MAX_SYMBOL_LENGTH: Final = 64
_MAX_GRID_AXES: Final = 16
_MAX_GRID_VALUES_PER_AXIS: Final = 256
_MAX_GRID_CONFIGURATIONS: Final = 4_096
_OPTION_KEY = re.compile(r"[a-z][a-z0-9-]{0,63}")
_PARAM_KEY = re.compile(r"[a-z][a-z0-9_]{0,63}")
_SAFE_MANAGED_ID = re.compile(r"(?:fake|[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*)")
_SAFE_REVISION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_SAFE_OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

_COMMON_RUN_OPTIONS = frozenset(
    {
        "lookback",
        "skip",
        "vol-window",
        "target-vol",
        "rebalance-every",
        "max-leverage",
        "allow-short",
        "no-allow-short",
        "fee-bps",
        "slippage-bps",
        "starting-cash",
        "account-type",
        "periods-per-year",
    }
)
_BACKTEST_RUN_OPTIONS = _COMMON_RUN_OPTIONS | {
    "size-on-equity",
    "no-size-on-equity",
    "halt-drawdown",
    "snapshot",
    "as-of",
}
_PORTFOLIO_OPTIONS = _BACKTEST_RUN_OPTIONS | {
    "train-size",
    "test-size",
    "embargo",
    "anchored",
    "no-anchored",
    "seed",
}
_CROSS_SECTIONAL_OPTIONS = frozenset(
    {
        "lookback",
        "skip",
        "vol-window",
        "target-vol",
        "rebalance-every",
        "top-quantile",
        "long-short",
        "no-long-short",
        "max-leverage",
        "fee-bps",
        "slippage-bps",
        "periods-per-year",
        "seed",
        "snapshot",
        "as-of",
    }
)
_VALIDATE_OPTIONS = _COMMON_RUN_OPTIONS | {
    "train-size",
    "test-size",
    "embargo",
    "anchored",
    "no-anchored",
    "tier1-paths",
    "tier2-paths",
    "n-resamples",
    "mean-block",
    "threshold",
    "null-model",
    "tier1-divergence-tol",
    "tier2-mode",
    "seed",
    "max-workers",
    "snapshot",
    "as-of",
}
_OPTIM_OPTIONS = _COMMON_RUN_OPTIONS | {
    "train-size",
    "test-size",
    "embargo",
    "anchored",
    "no-anchored",
    "pbo-blocks",
    "n-resamples",
    "mean-block",
    "dsr-threshold",
    "alpha",
    "seed",
    "max-workers",
    "snapshot",
    "as-of",
}
_FORECAST_RUN_OPTIONS = frozenset(
    {
        "horizon",
        "samples",
        "context",
        "temperature",
        "top-p",
        "top-k",
        "model",
        "model-revision",
        "tokenizer",
        "tokenizer-revision",
        "device",
        "as-of",
        "seed",
        "snapshot",
    }
)
_FORECAST_EVAL_OPTIONS = _FORECAST_RUN_OPTIONS | {"stride", "mean-block"}
_PROPFIRM_OPTIONS = _BACKTEST_RUN_OPTIONS - {"as-of"} | {
    "strategy",
    "account-size",
    "profit-target",
    "max-drawdown",
    "daily-loss",
    "profit-split",
    "min-trading-days",
    "n-paths",
    "mean-block",
    "horizon",
    "seed",
}
_BOOLEAN_OPTIONS = frozenset(
    {
        "allow-short",
        "no-allow-short",
        "size-on-equity",
        "no-size-on-equity",
        "anchored",
        "no-anchored",
        "long-short",
        "no-long-short",
    }
)
_GRID_COMMON_AXES = frozenset(
    {"lookback", "skip", "vol_window", "target_vol", "rebalance_every", "max_leverage"}
)


def _data_dir() -> Path:
    return AlphaSettings().data_dir


def _bounded_text(value: object, label: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValueError(f"{label} must be a non-empty string of at most {max_length} characters")
    if any(char in value for char in ("\x00", "\r", "\n")):
        raise ValueError(f"{label} contains a forbidden control character")
    return value


def _symbol(value: object) -> str:
    symbol = _bounded_text(value, "symbol", max_length=_MAX_SYMBOL_LENGTH)
    if ".." in symbol or "\\" in symbol or symbol.startswith("/") or symbol.endswith("/"):
        raise ValueError("symbol contains a filesystem-like path")
    return symbol


def _iso_date(value: object, label: str) -> str:
    text = _bounded_text(value, label, max_length=10)
    if _ISO_DATE.fullmatch(text) is None:
        raise ValueError(f"{label} must be YYYY-MM-DD")
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid YYYY-MM-DD date") from exc
    return text


def _symbols(values: list[str], *, tool: str) -> list[str]:
    if not 2 <= len(values) <= _MAX_SYMBOLS:
        raise ValueError(f"{tool} symbols must contain 2..{_MAX_SYMBOLS} items")
    result = [_symbol(value) for value in values]
    if len(set(result)) != len(result):
        raise ValueError(f"{tool} symbols contain duplicates")
    return result


def _strategy(value: object) -> str:
    strategy = _bounded_text(value, "strategy", max_length=64)
    if strategy not in known_strategies():
        raise ValueError(f"unknown strategy {strategy!r}; known: {known_strategies()}")
    return strategy


def _option_flags(
    options: dict[str, str] | None,
    *,
    tool: str,
    allowed: frozenset[str] | set[str],
) -> list[str]:
    """Translate only one tool's closed, bounded compatibility-option vocabulary."""
    if options is None:
        return []
    if len(options) > _MAX_OPTIONS:
        raise ValueError(f"{tool} options exceed the {_MAX_OPTIONS}-option limit")
    out: list[str] = []
    seen: set[str] = set()
    for raw_name, raw_value in options.items():
        if not isinstance(raw_name, str):
            raise ValueError(f"{tool} option names must be strings")
        name = raw_name.replace("_", "-")
        if _OPTION_KEY.fullmatch(name) is None or name not in allowed:
            raise ValueError(f"unsupported {tool} option {raw_name!r}")
        if name in seen:
            raise ValueError(f"duplicate normalized {tool} option {name!r}")
        seen.add(name)
        if not isinstance(raw_value, str) or len(raw_value) > _MAX_OPTION_VALUE_LENGTH:
            raise ValueError(
                f"{tool} option {name!r} must be a string of at most "
                f"{_MAX_OPTION_VALUE_LENGTH} characters"
            )
        if any(char in raw_value for char in ("\x00", "\r", "\n")):
            raise ValueError(f"{tool} option {name!r} contains a forbidden control character")
        if name in _BOOLEAN_OPTIONS:
            if raw_value != "":
                raise ValueError(f"boolean {tool} option {name!r} must use an empty value")
        elif not raw_value:
            raise ValueError(f"{tool} option {name!r} requires a value")
        if name in {"model", "tokenizer"} and _SAFE_MANAGED_ID.fullmatch(raw_value) is None:
            raise ValueError(f"{tool} option {name!r} must be 'fake' or a managed repository id")
        if (
            name in {"model-revision", "tokenizer-revision"}
            and _SAFE_REVISION.fullmatch(raw_value) is None
        ):
            raise ValueError(f"{tool} option {name!r} must be a safe immutable revision id")
        if name == "snapshot" and _SAFE_OPAQUE_ID.fullmatch(raw_value) is None:
            raise ValueError(f"{tool} option 'snapshot' must be an opaque snapshot id")
        if name == "strategy":
            _strategy(raw_value)
        out.append("--" + name)
        if raw_value:
            out.append(raw_value)
    return out


def _param_flags(strategy: str, params: dict[str, str] | None) -> list[str]:
    """Translate bounded, declared numeric parameters for one registered strategy."""
    if params is None:
        return []
    if len(params) > _MAX_PARAMS:
        raise ValueError(f"strategy params exceed the {_MAX_PARAMS}-parameter limit")
    allowed = {str(row["name"]) for row in catalog_strategy_params(strategy)}
    out: list[str] = []
    for name, raw_value in params.items():
        if not isinstance(name, str) or _PARAM_KEY.fullmatch(name) is None or name not in allowed:
            raise ValueError(f"unsupported parameter {name!r} for strategy {strategy!r}")
        value = _bounded_text(
            raw_value, f"strategy parameter {name!r}", max_length=_MAX_PARAM_VALUE_LENGTH
        )
        try:
            number = float(value)
        except ValueError as exc:
            raise ValueError(f"strategy parameter {name!r} must be numeric") from exc
        if not math.isfinite(number):
            raise ValueError(f"strategy parameter {name!r} must be finite")
        out.extend(("--param", f"{name}={value}"))
    return out


def _grid_flags(strategy: str, grid: dict[str, list[float]]) -> list[str]:
    if not 1 <= len(grid) <= _MAX_GRID_AXES:
        raise ValueError(f"grid must contain 1..{_MAX_GRID_AXES} axes")
    allowed = _GRID_COMMON_AXES | {str(row["name"]) for row in catalog_strategy_params(strategy)}
    out: list[str] = []
    seen: set[str] = set()
    configurations = 1
    for raw_name, values in grid.items():
        if not isinstance(raw_name, str):
            raise ValueError("grid axis names must be strings")
        name = raw_name.replace("-", "_")
        if _PARAM_KEY.fullmatch(name) is None or name not in allowed:
            raise ValueError(f"unsupported grid axis {raw_name!r} for strategy {strategy!r}")
        if name in seen:
            raise ValueError(f"duplicate normalized grid axis {name!r}")
        seen.add(name)
        if not isinstance(values, list) or not 1 <= len(values) <= _MAX_GRID_VALUES_PER_AXIS:
            raise ValueError(
                f"grid axis {name!r} must contain 1..{_MAX_GRID_VALUES_PER_AXIS} values"
            )
        normalized: list[str] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"grid axis {name!r} values must be numeric")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"grid axis {name!r} values must be finite")
            normalized.append(str(value))
        configurations *= len(values)
        if configurations > _MAX_GRID_CONFIGURATIONS:
            raise ValueError(f"grid exceeds the {_MAX_GRID_CONFIGURATIONS}-configuration limit")
        out.extend(("--grid", f"{name}=" + ",".join(normalized)))
    return out


# --- action tools (subprocess the CLI, return the run's manifest) ----------------------------


@mcp.tool()
def data_pull(
    symbol: str, source: str = "yfinance", start: str | None = None, end: str | None = None
) -> dict[str, Any]:
    """Fetch + store raw OHLCV bars + actions for SYMBOL (source: yfinance|ccxt|stooq)."""
    symbol = _symbol(symbol)
    if source not in {"yfinance", "ccxt", "stooq"}:
        raise ValueError("source must be yfinance, ccxt, or stooq")
    args = ["data", "pull", symbol, "--source", source]
    parsed_start = _iso_date(start, "start") if start is not None else None
    parsed_end = _iso_date(end, "end") if end is not None else None
    if parsed_start is not None and parsed_end is not None and parsed_start > parsed_end:
        raise ValueError("start must be on or before end")
    if parsed_start is not None:
        args += ["--start", parsed_start]
    if parsed_end is not None:
        args += ["--end", parsed_end]
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type=None)


@mcp.tool()
def backtest_run(
    symbol: str,
    strategy: str = "ts_momentum",
    params: dict[str, str] | None = None,
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Backtest one fixed-parameter strategy on SYMBOL and return the run manifest."""
    symbol = _symbol(symbol)
    strategy = _strategy(strategy)
    args = ["backtest", "run", symbol, "--strategy", strategy]
    args += _param_flags(strategy, params) + _option_flags(
        options, tool="backtest_run", allowed=_BACKTEST_RUN_OPTIONS
    )
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
    symbols = _symbols(symbols, tool="backtest_portfolio")
    strategy = _strategy(strategy)
    if weighting not in {"equal", "inverse_vol"}:
        raise ValueError("weighting must be equal or inverse_vol")
    args = ["backtest", "portfolio", *symbols, "--strategy", strategy, "--weighting", weighting]
    args += _param_flags(strategy, params) + _option_flags(
        options, tool="backtest_portfolio", allowed=_PORTFOLIO_OPTIONS
    )
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="portfolio")


@mcp.tool()
def backtest_cross_sectional(
    symbols: list[str], options: dict[str, str] | None = None
) -> dict[str, Any]:
    """Cross-sectional relative-strength book over SYMBOLS (long winners / short losers)."""
    symbols = _symbols(symbols, tool="backtest_cross_sectional")
    args = ["backtest", "cross-sectional", *symbols]
    args += _option_flags(
        options, tool="backtest_cross_sectional", allowed=_CROSS_SECTIONAL_OPTIONS
    )
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="cross_sectional")


@mcp.tool()
def validate(
    symbol: str,
    strategy: str = "ts_momentum",
    params: dict[str, str] | None = None,
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run the full validation gauntlet on SYMBOL (walk-forward, null, CIs, DSR, CPCV, Verdict)."""
    symbol = _symbol(symbol)
    strategy = _strategy(strategy)
    args = ["validate", symbol, "--strategy", strategy]
    args += _param_flags(strategy, params) + _option_flags(
        options, tool="validate", allowed=_VALIDATE_OPTIONS
    )
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
    symbol = _symbol(symbol)
    strategy = _strategy(strategy)
    args = ["optim", "grid", symbol, "--strategy", strategy]
    args += _grid_flags(strategy, grid)
    args += _option_flags(options, tool="optim_grid", allowed=_OPTIM_OPTIONS)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="optim")


@mcp.tool()
def forecast_run(symbol: str, options: dict[str, str] | None = None) -> dict[str, Any]:
    """Sample probabilistic future OHLCV paths for SYMBOL with the Kronos foundation model.

    Returns the outcome-cone manifest (quantile summary, P(up), pretrain-overlap flag).
    Common ``options``: ``{"horizon": "21", "samples": "100", "context": "400",
    "model": "NeoQuasar/Kronos-small", "device": "cpu", "as-of": "2026-06-30"}``.
    """
    args = ["forecast", "run", _symbol(symbol)]
    args += _option_flags(options, tool="forecast_run", allowed=_FORECAST_RUN_OPTIONS)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="forecast")


@mcp.tool()
def forecast_eval(symbol: str, options: dict[str, str] | None = None) -> dict[str, Any]:
    """Score the Kronos forecaster at rolling origins on SYMBOL (CRPS/coverage/hit-rate
    vs random-walk + bootstrap baselines, split pre/post the assumed pretraining cutoff).

    Common ``options``: ``{"horizon": "21", "stride": "63", "samples": "30"}``.
    """
    args = ["forecast", "eval", _symbol(symbol)]
    args += _option_flags(options, tool="forecast_eval", allowed=_FORECAST_EVAL_OPTIONS)
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="forecast")


@mcp.tool()
def propfirm_run(
    symbol: str | None = None,
    from_run: str | None = None,
    firm: str | None = None,
    params: dict[str, str] | None = None,
    options: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Prop-firm Monte Carlo (firm: topstep|apex|takeprofit). Pass one of SYMBOL / from_run."""
    strategy = _strategy((options or {}).get("strategy", "ts_momentum"))
    args = ["propfirm", "run"]
    if symbol is not None:
        args.append(_symbol(symbol))
    if from_run is not None:
        if not valid_run_id(from_run):
            raise ValueError("from_run must be a 16-character hexadecimal run id")
        args += ["--from-run", from_run]
    if firm is not None:
        if firm not in {"topstep", "apex", "takeprofit"}:
            raise ValueError("firm must be topstep, apex, or takeprofit")
        args += ["--firm", firm]
    args += _param_flags(strategy, params) + _option_flags(
        options, tool="propfirm_run", allowed=_PROPFIRM_OPTIONS
    )
    return _invoke.run_alpha(args, data_dir=_data_dir(), run_type="propfirm")


# --- Workstation v3 control plane (all operations use explicit CLI JSON commands) ------------


@mcp.tool()
def research_capture(idea: str, name: str | None = None) -> _types.ResearchCaptureOut:
    """Capture exact owner wording and return one bounded material-question batch.

    This creates only a draft Research Case. It cannot approve a contract, change a budget,
    reveal sealed data, or reach paper/order capabilities.
    """
    return cast(
        _types.ResearchCaptureOut,
        _control.research_capture(idea, data_dir=_data_dir(), name=name),
    )


@mcp.tool()
def research_get(project_id: str) -> _types.ResearchCaseOut:
    """Read the authoritative Research Case, active contract, next action, and firewall state."""
    return cast(
        _types.ResearchCaseOut,
        _control.research_get(project_id, data_dir=_data_dir()),
    )


@mcp.tool()
def research_propose(
    project_id: str,
    source_pack_id: str,
    answers: dict[str, str],
) -> _types.ResearchProposalOut:
    """Draft an approval-ready exploration contract from exactly three material answers.

    The result still requires a separate human-owner CLI approval. This tool cannot approve its
    own proposal or alter sealed confirmation/final-holdout state.
    """
    return cast(
        _types.ResearchProposalOut,
        _control.research_propose(
            project_id,
            source_pack_id,
            answers,
            data_dir=_data_dir(),
        ),
    )


@mcp.tool()
def research_launch(
    project_id: str,
    stage: Literal["pilot"],
) -> _types.ResearchLaunchOut:
    """Launch the approved synthetic D0 pilot; D1 and D2 runners are unavailable."""
    return cast(
        _types.ResearchLaunchOut,
        _control.research_launch(project_id, stage, data_dir=_data_dir()),
    )


@mcp.tool()
def research_status(project_id: str) -> _types.ResearchCaseOut:
    """Read one case's current phase, execution, budget, blocker, and exact next action."""
    return cast(
        _types.ResearchCaseOut,
        _control.research_get(project_id, data_dir=_data_dir()),
    )


@mcp.tool()
def research_report(project_id: str) -> _types.ResearchReportOut:
    """Read the current progress report or terminal packet without changing research state."""
    return cast(
        _types.ResearchReportOut,
        _control.research_report(project_id, data_dir=_data_dir()),
    )


@mcp.tool()
def build_research_context_packet(
    project_id: str,
    kind: Literal[
        "asset", "research_case", "experiment", "chart", "validation", "strategy_promotion"
    ],
    protocol_id: str | None = None,
    symbol: str | None = None,
) -> _types.ResearchContextPacketOut:
    """Assemble and record one bounded, content-addressed Codex context packet.

    Recording is visibility: the owner can open the exact bytes of every packet ever built.
    This draft-write records context only — it cannot approve, decide, or launch anything.
    """
    return cast(
        _types.ResearchContextPacketOut,
        _control.research_context_build(
            project_id, kind, data_dir=_data_dir(), protocol_id=protocol_id, symbol=symbol
        ),
    )


@mcp.tool()
def get_research_context_packet(packet_id: str) -> _types.ResearchContextPacketOut:
    """Return one recorded context packet byte-identically."""
    return cast(
        _types.ResearchContextPacketOut,
        _control.research_context_get(packet_id, data_dir=_data_dir()),
    )


@mcp.tool()
def add_research_note(
    project_id: str,
    note_kind: Literal[
        "critique", "confounder_review", "test_design", "completeness_review", "synthesis"
    ],
    body: str,
    context_packet_id: str | None = None,
) -> _types.ResearchNoteOut:
    """Append Codex commentary — structurally outside the evidence model, agent-authored only."""
    return cast(
        _types.ResearchNoteOut,
        _control.research_note_add(
            project_id,
            note_kind,
            body,
            data_dir=_data_dir(),
            context_packet_id=context_packet_id,
        ),
    )


@mcp.tool()
def get_research_brief(project_id: str) -> _types.ResearchBriefOut:
    """Build the "Resume with Codex" delta brief: what changed since the previous brief."""
    return cast(
        _types.ResearchBriefOut,
        _control.research_brief(project_id, data_dir=_data_dir()),
    )


@mcp.tool()
def list_research_protocols() -> _types.ResearchProtocolListOut:
    """List the Git-owned research protocol library (content stays owner-reviewed in Git)."""
    return cast(
        _types.ResearchProtocolListOut,
        _control.research_protocols_list(data_dir=_data_dir()),
    )


@mcp.tool()
def get_research_protocol(protocol_id: str) -> _types.ResearchProtocolOut:
    """Read one protocol entry plus its exact content."""
    return cast(
        _types.ResearchProtocolOut,
        _control.research_protocol_get(protocol_id, data_dir=_data_dir()),
    )


@mcp.tool()
def search_research_sources(query: str, limit: int = 50) -> _types.SourceSearchOut:
    """Search LOCAL source records by title/locator/DOI terms; never the network."""
    return cast(
        _types.SourceSearchOut,
        _control.research_sources_search(query, data_dir=_data_dir(), limit=limit),
    )


@mcp.tool()
def get_research_source(source_id: str) -> _types.JsonObject:
    """Read one immutable source record with its typed DOI/year/author descriptors."""
    return _control.research_source_get(source_id, data_dir=_data_dir())


@mcp.tool()
def draft_source_claim(
    project_id: str,
    source_id: str,
    contract_id: str,
    claim_text: str,
    direction: Literal["supports", "contradicts", "contextualizes", "method"],
    strength: Literal["weak", "moderate", "strong"],
    method_summary: str,
    sample_summary: str,
    markets: list[str],
    limitations: str,
    source_anchor: _types.JsonObject | None = None,
) -> _types.SourceClaimOut:
    """Draft one claim-level literature statement (always agent-authored).

    A published paper is never auto-trusted: only the owner's trusted-local CLI screening
    elevates a draft, and the scorecard's literature dimension counts screened claims only.
    """
    return cast(
        _types.SourceClaimOut,
        _control.source_claim_draft(
            project_id,
            data_dir=_data_dir(),
            source_id=source_id,
            contract_id=contract_id,
            claim_text=claim_text,
            direction=direction,
            strength=strength,
            method_summary=method_summary,
            sample_summary=sample_summary,
            markets=markets,
            limitations=limitations,
            source_anchor=source_anchor,
        ),
    )


@mcp.tool()
def get_data_inventory() -> _types.DataInventoryOut:
    """List every stored symbol — the read-only starting point of data feasibility."""
    return cast(_types.DataInventoryOut, _control.data_inventory(data_dir=_data_dir()))


@mcp.tool()
def get_data_quality(symbol: str) -> _types.JsonObject:
    """Read one symbol's source, qualification, and promotion status (read-only)."""
    return _control.data_quality(symbol, data_dir=_data_dir())


@mcp.tool()
def get_data_candles(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
) -> _types.DataCandlesOut:
    """Bounded point-in-time candle preview (last ``limit`` bars, at most 500).

    Reads through the same look-ahead firewall a backtest uses; ``end`` is a knowledge
    cutoff. This preview mirrors the QuantPad discovery bound and is never a bulk feed.
    """
    return cast(
        _types.DataCandlesOut,
        _control.data_candles(symbol, data_dir=_data_dir(), start=start, end=end, limit=limit),
    )


@mcp.tool()
def list_snapshots() -> _types.SnapshotListOut:
    """List every immutable snapshot's manifest summary (id, source, symbols, hash)."""
    return cast(_types.SnapshotListOut, _control.snapshots(data_dir=_data_dir()))


@mcp.tool()
def get_provider_registry() -> _types.ProviderRegistryOut:
    """The redacted provider capability/limitation registry; never probes the network."""
    return cast(_types.ProviderRegistryOut, _control.provider_registry(data_dir=_data_dir()))


@mcp.tool()
def create_strategy_project(
    name: str, hypothesis: str, falsification_criterion: str
) -> _types.ProjectSummaryOut:
    """Create a strategy-development project with a testable hypothesis and rejection rule."""
    return cast(
        _types.ProjectSummaryOut,
        _control.create_project(
            data_dir=_data_dir(),
            name=name,
            hypothesis=hypothesis,
            falsification=falsification_criterion,
        ),
    )


@mcp.tool()
def create_strategy_version(
    project_id: str,
    strategy_name: str,
    source_fingerprint: str,
    definition: dict[str, Any],
    parameter_space: dict[str, Any],
) -> _types.StrategyVersionOut:
    """Create/reuse an immutable content-addressed strategy version in PROJECT_ID."""
    return cast(
        _types.StrategyVersionOut,
        _control.create_version(
            project_id,
            data_dir=_data_dir(),
            strategy_name=strategy_name,
            source_fingerprint=source_fingerprint,
            definition=definition,
            parameter_space=parameter_space,
        ),
    )


@mcp.tool()
def create_experiment_spec(
    project_id: str,
    version_id: str,
    snapshot_id: str,
    universe: list[str],
    split_policy: dict[str, Any],
    costs: dict[str, Any],
    seeds: dict[str, Any],
    stage_config: dict[str, Any] | None = None,
) -> _types.ExperimentSpecOut:
    """Create/reuse a frozen experiment spec; no run or holdout reveal is performed."""
    return cast(
        _types.ExperimentSpecOut,
        _control.create_experiment(
            project_id,
            data_dir=_data_dir(),
            version_id=version_id,
            snapshot_id=snapshot_id,
            universe=universe,
            split_policy=split_policy,
            costs=costs,
            seeds=seeds,
            stage_config=stage_config or {},
        ),
    )


@mcp.tool()
def link_project_run(
    project_id: str,
    experiment_id: str,
    stage: Literal[
        "hypothesis",
        "data",
        "strategy",
        "baseline",
        "oos",
        "robustness",
        "optimization",
        "portfolio",
        "candidate",
        "holdout",
        "paper",
        "decision",
        "kronos",
        "ml",
    ],
    state: Literal["not_started", "ready", "queued", "running", "stale"],
    run_id: str,
) -> _types.StageRunLinkOut:
    """Link one already-completed canonical run to an experiment stage."""
    return cast(
        _types.StageRunLinkOut,
        _control.link_run(
            project_id,
            experiment_id,
            stage,
            state,
            run_id,
            data_dir=_data_dir(),
        ),
    )


@mcp.tool()
def advance_stage_state(
    link_id: str,
    state: Literal["ready", "queued", "running", "stale"],
    reason: str,
) -> _types.StageRunLinkOut:
    """Append one legal lifecycle transition to a cited stage/run link."""
    return cast(
        _types.StageRunLinkOut,
        _control.advance_stage(link_id, state, reason, data_dir=_data_dir()),
    )


@mcp.tool()
def advance_experiment_stage(
    project_id: str,
    experiment_id: str,
    stage: Literal[
        "hypothesis",
        "data",
        "strategy",
        "baseline",
        "oos",
        "robustness",
        "optimization",
        "portfolio",
        "candidate",
        "holdout",
        "paper",
        "decision",
        "kronos",
        "ml",
    ],
    state: Literal["ready", "queued", "running", "stale"],
    reason: str,
) -> _types.ExperimentStageStateOut:
    """Append one legal lifecycle transition before or without a completed run link."""
    return cast(
        _types.ExperimentStageStateOut,
        _control.advance_experiment_stage(
            project_id,
            experiment_id,
            stage,
            state,
            reason,
            data_dir=_data_dir(),
        ),
    )


@mcp.tool()
def record_project_attempt(
    project_id: str,
    experiment_id: str,
    stage: Literal[
        "hypothesis",
        "data",
        "strategy",
        "baseline",
        "oos",
        "robustness",
        "optimization",
        "portfolio",
        "candidate",
        "holdout",
        "paper",
        "decision",
        "kronos",
        "ml",
    ],
    status: Literal[
        "queued",
        "running",
        "completed",
        "passed",
        "warning",
        "failed",
        "pruned",
        "rejected",
        "cancelled",
    ],
    config_fingerprint: str,
    run_id: str | None = None,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> _types.AttemptRecordOut:
    """Record one attempted, failed, pruned, rejected, or completed configuration."""
    return cast(
        _types.AttemptRecordOut,
        _control.record_attempt(
            project_id,
            experiment_id,
            stage,
            status,
            config_fingerprint,
            data_dir=_data_dir(),
            run_id=run_id,
            error=error,
            details=details or {},
        ),
    )


@mcp.tool()
def seal_project_holdout(
    project_id: str,
    experiment_id: str,
    actor: str,
    reason: str,
    start_date: str,
    end_date: str,
) -> _types.HoldoutStateOut:
    """Seal a dated final-holdout window before selection; this cannot reveal its dates."""
    return cast(
        _types.HoldoutStateOut,
        _control.seal_holdout(
            project_id,
            experiment_id,
            actor,
            reason,
            start_date,
            end_date,
            data_dir=_data_dir(),
        ),
    )


@mcp.tool()
def list_projects(limit: int = 50, offset: int = 0) -> _types.ProjectPageOut:
    """List projects with ``items/limit/offset/has_more``; limit is capped at 100."""
    return cast(
        _types.ProjectPageOut,
        _control.list_projects(data_dir=_data_dir(), limit=limit, start=offset),
    )


@mcp.tool()
def get_project(project_id: str, lineage_limit: int = 100) -> _types.ProjectDetailOut:
    """Read typed project lineage with every nested collection capped at 200."""
    return cast(
        _types.ProjectDetailOut,
        _control.get_project(project_id, data_dir=_data_dir(), lineage_limit=lineage_limit),
    )


@mcp.tool()
def get_strategy_version(project_id: str, version_id: str) -> _types.StrategyVersionOut:
    """Read one immutable strategy version by its stable content identifier."""
    return cast(
        _types.StrategyVersionOut,
        _control.get_version(project_id, version_id, data_dir=_data_dir()),
    )


@mcp.tool()
def get_experiment_spec(project_id: str, experiment_id: str) -> _types.ExperimentSpecOut:
    """Read one immutable experiment specification by its stable content identifier."""
    return cast(
        _types.ExperimentSpecOut,
        _control.get_experiment(project_id, experiment_id, data_dir=_data_dir()),
    )


@mcp.tool()
def get_agent_brief(
    project_id: str, evidence_limit: int = 50, as_of: str | None = None
) -> _types.AgentBriefOut:
    """Get a bounded, point-in-time AgentBrief with exact evidence citations and allowed scope."""
    return cast(
        _types.AgentBriefOut,
        _control.agent_brief(
            project_id,
            data_dir=_data_dir(),
            evidence_limit=evidence_limit,
            as_of=as_of,
        ),
    )


@mcp.tool()
def create_development_job(
    kind: str,
    request: dict[str, Any],
    project_id: str | None = None,
    experiment_id: str | None = None,
) -> _types.ControlJobOut:
    """Create a durable queued journal entry only; this tool does not execute arbitrary code."""
    return cast(
        _types.ControlJobOut,
        _control.create_job(
            kind,
            request,
            data_dir=_data_dir(),
            project_id=project_id,
            experiment_id=experiment_id,
        ),
    )


@mcp.tool()
def list_development_jobs(limit: int = 50, offset: int = 0) -> _types.ControlJobPageOut:
    """List durable project-job journals with an explicit bounded continuation flag."""
    return cast(
        _types.ControlJobPageOut,
        _control.list_jobs(data_dir=_data_dir(), limit=limit, start=offset),
    )


@mcp.tool()
def get_development_job(
    job_id: str, event_limit: int = 100, event_offset: int = 0
) -> _types.ControlJobDetailOut:
    """Page backward through at most 200 newest-tail journal events for one job."""
    return cast(
        _types.ControlJobDetailOut,
        _control.get_job(
            job_id,
            data_dir=_data_dir(),
            event_limit=event_limit,
            event_offset=event_offset,
        ),
    )


@mcp.tool()
def plan_development_suite(
    project_id: str,
    experiment_id: str,
    action: Literal[
        "baseline",
        "inner_oos",
        "three_null_families",
        "monte_carlo",
        "optimize_grid",
        "fixed_stress",
        "portfolio_cross_asset",
        "qlib",
        "kronos",
        "holdout_reveal",
        "paper_preflight",
    ],
) -> _types.SuitePlanOut:
    """Preview one immutable allowlisted stage plan; sealed holdout dates remain redacted."""
    return cast(
        _types.SuitePlanOut,
        _control.suite_plan(project_id, experiment_id, action, data_dir=_data_dir()),
    )


@mcp.tool()
def launch_development_suite(
    project_id: str,
    experiment_id: str,
    action: Literal[
        "baseline",
        "inner_oos",
        "three_null_families",
        "monte_carlo",
        "optimize_grid",
        "fixed_stress",
        "portfolio_cross_asset",
        "qlib",
        "kronos",
        "paper_preflight",
    ],
) -> _types.SuiteLaunchOut:
    """Launch one ready allowlisted stage as a durable job; holdout reveal is unavailable."""
    return cast(
        _types.SuiteLaunchOut,
        _control.launch_suite(project_id, experiment_id, action, data_dir=_data_dir()),
    )


@mcp.tool()
def cancel_development_suite(
    job_id: str,
    reason: str = "agent requested cancellation",
) -> _types.JobCancellationOut:
    """Durably request cancellation; the owning suite worker observes it without PID access."""
    return cast(
        _types.JobCancellationOut,
        _control.cancel_job(job_id, data_dir=_data_dir(), reason=reason),
    )


@mcp.tool()
def reconcile_development_jobs(
    stale_after_seconds: int = 60,
) -> _types.JobReconciliationOut:
    """Fail only nonterminal journals with a heartbeat stale for at least the declared cutoff."""
    return cast(
        _types.JobReconciliationOut,
        _control.reconcile_jobs(data_dir=_data_dir(), stale_after_seconds=stale_after_seconds),
    )


@mcp.tool()
def plan_ml_experiment(project_id: str, experiment_id: str) -> _types.SuitePlanOut:
    """Resolve the isolated Qlib input/train/replay plan without exposing filesystem paths."""
    return cast(
        _types.SuitePlanOut,
        _control.suite_plan(project_id, experiment_id, "qlib", data_dir=_data_dir()),
    )


@mcp.tool()
def launch_ml_experiment(project_id: str, experiment_id: str) -> _types.SuiteLaunchOut:
    """Launch managed Qlib preparation, isolated training, validation, and canonical replay."""
    return cast(
        _types.SuiteLaunchOut,
        _control.launch_suite(project_id, experiment_id, "qlib", data_dir=_data_dir()),
    )


@mcp.tool()
def search_evidence(
    asset: str | None = None,
    project_id: str | None = None,
    status: Literal["draft", "corroborated", "rejected", "superseded"] | None = None,
    as_of: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> _types.EvidencePageOut:
    """Search latest point-in-time evidence revisions; limit is capped at 100."""
    return cast(
        _types.EvidencePageOut,
        _control.search_evidence(
            data_dir=_data_dir(),
            asset=asset,
            project_id=project_id,
            status=status,
            as_of=as_of,
            limit=limit,
            start=offset,
        ),
    )


@mcp.tool()
def search_asset_evidence(
    asset: str,
    project_id: str | None = None,
    status: Literal["draft", "corroborated", "rejected", "superseded"] | None = None,
    as_of: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> _types.EvidencePageOut:
    """Search prior findings and negative results for one required asset at an as-of time."""
    return cast(
        _types.EvidencePageOut,
        _control.search_evidence(
            data_dir=_data_dir(),
            asset=asset,
            project_id=project_id,
            status=status,
            as_of=as_of,
            limit=limit,
            start=offset,
        ),
    )


@mcp.tool()
def get_evidence(evidence_id: str, revision_limit: int = 100) -> _types.EvidenceDetailOut:
    """Read current evidence plus at most 200 immutable revisions."""
    return cast(
        _types.EvidenceDetailOut,
        _control.get_evidence(evidence_id, data_dir=_data_dir(), revision_limit=revision_limit),
    )


@mcp.tool()
def draft_evidence(
    claim: str,
    assets: list[str],
    frozen_universe: list[str],
    method: str,
    knowledge_at: str,
    author: str,
    source_run_id: str,
    source_artifact: str,
    source_field: str,
    timeframe: str = "1d",
    market_data_cutoff: str | None = None,
    project_id: str | None = None,
    strategy_version_id: str | None = None,
    experiment_id: str | None = None,
    metric_name: str | None = None,
    metric_value: float | None = None,
    metric_unit: str | None = None,
    row_selector: dict[str, Any] | None = None,
    counterevidence: list[str] | None = None,
    contradiction_ids: list[str] | None = None,
) -> _types.EvidenceRecordOut:
    """Create an exactly cited evidence record; revision one is always ``draft``."""
    body: dict[str, object] = {
        "claim": claim,
        "assets": assets,
        "frozen_universe": frozen_universe,
        "method": method,
        "knowledge_at": knowledge_at,
        "author": author,
        "author_kind": "agent",
        "source_run_id": source_run_id,
        "source_artifact": source_artifact,
        "source_field": source_field,
        "timeframe": timeframe,
        "market_data_cutoff": market_data_cutoff,
        "project_id": project_id,
        "strategy_version_id": strategy_version_id,
        "experiment_id": experiment_id,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_unit": metric_unit,
        "row_selector": row_selector or {},
        "counterevidence": counterevidence or [],
        "contradiction_ids": contradiction_ids or [],
    }
    return cast(
        _types.EvidenceRecordOut,
        _control.draft_evidence(body, data_dir=_data_dir()),
    )


@mcp.tool()
def review_evidence(
    evidence_id: str,
    status: Literal["draft", "rejected", "superseded"],
    author: str,
    claim: str | None = None,
    counterevidence: list[str] | None = None,
    contradiction_ids: list[str] | None = None,
    source_run_id: str | None = None,
    source_artifact: str | None = None,
    source_field: str | None = None,
    row_selector: dict[str, Any] | None = None,
) -> _types.EvidenceRecordOut:
    """Append a cited review revision without mutating prior evidence."""
    body: dict[str, object] = {
        "status": status,
        "author": author,
        "author_kind": "agent",
        "claim": claim,
        "counterevidence": counterevidence,
        "contradiction_ids": contradiction_ids,
        "source_run_id": source_run_id,
        "source_artifact": source_artifact,
        "source_field": source_field,
        "row_selector": row_selector,
    }
    return cast(
        _types.EvidenceRecordOut,
        _control.review_evidence(evidence_id, body, data_dir=_data_dir()),
    )


# --- read tools (no subprocess) --------------------------------------------------------------


@mcp.tool()
def get_run(run_id: str) -> _types.LegacyRunManifestOut:
    """Fetch one validated manifest capped at 1 MB; retained for legacy callers."""
    return cast(_types.LegacyRunManifestOut, _runs.get_run(run_id, data_dir=_data_dir()))


@mcp.tool()
def list_runs(limit: int = 100, offset: int = 0) -> list[_types.LegacyRunSummaryOut]:
    """List one deterministic legacy run page; limit is capped at 500."""
    return cast(
        list[_types.LegacyRunSummaryOut],
        _runs.list_runs(data_dir=_data_dir(), limit=limit, offset=offset),
    )


@mcp.tool()
def list_strategies() -> list[str]:
    """List the registered strategy names available to backtest / validate / optim."""
    return list(known_strategies())


@mcp.tool()
def get_chart_bundle(
    run_id: str,
    limit: int = 2_000,
    bar_limit: int = 25_000,
    start: str | None = None,
    end: str | None = None,
) -> _types.ChartBundleOut:
    """Read bounded frozen bars plus exact decision/order/fill/trade and annotation evidence."""
    return cast(
        _types.ChartBundleOut,
        run_projection.chart_bundle(
            run_id,
            data_dir=_data_dir(),
            limit=limit,
            bar_limit=bar_limit,
            start=start,
            end=end,
        ),
    )


@mcp.tool()
def get_portfolio_analytics(
    run_id: str,
    timestamp_limit: int = 2_000,
    symbol_limit: int = 50,
) -> _types.PortfolioAnalyticsOut:
    """Read bounded causal sleeve allocations, exposure, and aligned-OOS correlations."""
    result = run_projection.portfolio_analytics(
        run_id,
        data_dir=_data_dir(),
        timestamp_limit=timestamp_limit,
        symbol_limit=symbol_limit,
    )
    if result is None:
        raise DataError(
            "portfolio analytics unavailable; rerun this legacy portfolio for artifacts"
        )
    return cast(_types.PortfolioAnalyticsOut, result)


@mcp.tool()
def compare_runs(run_ids: list[str]) -> _types.RunComparisonOut:
    """Compare 2..8 immutable runs using bounded metrics with exact manifest-field citations."""
    return cast(
        _types.RunComparisonOut,
        run_projection.compare_runs(run_ids, data_dir=_data_dir()),
    )


def main() -> None:
    """Entry point: run the stdio MCP server (Claude Code / Desktop launch this)."""
    mcp.run()


if __name__ == "__main__":
    main()
