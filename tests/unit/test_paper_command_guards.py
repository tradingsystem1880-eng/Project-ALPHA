"""Small fail-closed helpers behind the paper command surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from alpha_cli import paper_cmds, paper_store
from alpha_core import DataError


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"lookback": 0}, "lookback"),
        ({"skip": -1}, "skip"),
        ({"vol_window": 1}, "vol_window"),
        ({"rebalance_every": 0}, "rebalance_every"),
        ({"starting_cash": float("nan")}, "starting_cash"),
    ],
)
def test_paper_spec_rejects_invalid_controls(overrides: dict[str, object], match: str) -> None:
    kwargs: dict[str, object] = {
        "strategy": "ts_momentum",
        "param": None,
        "starting_cash": 100_000.0,
        "lookback": 20,
        "skip": 1,
        "vol_window": 10,
        "target_vol": 0.15,
        "rebalance_every": 1,
        "max_leverage": 1.0,
    }
    kwargs.update(overrides)
    with pytest.raises(DataError, match=match):
        paper_cmds._spec(**kwargs)  # type: ignore[arg-type]  # noqa: SLF001


def test_required_value_and_utc_timestamp_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_TEST_VALUE", raising=False)
    with pytest.raises(DataError, match="MISSING_TEST_VALUE"):
        paper_cmds._required_value(None, "MISSING_TEST_VALUE")  # noqa: SLF001
    assert paper_cmds._required_value(" value ", "unused") == "value"  # noqa: SLF001
    with pytest.raises(DataError, match="explicit UTC offset"):
        paper_cmds._utc_timestamp("2026-08-03T10:00:00", "cutoff")  # noqa: SLF001
    assert paper_cmds._utc_timestamp(  # noqa: SLF001
        "2026-08-03T20:00:00+10:00", "cutoff"
    ) == datetime(2026, 8, 3, 10, tzinfo=UTC)


def _ibkr_session(data_dir: Path) -> str:
    row = paper_store.create_session(
        data_dir,
        provider="ibkr",
        symbol="SPY",
        instrument_id="SPY.ARCA",
        strategy="ts_momentum",
        strategy_params={},
        snapshot_id="spy",
        pid=1,
        execution_mode="ibkr_paper",
        account_alias="DU…4567",
        risk_profile_id="ibkr-equity-paper-v1",
        decision_artifact_id="a" * 64,
    )
    return str(row["session_id"])


def test_expected_position_uses_latest_valid_journal_state(tmp_path: Path) -> None:
    assert paper_cmds._expected_ibkr_position(tmp_path, "SPY.ARCA") == 0.0  # noqa: SLF001
    session_id = _ibkr_session(tmp_path)
    paper_store.append_event(tmp_path, session_id, "position", {"net_units": 7.0})
    assert paper_cmds._expected_ibkr_position(tmp_path, "SPY.ARCA") == 7.0  # noqa: SLF001


def test_expected_position_rejects_ambiguous_or_failed_journal(tmp_path: Path) -> None:
    session_id = _ibkr_session(tmp_path)
    paper_store.append_event(tmp_path, session_id, "order", {"quantity": 1.0})
    with pytest.raises(DataError, match="lacks a final position"):
        paper_cmds._expected_ibkr_position(tmp_path, "SPY.ARCA")  # noqa: SLF001
    paper_store.finish_session(
        tmp_path,
        session_id,
        status="failed",
        terminal_error="injected",
    )
    with pytest.raises(DataError, match="requires reconciliation"):
        paper_cmds._expected_ibkr_position(tmp_path, "SPY.ARCA")  # noqa: SLF001
