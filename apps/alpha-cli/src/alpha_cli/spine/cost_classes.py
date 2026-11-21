"""One home for default trading costs and annualisation rules by asset class.

The numbers are owner-set working assumptions, not quotes from a venue. Each row names where its
number comes from. Nothing here is read by an identity: a rule test records the numbers it used.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from alpha_cli.spine.setup_costs import (
    CRYPTO_FEE_BPS,
    CRYPTO_PROVIDERS,
    CRYPTO_SLIPPAGE_BPS,
    SHORT_BORROW_BPS_PER_YEAR,
    SHORT_CARRY_BPS_PER_DAY,
)
from alpha_cli.spine.stores import ResolvedAsset
from alpha_data.store import ParquetStore
from alpha_data.timeframe import DAILY, store_dir

CLASS_DEFAULT = "class-default"  # the spec value: `costs = "class-default"`
CLASS_DEFAULT_LABEL = "class-default-costs"
ASSUMED_LABEL = "cost-class-assumed"
BORROW_LABEL = "borrow-at-class-rate"
STOCK_SESSIONS = 252
CRYPTO_DAYS = 365


@dataclass(frozen=True)
class CostRow:
    key: str
    name: str
    fee_bps: float  # per side
    slippage_bps: float  # per side
    borrow_bps_per_year: float | None  # None: a short has no borrow rate here
    borrow_reason: str
    periods_per_year: int  # daily bars
    periods_rule: str
    source: str


ROWS: dict[str, CostRow] = {
    row.key: row
    for row in (
        CostRow(
            "us_large_etf",
            "US large ETF",
            1.0,
            1.0,
            30.0,
            "",
            STOCK_SESSIONS,
            "252 trading sessions a year",
            "Fee 1 bp: the old flat default. Slippage 1 bp: about half the quoted spread of a "
            "large, liquid fund. Borrow 30 bp: a typical easy-to-borrow fund. Not verified.",
        ),
        CostRow(
            "us_stock",
            "US stock",
            2.0,
            5.0,
            float(SHORT_BORROW_BPS_PER_YEAR),
            "",
            STOCK_SESSIONS,
            "252 trading sessions a year",
            "Fee 2 bp: regulatory and exchange fees on a small order. Slippage 5 bp: the spread "
            "and impact of a small-cap or mid-cap name. Borrow: the setup lane's 50 bp. "
            "Not verified.",
        ),
        CostRow(
            "crypto_spot",
            "crypto spot (taker)",
            CRYPTO_FEE_BPS,
            CRYPTO_SLIPPAGE_BPS,
            None,
            "a spot position cannot be shorted; use a perpetual",
            CRYPTO_DAYS,
            "365 days a year",
            "The setup lane's crypto numbers: taker fee about 10 bp, slippage 5 bp. Not verified.",
        ),
        CostRow(
            "crypto_perpetual",
            "crypto perpetual",
            5.0,
            CRYPTO_SLIPPAGE_BPS,
            float(SHORT_CARRY_BPS_PER_DAY * 365),
            "",
            CRYPTO_DAYS,
            "365 days a year",
            "Taker fee 5 bp: a common perpetual schedule. Slippage: the spot figure. The yearly "
            "rate is the setup lane's 3 bp a day of funding times 365. Not verified.",
        ),
    )
}
# The most conservative row: the highest cost of one side. Used when the class is not known.
CONSERVATIVE = max(ROWS.values(), key=lambda row: row.fee_bps + row.slippage_bps)


def asset_class(resolved: ResolvedAsset) -> str | None:
    """The row key for a stored asset, or None when its record does not say.

    A stored dataset identity decides. Without one, a crypto provider or a slash pair is crypto
    spot; an equity provider alone does not tell a stock from an ETF, so it is not known.
    """
    path = ParquetStore(store_dir(resolved.data_dir, DAILY))._provenance_path(resolved.symbol)
    provenance: dict[str, Any] = {}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        provenance = loaded if isinstance(loaded, dict) else {}
    dataset = provenance.get("dataset")
    if isinstance(dataset, dict):
        kind, venue = dataset.get("asset_class"), dataset.get("venue")
        if kind == "crypto":
            return "crypto_spot"
        if venue == "US" and kind == "etf":
            return "us_large_etf"
        if venue == "US" and kind == "stock":
            return "us_stock"
        return None
    parts = set(resolved.source.lower().split(":"))
    if "/" in resolved.symbol or parts & CRYPTO_PROVIDERS:
        return "crypto_spot"
    return None


def class_row(key: str | None) -> tuple[CostRow, bool]:
    """The row for a class key and whether it was assumed (key unknown)."""
    return (ROWS[key], False) if key in ROWS else (CONSERVATIVE, True)


def _bp(value: float, unit: str) -> str:
    return f"{value:g} basis point{'' if value == 1 else 's'}{unit}"


def cost_line(fee_bps: float, slippage_bps: float, row: CostRow | None, assumed: bool) -> str:
    """The one plain line of costs used. `row` None: the spec stated its own costs."""
    base = f"Costs: {_bp(fee_bps, ' fee')} and {slippage_bps:g} slippage per side"
    if row is None:
        if (fee_bps, slippage_bps) == (1.0, 2.0):
            return f"{base}, the flat default, not chosen by asset class."
        return f"{base}, as the spec states."
    if assumed:
        return (
            f"{base}, the most cautious default, for {row.name}: "
            "the asset class is not recorded, so it is assumed."
        )
    return f"{base}, the default for a {row.name}."


def periods_line(periods_per_year: int, basis: str, rule: str | None = None) -> str:
    text = f"Annualised with {periods_per_year} periods a year ({basis})."
    return f"{text} Rule for this asset class: {rule}." if rule else text


def periods_rule_text(key: str | None) -> str:
    return class_row(key)[0].periods_rule


def borrow_row(key: str | None) -> tuple[CostRow, bool]:
    """The row whose borrow rate applies; an unknown class takes the highest rate."""
    if key in ROWS and ROWS[key].borrow_bps_per_year is not None:
        return ROWS[key], False
    if key in ROWS:
        return ROWS[key], False  # spot: no rate, and the reason says so
    rated = [row for row in ROWS.values() if row.borrow_bps_per_year is not None]
    return max(rated, key=lambda row: row.borrow_bps_per_year or 0.0), True


def borrow_fact(
    row: CostRow, start_equity: float, end_equity: float, shorts: list[tuple[float, float]]
) -> dict[str, Any]:
    """Result after a borrow charge on short trades; a missing rate or notional is a reason.

    `shorts` holds (entry notional, calendar days held) per short trade. The charge is a plain
    sum in account currency, taken from the stored end equity.
    """
    if row.borrow_bps_per_year is None:
        return {"result_after_borrow": None, "borrow_charge": None, "reason": row.borrow_reason}
    charge = math.fsum(
        notional * row.borrow_bps_per_year / 10_000.0 * days / 365.0 for notional, days in shorts
    )
    return {
        "result_after_borrow": (end_equity - charge) / start_equity - 1.0,
        "borrow_charge": charge,
        "reason": None,
    }
