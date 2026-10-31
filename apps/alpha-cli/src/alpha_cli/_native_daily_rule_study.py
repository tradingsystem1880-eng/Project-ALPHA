"""Inert Packet 3 study identity. Validation grants no launch or owner authority.

The query is CryptoSnapshotV1 lineage, never a canonical Parquet snapshot. The
proposed sizing and economic terms must be owner-frozen before numerical effects.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from alpha_cli.crypto_price_snapshot_query import (
    BinanceDailyPriceSnapshotQueryV1,
    validate_binance_daily_price_identity,
)
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoRawReceiptV1
from alpha_strategies.rules import canonical_json, rule_spec_from_json


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class _Frozen(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, allow_inf_nan=False, populate_by_name=True
    )

    @model_validator(mode="before")
    @classmethod
    def literal_types(cls, value: object) -> object:
        # Pydantic's Literal[1] accepts True even in strict mode. Counts are not flags.
        if isinstance(value, dict):
            for name, field in cls.model_fields.items():
                if name in value and get_origin(field.annotation) is Literal:
                    choices = get_args(field.annotation)
                    if not any(type(value[name]) is type(choice) for choice in choices):
                        raise ValueError(f"{name} has the wrong literal type")
        return value


class DailyRuleEconomicsV1(_Frozen):
    """Explicit proposed research economics, not defaults for any other study."""

    starting_cash: float = Field(gt=0, le=1_000_000)
    currency: Literal["USDT"]
    account_type: Literal["CASH"]
    fixed_quantity_btc: float = Field(gt=0, le=1)
    sizing: Literal["fixed_units_long_flat_no_rebalance_while_long"]
    control_sizing: Literal["same_fixed_units_buy_once_then_hold"]
    control_entry_policy: Literal["first_eligible_attempt_only"]
    fee_bps_per_side: float = Field(ge=0, le=100)
    spread_bps_full: float = Field(ge=0, le=100)
    slippage_bps_per_side: float = Field(ge=0, le=100)
    price_precision: Literal[2]
    quantity_precision: Literal[6]
    quantity_increment_btc: float = Field(ge=0.000001, le=0.000001)
    fill_timing: Literal["utc_day_end_next_open_plus_1us"]
    gap_policy: Literal["reject_unaffordable_buy_no_resize"]
    terminal_liquidation: Literal[False]
    terminal_valuation: Literal["last_admitted_open_quote"]
    terminal_decision: Literal["unfilled_without_next_admitted_quote"]
    allow_short: Literal[False]
    leverage: Literal[1]

    @model_validator(mode="after")
    def exact_units(self) -> DailyRuleEconomicsV1:
        if Decimal(str(self.fixed_quantity_btc)) % Decimal(str(self.quantity_increment_btc)):
            raise ValueError("daily study quantity must align exactly with its venue increment")
        return self

    @property
    def half_spread_and_slippage_bps(self) -> float:
        return self.spread_bps_full / 2 + self.slippage_bps_per_side


class DailyRuleResourcesV1(_Frozen):
    """Bounded proposal; the existing reservation ledger remains authoritative."""

    trials: Literal[1]
    baseline_control_exposures: Literal[2]
    d0_exposures: Literal[3]
    repairs: Literal[0]
    model_calls: Literal[0]
    tool_calls: Literal[0]
    max_http_attempts: int = Field(ge=2, le=8)
    max_response_bytes: int = Field(ge=1, le=8 * 1024 * 1024)
    max_rows: Literal[1096]
    max_wall_seconds: int = Field(ge=1, le=60)
    max_cpus: Literal[1]
    max_memory_bytes: int = Field(ge=256 * 1024 * 1024, le=2 * 1024 * 1024 * 1024)
    max_artifact_bytes: int = Field(ge=1, le=32 * 1024 * 1024)


class DailyRuleStudyV1(_Frozen):
    """A content-bound complete request, requiring independent authority admission.

    No empty/partial query, mutable mapping, provider substitution, extra history,
    tuning variant or unsupported scientific acceptance can enter this identity.
    """

    schema_name: Literal["FrozenDailyRuleStudyV1"] = Field(alias="schema")
    capability: Literal["binance_btcusdt_daily_momentum20_control_v1"]
    provider: Literal["binance"]
    venue: Literal["binance"]
    market: Literal["spot"]
    symbol: Literal["BTC/USDT"]
    data_origin: Literal["artificial_fixture", "captured_provider_history"]
    discovery_start: Literal["2020-01-01T00:00:00+00:00"]
    discovery_end_exclusive: Literal["2023-01-01T00:00:00+00:00"]
    warmup_bars: Literal[20]
    first_decision_bar: Literal["2020-01-21T00:00:00+00:00"]
    signal: Literal["long_if_close_t_gt_close_t_minus_20_else_flat"]
    control: Literal["buy_same_units_at_first_eligible_next_open_then_hold"]
    rules_spec: str
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_document: str = Field(max_length=2 * 1024 * 1024)
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    container_image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    storage_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    economics: DailyRuleEconomicsV1
    resources: DailyRuleResourcesV1
    claim_scope: Literal["exploratory_reconstructed_discovery_history"]
    point_in_time_claim: Literal[False]
    scientific_acceptance: Literal["not_admitted"]
    authority: Literal["none"]

    @model_validator(mode="after")
    def exact_bindings(self) -> DailyRuleStudyV1:
        if self.rules_spec != momentum20_rule():
            raise ValueError("daily study requires its exact canonical momentum20 RuleSpec")
        try:
            query = json.loads(self.query_document)
        except (ValueError, TypeError) as error:
            raise ValueError("daily study requires a canonical price query document") from error
        if (
            _canonical(query) != self.query_document
            or hashlib.sha256(self.query_document.encode()).hexdigest() != self.query_sha256
            or not isinstance(query, dict)
            or query.get("schema") != "BinanceDailyPriceSnapshotQueryV1"
            or query.get("start") != self.discovery_start
            or query.get("end_exclusive") != self.discovery_end_exclusive
            or query.get("available_by") != self.discovery_end_exclusive
            or query.get("requested_row_count") != 1096
            or query.get("returned_row_count") != 1096
            or query.get("coverage") != "complete_requested_utc_days"
            or query.get("point_in_time_claim") is not False
            or query.get("execution_authority") is not False
            or query.get("snapshot_id") != self.snapshot_sha256
        ):
            raise ValueError("daily study query identity/coverage/claim differs")
        rows = query.get("rows")
        if not isinstance(rows, list) or len(rows) != 1096:
            raise ValueError("daily study requires every frozen discovery row")
        try:
            dataset = CryptoDatasetIdentityV1.from_dict(query.get("dataset"))
            validate_binance_daily_price_identity(dataset)
            if query.get("dataset_sha256") != dataset.content_sha256:
                raise DataError("daily study query dataset hash differs")
            sources = query.get("source_receipts")
            if not isinstance(sources, list) or not 1 <= len(sources) <= 100:
                raise DataError("daily study query requires bounded source receipts")
            receipts = tuple(CryptoRawReceiptV1.from_dict(source) for source in sources)
            if any(
                receipt.dataset != dataset
                or receipt.provider_schema != "binance-public-rest-v1"
                or receipt.parser_version != "binance-archive-rest-v1"
                for receipt in receipts
            ):
                raise DataError("daily study query source identity differs")
        except DataError as error:
            raise ValueError("daily study query source/dataset identity differs") from error
        start = datetime(2020, 1, 1, tzinfo=UTC)
        for index, row in enumerate(rows):
            opened = start + timedelta(days=index)
            if (
                not isinstance(row, dict)
                or row.get("open_time") != opened.isoformat()
                or row.get("available_at") != (opened + timedelta(days=1)).isoformat()
            ):
                raise ValueError("daily study frozen query row chronology differs")
        return self

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json", by_alias=True)

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict()).encode()).hexdigest()


def momentum20_rule() -> str:
    """Positive twenty-day close return; equality and negative returns are flat."""
    return canonical_json(
        rule_spec_from_json(
            _canonical(
                {
                    "version": 1,
                    "name": "btc-discovery-momentum20-frozen",
                    "history": 21,
                    "long_when": [
                        {
                            "left": {"source": "close"},
                            "op": ">",
                            "right": {"source": "close", "lag": 20},
                        }
                    ],
                    "short_when": [],
                }
            )
        )
    )


def daily_rule_terms_proposal() -> tuple[DailyRuleEconomicsV1, DailyRuleResourcesV1]:
    """Reviewable proposal only; never infer approval from calling this function."""
    return (
        DailyRuleEconomicsV1(
            starting_cash=10_000.0,
            currency="USDT",
            account_type="CASH",
            fixed_quantity_btc=0.05,
            sizing="fixed_units_long_flat_no_rebalance_while_long",
            control_sizing="same_fixed_units_buy_once_then_hold",
            control_entry_policy="first_eligible_attempt_only",
            fee_bps_per_side=10.0,
            spread_bps_full=2.0,
            slippage_bps_per_side=5.0,
            price_precision=2,
            quantity_precision=6,
            quantity_increment_btc=0.000001,
            fill_timing="utc_day_end_next_open_plus_1us",
            gap_policy="reject_unaffordable_buy_no_resize",
            terminal_liquidation=False,
            terminal_valuation="last_admitted_open_quote",
            terminal_decision="unfilled_without_next_admitted_quote",
            allow_short=False,
            leverage=1,
        ),
        DailyRuleResourcesV1(
            trials=1,
            baseline_control_exposures=2,
            d0_exposures=3,
            repairs=0,
            model_calls=0,
            tool_calls=0,
            max_http_attempts=4,
            max_response_bytes=1024 * 1024,
            max_rows=1096,
            max_wall_seconds=60,
            max_cpus=1,
            max_memory_bytes=1024 * 1024 * 1024,
            max_artifact_bytes=32 * 1024 * 1024,
        ),
    )


def bind_daily_study(
    query: BinanceDailyPriceSnapshotQueryV1,
    *,
    snapshot_sha256: str,
    runtime_profile_sha256: str,
    container_image_id: str,
    storage_config_sha256: str,
    economics: DailyRuleEconomicsV1,
    resources: DailyRuleResourcesV1,
    data_origin: Literal["artificial_fixture", "captured_provider_history"],
) -> DailyRuleStudyV1:
    """Freeze a verified query read; this does not approve, reserve, spawn or execute.

    Admission must reopen the exact query before effects; a caller-created object
    or a content hash is not proof of qualified source or consumed owner approval.
    """
    if type(query) is not BinanceDailyPriceSnapshotQueryV1:
        raise DataError("daily study requires its typed frozen price query")
    if (
        query.start != datetime(2020, 1, 1, tzinfo=UTC)
        or query.end != datetime(2023, 1, 1, tzinfo=UTC)
        or query.available_by != query.end
    ):
        raise DataError("daily study query must match the approved 2020–2022 discovery scope")
    try:
        return DailyRuleStudyV1(
            schema_name="FrozenDailyRuleStudyV1",
            capability="binance_btcusdt_daily_momentum20_control_v1",
            provider="binance",
            venue="binance",
            market="spot",
            symbol="BTC/USDT",
            data_origin=data_origin,
            discovery_start="2020-01-01T00:00:00+00:00",
            discovery_end_exclusive="2023-01-01T00:00:00+00:00",
            warmup_bars=20,
            first_decision_bar="2020-01-21T00:00:00+00:00",
            signal="long_if_close_t_gt_close_t_minus_20_else_flat",
            control="buy_same_units_at_first_eligible_next_open_then_hold",
            rules_spec=momentum20_rule(),
            snapshot_sha256=snapshot_sha256,
            query_document=_canonical(query.to_dict()),
            query_sha256=query.content_sha256,
            runtime_profile_sha256=runtime_profile_sha256,
            container_image_id=container_image_id,
            storage_config_sha256=storage_config_sha256,
            economics=economics,
            resources=resources,
            claim_scope="exploratory_reconstructed_discovery_history",
            point_in_time_claim=False,
            scientific_acceptance="not_admitted",
            authority="none",
        )
    except ValidationError as error:
        raise DataError("daily study binding is invalid") from error
