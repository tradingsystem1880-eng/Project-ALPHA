"""Characterization golden for ``_artifacts.write_execution_trace`` (pre-decomposition guard).

``write_execution_trace`` is a ~274-line inline event-graph builder that is about to be
decomposed. This module pins its CURRENT observable behavior at content level (sorted records
plus schema strings, never raw parquet bytes) against a committed fixture generated from the
implementation as of 2026-07-20: one non-trivial in-memory ``BacktestResult`` with two decision
rounds, a multi-order decision, interleaved order/fill sequences between decision groups, an
orphan order (no prior decision), and an orphan trade (no matching exit fill).

Behavior deliberately pinned by the golden:

* Consolidated ``execution_trace.parquet`` sequence ids are POSITIONAL (1..N over the sorted
  event stream); engine order/fill sequence ids survive only in ``orders.parquet`` /
  ``fills.parquet``.
* Decision ids are remapped from decision-local to global position AFTER consolidation, so a
  decision that follows interleaved orders/fills keeps one global id everywhere (local 3 -> 10).
* Same-timestamp same-rank events tie-break LEXICOGRAPHICALLY on the internal string key, so
  engine order sequence 10 sorts between 1 and 3 (``"order:10" < "order:3"``), not last.
* Orphaned orders (no prior same-instrument decision) and orphaned trades (no matching exit
  fill) get silently null parents, while orphaned indicator/annotation evidence fails loud with
  ``DataError`` before ANY artifact is written.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_backtest.results import BacktestResult, FillTrace, OrderTrace, Trade
from alpha_cli import _artifacts
from alpha_core import (
    ChartAnchor,
    ChartAnnotationTrace,
    DataError,
    DecisionTrace,
    IndicatorTrace,
)

_GOLDEN_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "execution_trace_golden" / "expected.json"
)

# alphabetical, matching sorted(snapshot) keys
_SIDECARS = (
    "chart_annotations.parquet",
    "decision_trace.parquet",
    "execution_trace.parquet",
    "fills.parquet",
    "indicator_series.parquet",
    "orders.parquet",
)

_AAPL = "AAPL.SIM"
_MSFT = "MSFT.SIM"
_TSLA = "TSLA.SIM"

_JAN2_CLOSE = datetime(2026, 1, 2, 23, tzinfo=UTC)
_JAN3_CLOSE = datetime(2026, 1, 3, 23, tzinfo=UTC)
_JAN5_CLOSE = datetime(2026, 1, 5, 23, tzinfo=UTC)
_JAN6_OPEN = datetime(2026, 1, 6, tzinfo=UTC)
_JAN6_CLOSE = datetime(2026, 1, 6, 23, tzinfo=UTC)
_JAN7_OPEN = datetime(2026, 1, 7, tzinfo=UTC)


def golden_result() -> BacktestResult:
    """A deterministic non-trivial causal graph; every input tuple is deliberately shuffled.

    The writer must sort decisions/trades/indicators/annotations itself, so the golden also pins
    the sorting conventions. Engine order sequence ids are 1/10/3/6/4/5 on purpose: 1 and 10
    both belong to the first AAPL decision (multi-order decision) and 10 exposes the
    lexicographic same-timestamp tie-break.
    """
    return BacktestResult(
        orders=6,
        fills=5,
        rejected=1,
        equity_curve=[],
        trades=[
            Trade(
                instrument_id=_MSFT,
                side="SELL",
                quantity=4.0,
                entry_price=210.0,
                exit_price=208.5,
                entry_ts=_JAN6_OPEN,
                exit_ts=_JAN7_OPEN,
                realized_pnl=6.0,
                realized_return=0.00714,
            ),
            Trade(  # orphan: no TSLA fills exist at its exit timestamp
                instrument_id=_TSLA,
                side="BUY",
                quantity=1.0,
                entry_price=50.0,
                exit_price=51.0,
                entry_ts=_JAN6_OPEN,
                exit_ts=_JAN7_OPEN,
                realized_pnl=1.0,
                realized_return=0.02,
            ),
            Trade(
                instrument_id=_AAPL,
                side="BUY",
                quantity=10.0,
                entry_price=100.55,
                exit_price=102.0,
                entry_ts=_JAN6_OPEN,
                exit_ts=_JAN7_OPEN,
                realized_pnl=14.5,
                realized_return=0.0144,
            ),
        ],
        decision_trace=(
            DecisionTrace(
                ts=_JAN6_CLOSE,
                instrument_id=_MSFT,
                signal=0,
                target_quantity=0.0,
                reason="exit short",
            ),
            DecisionTrace(
                ts=_JAN5_CLOSE,
                instrument_id=_AAPL,
                signal=1,
                target_quantity=10.0,
                reason="enter long",
            ),
            DecisionTrace(
                ts=_JAN6_CLOSE,
                instrument_id=_AAPL,
                signal=0,
                target_quantity=0.0,
                reason="exit long",
            ),
            DecisionTrace(
                ts=_JAN5_CLOSE,
                instrument_id=_MSFT,
                signal=-1,
                target_quantity=4.0,
                reason="enter short",
            ),
        ),
        order_trace=(
            OrderTrace(
                sequence_id=1,
                ts=_JAN6_OPEN,
                instrument_id=_AAPL,
                side="BUY",
                quantity=6.0,
                filled_quantity=6.0,
                status="FILLED",
            ),
            OrderTrace(  # second order from the SAME first AAPL decision
                sequence_id=10,
                ts=_JAN6_OPEN,
                instrument_id=_AAPL,
                side="BUY",
                quantity=4.0,
                filled_quantity=4.0,
                status="FILLED",
            ),
            OrderTrace(
                sequence_id=3,
                ts=_JAN6_OPEN,
                instrument_id=_MSFT,
                side="SELL",
                quantity=4.0,
                filled_quantity=4.0,
                status="FILLED",
            ),
            OrderTrace(  # orphan: TSLA has no decision anywhere
                sequence_id=6,
                ts=_JAN6_OPEN,
                instrument_id=_TSLA,
                side="BUY",
                quantity=1.0,
                filled_quantity=0.0,
                status="REJECTED",
            ),
            OrderTrace(
                sequence_id=4,
                ts=_JAN7_OPEN,
                instrument_id=_AAPL,
                side="SELL",
                quantity=10.0,
                filled_quantity=10.0,
                status="FILLED",
            ),
            OrderTrace(
                sequence_id=5,
                ts=_JAN7_OPEN,
                instrument_id=_MSFT,
                side="BUY",
                quantity=4.0,
                filled_quantity=4.0,
                status="FILLED",
            ),
        ),
        fill_trace=(
            FillTrace(
                sequence_id=1,
                order_sequence_id=1,
                ts=_JAN6_OPEN,
                instrument_id=_AAPL,
                side="BUY",
                quantity=6.0,
                price=100.5,
            ),
            FillTrace(
                sequence_id=2,
                order_sequence_id=10,
                ts=_JAN6_OPEN,
                instrument_id=_AAPL,
                side="BUY",
                quantity=4.0,
                price=100.625,
            ),
            FillTrace(
                sequence_id=3,
                order_sequence_id=3,
                ts=_JAN6_OPEN,
                instrument_id=_MSFT,
                side="SELL",
                quantity=4.0,
                price=210.0,
            ),
            FillTrace(
                sequence_id=4,
                order_sequence_id=4,
                ts=_JAN7_OPEN,
                instrument_id=_AAPL,
                side="SELL",
                quantity=10.0,
                price=102.0,
            ),
            FillTrace(
                sequence_id=5,
                order_sequence_id=5,
                ts=_JAN7_OPEN,
                instrument_id=_MSFT,
                side="BUY",
                quantity=4.0,
                price=208.5,
            ),
        ),
        indicator_trace=(
            IndicatorTrace(
                ts=_JAN6_CLOSE, instrument_id=_MSFT, name="close", value=209.5, unit="price"
            ),
            IndicatorTrace(
                ts=_JAN5_CLOSE, instrument_id=_AAPL, name="momentum_63", value=0.05, unit="ratio"
            ),
            IndicatorTrace(
                ts=_JAN5_CLOSE, instrument_id=_MSFT, name="close", value=211.0, unit="price"
            ),
            IndicatorTrace(
                ts=_JAN6_CLOSE, instrument_id=_AAPL, name="close", value=101.5, unit="price"
            ),
            IndicatorTrace(
                ts=_JAN5_CLOSE, instrument_id=_AAPL, name="close", value=100.0, unit="price"
            ),
        ),
        chart_annotations=(
            ChartAnnotationTrace(
                decision_ts=_JAN6_CLOSE,
                instrument_id=_AAPL,
                kind="line",
                label="exit level",
                unit="price",
                reason="flatten at target",
                anchors=(
                    ChartAnchor(ts=_JAN5_CLOSE, value=101.5),
                    ChartAnchor(ts=_JAN6_CLOSE, value=101.5),
                ),
            ),
            ChartAnnotationTrace(
                decision_ts=_JAN5_CLOSE,
                instrument_id=_MSFT,
                kind="zone",
                label="short band",
                unit="price",
                reason="mean-reversion band",
                anchors=(
                    ChartAnchor(ts=_JAN2_CLOSE, value=212.0),
                    ChartAnchor(ts=_JAN5_CLOSE, value=208.0),
                ),
            ),
            ChartAnnotationTrace(  # three anchors -> anchor_index expansion 0..2
                decision_ts=_JAN5_CLOSE,
                instrument_id=_AAPL,
                kind="polyline",
                label="entry channel",
                unit="price",
                reason="breakout channel",
                anchors=(
                    ChartAnchor(ts=_JAN2_CLOSE, value=98.0),
                    ChartAnchor(ts=_JAN3_CLOSE, value=99.0),
                    ChartAnchor(ts=_JAN5_CLOSE, value=100.0),
                ),
            ),
        ),
    )


def snapshot_tables(rdir: Path) -> dict[str, Any]:
    """Content-level snapshot of every artifact in ``rdir``: schema strings + sorted records."""
    tables: dict[str, Any] = {}
    for path in sorted(rdir.iterdir()):
        frame = pl.read_parquet(path)
        records = [
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in row.items()
            }
            for row in frame.to_dicts()
        ]
        records.sort(key=lambda record: json.dumps(record, sort_keys=True))
        tables[path.name] = {
            "schema": [{"name": name, "dtype": str(dtype)} for name, dtype in frame.schema.items()],
            "rows": records,
        }
    return tables


def test_execution_trace_matches_committed_golden(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    _artifacts.write_execution_trace(rdir, golden_result())

    # Structural spot-checks first: they document WHY the golden looks the way it does and give
    # readable failures before the full-content comparison below.
    trace = pl.read_parquet(rdir / "execution_trace.parquet")
    assert trace["sequence_id"].to_list() == list(range(1, 19))  # positional, contiguous

    decisions = pl.read_parquet(rdir / "decision_trace.parquet")
    # decision-local ids 1..4 remapped to global positions: interleaved orders/fills shift the
    # second decision round to 10/11.
    assert decisions["sequence_id"].to_list() == [1, 2, 10, 11]

    orders = pl.read_parquet(rdir / "orders.parquet")
    jan6_aapl = orders.filter((pl.col("instrument_id") == _AAPL) & (pl.col("ts") == _JAN6_OPEN))
    assert jan6_aapl["sequence_id"].to_list() == [1, 10]
    assert jan6_aapl["decision_sequence_id"].to_list() == [1, 1]  # one decision, two orders
    assert orders.filter(pl.col("instrument_id") == _TSLA)["decision_sequence_id"].to_list() == [
        None
    ]  # orphan order: silently null, no raise

    # Lexicographic same-ts tie-break: engine order 10 ("order:10") sorts before engine order 3
    # ("order:3"), so the four Jan-6-open order events take global ids 3..6 in this order.
    jan6_orders = trace.filter((pl.col("event_type") == "order") & (pl.col("ts") == _JAN6_OPEN))
    assert jan6_orders["sequence_id"].to_list() == [3, 4, 5, 6]
    assert jan6_orders["instrument_id"].to_list() == [_AAPL, _AAPL, _MSFT, _TSLA]
    assert jan6_orders["quantity"].to_list() == [6.0, 4.0, 4.0, 1.0]
    # ... and the fill that references engine order 10 (price 100.625) parents to global id 4,
    # proving order 10 got position 4 (a numeric tie-break would have put it last, at 6).
    partial = trace.filter((pl.col("event_type") == "fill") & (pl.col("price") == 100.625))
    assert partial["parent_sequence_id"].to_list() == [4]

    trades = trace.filter(pl.col("event_type") == "trade")
    assert trades["instrument_id"].to_list() == [_AAPL, _MSFT, _TSLA]
    assert trades["parent_sequence_id"].to_list() == [14, 15, None]  # orphan trade: null parent

    # The guard: FULL row-level content of every sidecar equals the committed fixture.
    actual = snapshot_tables(rdir)
    assert sorted(actual) == list(_SIDECARS)
    expected: dict[str, Any] = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    assert actual == expected


def test_empty_result_writes_all_six_sidecars_with_golden_schemas(tmp_path: Path) -> None:
    """The empty-frame branch must pin the exact same schemas as the populated branch."""
    rdir = tmp_path / "runs" / "empty"
    _artifacts.write_execution_trace(
        rdir, BacktestResult(orders=0, fills=0, trades=[], equity_curve=[])
    )
    actual = snapshot_tables(rdir)
    expected: dict[str, Any] = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    assert sorted(actual) == list(_SIDECARS)
    for name, table in actual.items():
        assert table["rows"] == []
        assert table["schema"] == expected[name]["schema"]


def test_duplicate_decision_key_raises_before_any_artifact(tmp_path: Path) -> None:
    """Two decisions sharing (ts, instrument) are ambiguous even with different reasons."""
    rdir = tmp_path / "runs" / "duplicate"
    result = BacktestResult(
        orders=0,
        fills=0,
        trades=[],
        equity_curve=[],
        decision_trace=(
            DecisionTrace(
                ts=_JAN5_CLOSE,
                instrument_id=_AAPL,
                signal=1,
                target_quantity=10.0,
                reason="first",
            ),
            DecisionTrace(
                ts=_JAN5_CLOSE,
                instrument_id=_AAPL,
                signal=0,
                target_quantity=0.0,
                reason="second",
            ),
        ),
    )
    with pytest.raises(DataError, match="causal decision evidence is ambiguous"):
        _artifacts.write_execution_trace(rdir, result)
    assert not rdir.exists()  # fail-loud happens before the first publish


def test_orphaned_indicator_evidence_raises_before_any_artifact(tmp_path: Path) -> None:
    """An indicator keyed to a (ts, instrument) with no decision fails loud, writing nothing."""
    rdir = tmp_path / "runs" / "orphan-indicator"
    result = BacktestResult(
        orders=0,
        fills=0,
        trades=[],
        equity_curve=[],
        decision_trace=(
            DecisionTrace(
                ts=_JAN5_CLOSE,
                instrument_id=_MSFT,  # decision exists, but for another instrument
                signal=1,
                target_quantity=1.0,
                reason="enter",
            ),
        ),
        indicator_trace=(
            IndicatorTrace(
                ts=_JAN5_CLOSE, instrument_id=_AAPL, name="close", value=100.0, unit="price"
            ),
        ),
    )
    with pytest.raises(DataError, match="causal evidence has no matching decision"):
        _artifacts.write_execution_trace(rdir, result)
    assert not rdir.exists()


def test_orphaned_annotation_evidence_raises_before_any_artifact(tmp_path: Path) -> None:
    """An annotation whose decision_ts matches no decision fails loud, writing nothing."""
    rdir = tmp_path / "runs" / "orphan-annotation"
    result = BacktestResult(
        orders=0,
        fills=0,
        trades=[],
        equity_curve=[],
        decision_trace=(
            DecisionTrace(
                ts=_JAN5_CLOSE,
                instrument_id=_AAPL,
                signal=1,
                target_quantity=1.0,
                reason="enter",
            ),
        ),
        chart_annotations=(
            ChartAnnotationTrace(
                decision_ts=_JAN6_CLOSE,  # no decision at this timestamp
                instrument_id=_AAPL,
                kind="line",
                label="level",
                unit="price",
                reason="evidence",
                anchors=(
                    ChartAnchor(ts=_JAN5_CLOSE, value=100.0),
                    ChartAnchor(ts=_JAN6_CLOSE, value=101.0),
                ),
            ),
        ),
    )
    with pytest.raises(DataError, match="causal evidence has no matching decision"):
        _artifacts.write_execution_trace(rdir, result)
    assert not rdir.exists()


def test_dangling_fill_order_reference_keeps_silent_null_parent(tmp_path: Path) -> None:
    """Characterizes the asymmetry: a fill referencing a nonexistent order does NOT raise.

    The dangling engine id survives verbatim in ``fills.parquet`` while the consolidated event's
    ``parent_sequence_id`` is silently null — unlike indicator/annotation orphans, which fail
    loud (see the tests above).
    """
    rdir = tmp_path / "runs" / "dangling-fill"
    result = BacktestResult(
        orders=0,
        fills=1,
        trades=[],
        equity_curve=[],
        decision_trace=(
            DecisionTrace(
                ts=_JAN5_CLOSE,
                instrument_id=_AAPL,
                signal=1,
                target_quantity=5.0,
                reason="enter",
            ),
        ),
        fill_trace=(
            FillTrace(
                sequence_id=1,
                order_sequence_id=99,  # no such order anywhere
                ts=_JAN6_OPEN,
                instrument_id=_AAPL,
                side="BUY",
                quantity=5.0,
                price=100.0,
            ),
        ),
    )
    _artifacts.write_execution_trace(rdir, result)

    fills = pl.read_parquet(rdir / "fills.parquet")
    assert fills["order_sequence_id"].to_list() == [99]
    trace = pl.read_parquet(rdir / "execution_trace.parquet")
    fill_events = trace.filter(pl.col("event_type") == "fill")
    assert fill_events["parent_sequence_id"].to_list() == [None]
    assert pl.read_parquet(rdir / "orders.parquet").height == 0
