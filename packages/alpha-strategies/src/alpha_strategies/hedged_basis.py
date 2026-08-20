"""Pure sandbox model for the registered two-venue BTCUSDT basis candidate.

This module evaluates an already-materialized, point-in-time crowding event stream.  It does not
construct orders, connect to either venue, or reinterpret either leg as a universal crypto price.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Final, Literal

from alpha_core import DataError

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_INPUT_NAMES: Final = ("binance_spot", "bybit_linear")


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"hedged basis {label} must be timezone-aware")
    return value.astimezone(UTC)


def _finite_positive(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DataError(f"hedged basis {label} must be finite")
    result = float(value)
    if result <= 0.0:
        raise DataError(f"hedged basis {label} must be positive")
    return result


def _json_value(value: object) -> object:
    if isinstance(value, datetime):
        return _utc(value, "timestamp").isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _digest(value: object) -> str:
    encoded = json.dumps(
        _json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _parse_time(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise DataError(f"hedged basis {label} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError(f"hedged basis {label} must be an ISO timestamp") from exc
    return _utc(parsed, label)


@dataclass(frozen=True, slots=True)
class HedgedBasisPlanV1:
    strategy_name: str = "hedged_basis_crowding_v1"
    perp_venue: str = "bybit"
    spot_venue: str = "binance"
    instrument: str = "BTCUSDT"
    base_asset: str = "BTC"
    quote_asset: str = "USDT"
    perp_market_type: str = "linear_perpetual"
    spot_market_type: str = "spot"
    total_round_trip_cost_bps: float = 40.0
    annualization_days: int = 365
    funding_interval_hours: int = 8
    deployment_scope: Literal["sandbox_only"] = "sandbox_only"
    paper_blocker: str = "UNSUPPORTED_MULTI_VENUE_PAPER"
    places_orders: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        if (
            self.strategy_name != "hedged_basis_crowding_v1"
            or self.perp_venue != "bybit"
            or self.spot_venue != "binance"
            or self.instrument != "BTCUSDT"
            or self.base_asset != "BTC"
            or self.quote_asset != "USDT"
            or self.perp_market_type != "linear_perpetual"
            or self.spot_market_type != "spot"
            or self.total_round_trip_cost_bps != 40.0
            or self.annualization_days != 365
            or self.funding_interval_hours != 8
            or self.deployment_scope != "sandbox_only"
            or self.paper_blocker != "UNSUPPORTED_MULTI_VENUE_PAPER"
            or self.places_orders is not False
            or self.schema_version != 1
        ):
            raise DataError("hedged basis plan differs from the registered sandbox candidate")

    @property
    def periods_per_year(self) -> int:
        return self.annualization_days * 24 // self.funding_interval_hours

    @property
    def plan_fingerprint(self) -> str:
        return _digest(asdict(self))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@cache
def registered_hedged_basis_plan() -> HedgedBasisPlanV1:
    return HedgedBasisPlanV1()


@dataclass(frozen=True, slots=True)
class HedgedBasisObservationV1:
    observation_id: str
    event_time: datetime
    event_available_at: datetime
    entry_time: datetime
    entry_available_at: datetime
    exit_time: datetime
    exit_available_at: datetime
    bybit_perp_entry: float
    bybit_perp_exit: float
    binance_spot_entry: float
    binance_spot_exit: float
    funding_rate: float
    funding_available_at: datetime
    perp_quantity_btc: float
    spot_quantity_btc: float
    input_sha256: tuple[tuple[str, str], ...]
    event_operator_fingerprint: str
    correction_lineage: tuple[str, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        for field in (
            "event_time",
            "event_available_at",
            "entry_time",
            "entry_available_at",
            "exit_time",
            "exit_available_at",
            "funding_available_at",
        ):
            object.__setattr__(self, field, _utc(getattr(self, field), field))
        for field in (
            "bybit_perp_entry",
            "bybit_perp_exit",
            "binance_spot_entry",
            "binance_spot_exit",
        ):
            object.__setattr__(self, field, _finite_positive(getattr(self, field), field))
        if not math.isfinite(self.funding_rate):
            raise DataError("hedged basis funding rate must be finite")
        quantities = (self.perp_quantity_btc, self.spot_quantity_btc)
        if any(not math.isfinite(value) for value in quantities) or not (
            self.perp_quantity_btc < 0.0
            and self.spot_quantity_btc > 0.0
            and abs(self.perp_quantity_btc) == self.spot_quantity_btc
        ):
            raise DataError("hedged basis legs must be delta matched in BTC")
        if not (
            self.event_available_at <= self.event_time
            and self.funding_available_at <= self.event_time
            and self.event_time < self.entry_time < self.exit_time
            and self.entry_available_at <= self.entry_time
            and self.exit_available_at == self.exit_time
        ):
            raise DataError("hedged basis observation is not causal")
        if self.exit_time - self.event_time != timedelta(
            hours=registered_hedged_basis_plan().funding_interval_hours
        ):
            raise DataError("hedged basis exit is not the next registered funding boundary")
        if (
            tuple(name for name, _ in self.input_sha256) != _INPUT_NAMES
            or any(_SHA256.fullmatch(digest) is None for _, digest in self.input_sha256)
            or _SHA256.fullmatch(self.event_operator_fingerprint) is None
            or len(set(self.correction_lineage)) != len(self.correction_lineage)
            or tuple(sorted(self.correction_lineage)) != self.correction_lineage
            or any(not item.strip() for item in self.correction_lineage)
        ):
            raise DataError("hedged basis provider identity and lineage are invalid")
        if self.schema_version != 1 or self.observation_id != _digest(self.body()):
            raise DataError("hedged basis observation identity is invalid")

    def body(self) -> dict[str, object]:
        return {
            "event_time": self.event_time,
            "event_available_at": self.event_available_at,
            "entry_time": self.entry_time,
            "entry_available_at": self.entry_available_at,
            "exit_time": self.exit_time,
            "exit_available_at": self.exit_available_at,
            "bybit_perp_entry": self.bybit_perp_entry,
            "bybit_perp_exit": self.bybit_perp_exit,
            "binance_spot_entry": self.binance_spot_entry,
            "binance_spot_exit": self.binance_spot_exit,
            "funding_rate": self.funding_rate,
            "funding_available_at": self.funding_available_at,
            "perp_quantity_btc": self.perp_quantity_btc,
            "spot_quantity_btc": self.spot_quantity_btc,
            "input_sha256": self.input_sha256,
            "event_operator_fingerprint": self.event_operator_fingerprint,
            "correction_lineage": self.correction_lineage,
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, object]:
        payload = _json_value({**self.body(), "observation_id": self.observation_id})
        if not isinstance(payload, dict):  # pragma: no cover - the input is an object literal.
            raise DataError("hedged basis observation serialization failed")
        return payload

    @classmethod
    def create(cls, **values: object) -> HedgedBasisObservationV1:
        body = {**values, "schema_version": 1}
        return cls(observation_id=_digest(body), **body)  # type: ignore[arg-type]

    @classmethod
    def from_dict(cls, value: object) -> HedgedBasisObservationV1:
        required = {
            "observation_id",
            "event_time",
            "event_available_at",
            "entry_time",
            "entry_available_at",
            "exit_time",
            "exit_available_at",
            "bybit_perp_entry",
            "bybit_perp_exit",
            "binance_spot_entry",
            "binance_spot_exit",
            "funding_rate",
            "funding_available_at",
            "perp_quantity_btc",
            "spot_quantity_btc",
            "input_sha256",
            "event_operator_fingerprint",
            "correction_lineage",
            "schema_version",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise DataError("hedged basis observation payload is malformed")
        inputs = value.get("input_sha256")
        lineage = value.get("correction_lineage")
        if (
            not isinstance(inputs, list)
            or any(
                not isinstance(item, list)
                or len(item) != 2
                or any(not isinstance(part, str) for part in item)
                for item in inputs
            )
            or not isinstance(lineage, list)
            or any(not isinstance(item, str) for item in lineage)
        ):
            raise DataError("hedged basis observation payload is malformed")
        try:
            return cls(
                observation_id=str(value["observation_id"]),
                event_time=_parse_time(value["event_time"], "event_time"),
                event_available_at=_parse_time(value["event_available_at"], "event_available_at"),
                entry_time=_parse_time(value["entry_time"], "entry_time"),
                entry_available_at=_parse_time(value["entry_available_at"], "entry_available_at"),
                exit_time=_parse_time(value["exit_time"], "exit_time"),
                exit_available_at=_parse_time(value["exit_available_at"], "exit_available_at"),
                bybit_perp_entry=float(value["bybit_perp_entry"]),
                bybit_perp_exit=float(value["bybit_perp_exit"]),
                binance_spot_entry=float(value["binance_spot_entry"]),
                binance_spot_exit=float(value["binance_spot_exit"]),
                funding_rate=float(value["funding_rate"]),
                funding_available_at=_parse_time(
                    value["funding_available_at"], "funding_available_at"
                ),
                perp_quantity_btc=float(value["perp_quantity_btc"]),
                spot_quantity_btc=float(value["spot_quantity_btc"]),
                input_sha256=tuple((str(item[0]), str(item[1])) for item in inputs),
                event_operator_fingerprint=str(value["event_operator_fingerprint"]),
                correction_lineage=tuple(lineage),
                schema_version=int(value["schema_version"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError("hedged basis observation payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class HedgedBasisTradeV1:
    observation_id: str
    entry_time: datetime
    exit_time: datetime
    available_at: datetime
    bybit_perp_short_return: float
    binance_spot_long_return: float
    funding_return: float
    cost_return: float
    net_return: float


@dataclass(frozen=True, slots=True)
class HedgedBasisEvaluationV1:
    status: Literal["EVALUATED"]
    trades: tuple[HedgedBasisTradeV1, ...]
    input_sha256: tuple[tuple[str, str], ...]
    event_operator_fingerprint: str
    plan_fingerprint: str
    total_round_trip_cost_bps: float
    periods_per_year: int
    cumulative_return: float
    deployment_scope: Literal["sandbox_only"] = "sandbox_only"
    places_orders: bool = False
    schema_version: int = 1


def evaluate_hedged_basis(
    observations: tuple[HedgedBasisObservationV1, ...],
) -> HedgedBasisEvaluationV1:
    """Evaluate the exact two-leg cash flows on spot-notional capital, net of frozen costs."""
    if not observations:
        raise DataError("hedged basis evaluation requires at least one admitted event")
    first = observations[0]
    previous_exit: datetime | None = None
    trades: list[HedgedBasisTradeV1] = []
    plan = registered_hedged_basis_plan()
    cost = plan.total_round_trip_cost_bps / 10_000.0
    cumulative = 1.0
    for observation in observations:
        if previous_exit is not None and observation.event_time < previous_exit:
            raise DataError("hedged basis events must be strictly ordered and non-overlapping")
        if (
            observation.input_sha256 != first.input_sha256
            or observation.event_operator_fingerprint != first.event_operator_fingerprint
        ):
            raise DataError("hedged basis events must share the same frozen input lineage")
        perp = (observation.bybit_perp_entry - observation.bybit_perp_exit) / (
            observation.bybit_perp_entry
        )
        spot = observation.binance_spot_exit / observation.binance_spot_entry - 1.0
        net = perp + spot + observation.funding_rate - cost
        if not math.isfinite(net) or net <= -1.0:
            raise DataError("hedged basis event produced an invalid net return")
        trades.append(
            HedgedBasisTradeV1(
                observation_id=observation.observation_id,
                entry_time=observation.entry_time,
                exit_time=observation.exit_time,
                available_at=observation.exit_available_at,
                bybit_perp_short_return=perp,
                binance_spot_long_return=spot,
                funding_return=observation.funding_rate,
                cost_return=-cost,
                net_return=net,
            )
        )
        cumulative *= 1.0 + net
        previous_exit = observation.exit_time
    return HedgedBasisEvaluationV1(
        status="EVALUATED",
        trades=tuple(trades),
        input_sha256=first.input_sha256,
        event_operator_fingerprint=first.event_operator_fingerprint,
        plan_fingerprint=plan.plan_fingerprint,
        total_round_trip_cost_bps=plan.total_round_trip_cost_bps,
        periods_per_year=plan.periods_per_year,
        cumulative_return=cumulative - 1.0,
    )


__all__ = [
    "HedgedBasisEvaluationV1",
    "HedgedBasisObservationV1",
    "HedgedBasisPlanV1",
    "HedgedBasisTradeV1",
    "evaluate_hedged_basis",
    "registered_hedged_basis_plan",
]
