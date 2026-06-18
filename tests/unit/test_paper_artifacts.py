"""Unit tests for the offline paper-session artifact schema (Phase 4c)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_paper.artifacts import (
    AuditLog,
    new_session_id,
    read_session,
    session_dir,
    write_equity_curve,
    write_session,
)
from alpha_paper.errors import PaperError


def test_new_session_id_is_deterministic_with_injected_clock_and_suffix() -> None:
    when = datetime(2026, 6, 18, 4, 58, 1, tzinfo=UTC)
    assert new_session_id(when, "abcd1234") == "20260618T045801Z-abcd1234"


def test_session_dir_layout(tmp_path: Path) -> None:
    assert session_dir(tmp_path, "sid") == tmp_path / "paper" / "sid"


def test_write_then_read_session_round_trips(tmp_path: Path) -> None:
    sdir = session_dir(tmp_path, "sid")
    payload = {"symbol": "BTC/USDT", "exchange": "coinbase", "started_at": "2026-06-18T04:58:01Z"}
    write_session(sdir, payload)
    assert read_session(sdir) == payload


def test_write_session_refuses_credential_like_fields(tmp_path: Path) -> None:
    sdir = session_dir(tmp_path, "sid")
    with pytest.raises(PaperError, match="credential-like"):
        write_session(sdir, {"paper_api_key": "leak", "symbol": "BTC/USDT"})
    with pytest.raises(PaperError, match="credential-like"):
        write_session(sdir, {"api_secret": "leak"})
    assert not (sdir / "session.json").exists()  # nothing written when it fails loud


def test_audit_log_appends_jsonlines_in_order(tmp_path: Path) -> None:
    ticks = iter(
        [
            datetime(2026, 6, 18, 0, 0, 0, tzinfo=UTC),
            datetime(2026, 6, 18, 0, 0, 1, tzinfo=UTC),
        ]
    )
    log = AuditLog(session_dir(tmp_path, "sid"), clock=lambda: next(ticks))
    log.record("decision", target_units=1.5)
    log.record("order", side="BUY", qty=1.0)
    records = log.read()
    assert [r["event"] for r in records] == ["decision", "order"]
    assert records[0]["target_units"] == 1.5
    assert records[0]["ts"] == "2026-06-18T00:00:00+00:00"


def test_equity_curve_parquet_round_trips(tmp_path: Path) -> None:
    sdir = session_dir(tmp_path, "sid")
    curve = [
        (datetime(2026, 6, 18, 0, 0, tzinfo=UTC), 1_000_000.0),
        (datetime(2026, 6, 19, 0, 0, tzinfo=UTC), 1_001_000.0),
    ]
    write_equity_curve(sdir, curve)
    frame = pl.read_parquet(sdir / "equity_curve.parquet")
    assert frame["equity"].to_list() == [1_000_000.0, 1_001_000.0]
