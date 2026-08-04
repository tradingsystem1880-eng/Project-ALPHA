"""Machine-derived operational paper acceptance report.

Elapsed time and operator assertions are deliberately absent. A requirement is satisfied only by
an immutable journal event emitted by the corresponding integration path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from alpha_cli import paper_store

_REQUIREMENTS: Final[dict[str, tuple[str, str, str, int]]] = {
    "binance.network_smoke": ("local_sandbox", "binance_network_smoke", "connection", 1),
    "binance.utc_rollover": ("local_sandbox", "binance_utc_rollover", "risk_check", 1),
    "ibkr_equity.contract_resolution": (
        "ibkr_paper",
        "equity_contract_resolution",
        "connection",
        1,
    ),
    "ibkr_equity.market_data_permission": (
        "ibkr_paper",
        "equity_market_data_permission",
        "connection",
        1,
    ),
    "ibkr_equity.acknowledged_cancellation": ("ibkr_paper", "equity_cancellation", "cancel", 1),
    "ibkr_equity.entry_exit_cycle": ("ibkr_paper", "equity_entry_exit", "fill", 2),
    "ibkr_equity.overnight_gateway_restart": (
        "ibkr_paper",
        "equity_overnight_restart",
        "reconciliation",
        1,
    ),
    "ibkr_equity.zero_duplicate_orders": ("ibkr_paper", "equity_zero_duplicates", "risk_check", 1),
    "ibkr_equity.zero_unexplained_positions": (
        "ibkr_paper",
        "equity_zero_unexplained_positions",
        "risk_check",
        1,
    ),
    "ibkr_equity.zero_unresolved_fills": (
        "ibkr_paper",
        "equity_zero_unresolved_fills",
        "risk_check",
        1,
    ),
    "ibkr_equity.zero_live_port_attempts": (
        "ibkr_paper",
        "equity_zero_live_port_attempts",
        "risk_check",
        1,
    ),
    "ibkr_equity.zero_secret_leakage": (
        "ibkr_paper",
        "equity_zero_secret_leakage",
        "risk_check",
        1,
    ),
    "ibkr_future.contract_resolution": (
        "ibkr_paper",
        "future_contract_resolution",
        "connection",
        1,
    ),
    "ibkr_future.market_data_permission": (
        "ibkr_paper",
        "future_market_data_permission",
        "connection",
        1,
    ),
    "ibkr_future.acknowledged_cancellation": ("ibkr_paper", "future_cancellation", "cancel", 1),
    "ibkr_future.entry_exit_cycle": ("ibkr_paper", "future_entry_exit", "fill", 2),
    "ibkr_future.overnight_gateway_restart": (
        "ibkr_paper",
        "future_overnight_restart",
        "reconciliation",
        1,
    ),
    "ibkr_future.zero_duplicate_orders": ("ibkr_paper", "future_zero_duplicates", "risk_check", 1),
    "ibkr_future.zero_unexplained_positions": (
        "ibkr_paper",
        "future_zero_unexplained_positions",
        "risk_check",
        1,
    ),
    "ibkr_future.zero_unresolved_fills": (
        "ibkr_paper",
        "future_zero_unresolved_fills",
        "risk_check",
        1,
    ),
    "ibkr_future.zero_live_port_attempts": (
        "ibkr_paper",
        "future_zero_live_port_attempts",
        "risk_check",
        1,
    ),
    "ibkr_future.zero_secret_leakage": (
        "ibkr_paper",
        "future_zero_secret_leakage",
        "risk_check",
        1,
    ),
}


def required_scenarios() -> dict[str, tuple[str, str, str, int]]:
    """Return a copy of the fixed acceptance contract for test/evidence harnesses."""
    return dict(_REQUIREMENTS)


def readiness_report(data_dir: Path) -> dict[str, object]:
    """Evaluate every required scenario from durable journal evidence."""
    observed: dict[str, list[dict[str, object]]] = {}
    blockers: list[dict[str, object]] = []
    sessions = paper_store.list_sessions(data_dir)
    for session in sessions:
        session_id = str(session["session_id"])
        mode = str(session["execution_mode"])
        for event in paper_store.read_events(data_dir, session_id):
            payload = event["payload"]
            if not isinstance(payload, dict):
                continue
            scenario = payload.get("scenario")
            if isinstance(scenario, str) and payload.get("passed") is True:
                observed.setdefault(scenario, []).append(
                    {
                        "session_id": session_id,
                        "sequence": event["sequence"],
                        "event_type": event["event_type"],
                        "execution_mode": mode,
                    }
                )
            if event["event_type"] in {"reconciliation_warning", "rejection"} or (
                event["event_type"] == "risk_check" and payload.get("passed") is False
            ):
                blockers.append(
                    {
                        "session_id": session_id,
                        "sequence": event["sequence"],
                        "event_type": event["event_type"],
                    }
                )

    requirements: list[dict[str, object]] = []
    for requirement, (mode, scenario, event_type, minimum_count) in _REQUIREMENTS.items():
        evidence = [
            item
            for item in observed.get(scenario, [])
            if item["execution_mode"] == mode and item["event_type"] == event_type
        ]
        requirements.append(
            {
                "id": requirement,
                "passed": len(evidence) >= minimum_count,
                "evidence": evidence,
            }
        )
    passed = all(bool(requirement["passed"]) for requirement in requirements) and not blockers
    return {
        "schema_version": 1,
        "status": "passed" if passed else "pending",
        "paper_passed": passed,
        "requirements": requirements,
        "blocking_events": blockers,
        "futures_research_supported": False,
        "live_capital_routing": "absent",
        "derived_from_elapsed_time": False,
    }


__all__ = ["readiness_report", "required_scenarios"]
