"""Cheap registered route classification; safe in lifecycle reads and database locks."""

from __future__ import annotations

from collections.abc import Mapping

NAME = "binance_btcusdt_daily_rule_control"
PLAN_SCHEMA = "FrozenDailyRulePlanV1"


def contract_is_daily(contract: Mapping[str, object]) -> bool:
    protocol = contract.get("protocol")
    operator = protocol.get("d0_operator") if isinstance(protocol, Mapping) else None
    return isinstance(operator, Mapping) and operator.get("name") == NAME
