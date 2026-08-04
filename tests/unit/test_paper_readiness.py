"""Machine evidence, never elapsed time, determines paper readiness."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from alpha_cli import paper_readiness, paper_store


def _session(data_dir: Path, *, ibkr: bool) -> str:
    row = paper_store.create_session(
        data_dir,
        provider="ibkr" if ibkr else "binance",
        symbol="SPY" if ibkr else "BTC/USDT",
        instrument_id="SPY.ARCA" if ibkr else "BTCUSDT.BINANCE",
        strategy="connectivity_probe" if ibkr else "ts_momentum",
        strategy_params={},
        snapshot_id="evidence",
        execution_mode="ibkr_paper" if ibkr else "local_sandbox",
        account_alias="DU1234567" if ibkr else None,
        risk_profile_id="ibkr-equity-paper-v1" if ibkr else "crypto-sandbox-v1",
        started_at=datetime(2026, 8, 3, tzinfo=UTC),
    )
    return str(row["session_id"])


def test_empty_or_elapsed_history_never_passes(tmp_path: Path) -> None:
    report = paper_readiness.readiness_report(tmp_path)
    assert report["paper_passed"] is False
    assert report["status"] == "pending"
    assert report["derived_from_elapsed_time"] is False


def test_every_scenario_requires_a_machine_journal_event(tmp_path: Path) -> None:
    sandbox = _session(tmp_path, ibkr=False)
    ibkr = _session(tmp_path, ibkr=True)
    for mode, scenario, event_type, minimum_count in paper_readiness.required_scenarios().values():
        for _ in range(minimum_count):
            paper_store.append_event(
                tmp_path,
                ibkr if mode == "ibkr_paper" else sandbox,
                event_type,
                {"scenario": scenario, "passed": True},
            )

    report = paper_readiness.readiness_report(tmp_path)
    assert report["paper_passed"] is True
    assert report["futures_research_supported"] is False

    paper_store.append_event(
        tmp_path,
        ibkr,
        "reconciliation_warning",
        {"reason": "unresolved fill"},
    )
    blocked = paper_readiness.readiness_report(tmp_path)
    assert blocked["paper_passed"] is False
    assert blocked["blocking_events"]
