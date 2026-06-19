"""Frame-level schema firewall for stored bars — fail loud on malformed frames.

The point-in-time reader's positional/temporal reads (``pit.py``) assume bars are ts-sorted,
unique, finite, OHLC-consistent and strictly-positively priced. That assumption used to live in a
*comment*; this module turns it into a mechanically-enforced contract.

Pandera declares the **structural** part of the contract (exactly these columns, with float/datetime
dtypes); the **value/ordering** invariants are asserted directly in polars where they read most
clearly. Every failure — pandera's or ours — is re-raised as a typed :class:`alpha_core.DataError`,
honouring the no-bare-exception / fail-loud rule.

This is deliberately *not* wired into :class:`alpha_data.store.ParquetStore`, which is a raw,
unadjusted layer that tolerates imperfect vendor data; the firewall belongs at the PIT boundary
that downstream code actually reads through.
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl
from pandera.errors import SchemaError, SchemaErrors

from alpha_core import DataError

_PRICE_COLS = ("open", "high", "low", "close")

# Structural contract: exactly the bar columns with float price/volume dtypes. ``ts`` is left
# dtype-free here (pandera pins an exact time unit/timezone, which would reject tz-aware UTC bars)
# and checked as a temporal type in polars below. Value bounds are checked in polars too.
_BAR_SCHEMA = pa.DataFrameSchema(
    {
        "ts": pa.Column(nullable=False),
        "open": pa.Column(pl.Float64, nullable=False),
        "high": pa.Column(pl.Float64, nullable=False),
        "low": pa.Column(pl.Float64, nullable=False),
        "close": pa.Column(pl.Float64, nullable=False),
        "volume": pa.Column(pl.Float64, nullable=False),
    },
    strict=True,  # reject unexpected columns
    ordered=False,
)


def validate_bars(df: pl.DataFrame, *, symbol: str) -> pl.DataFrame:
    """Return ``df`` unchanged iff it is a well-formed bar frame, else raise ``DataError``.

    Enforced: the structural schema (columns + dtypes), non-empty, all prices finite and strictly
    positive, ``high >= low``, ``volume`` finite and non-negative, and ``ts`` strictly increasing
    (sorted ascending with no duplicates).
    """
    try:
        _BAR_SCHEMA.validate(df, lazy=True)
    except (SchemaError, SchemaErrors) as exc:
        raise DataError(f"bars for {symbol!r} failed schema validation: {exc}") from exc

    if df.height == 0:
        raise DataError(f"bars for {symbol!r} are empty")

    checks = df.select(
        prices_finite=pl.all_horizontal(pl.col(c).is_finite() for c in _PRICE_COLS).all(),
        prices_positive=pl.all_horizontal(pl.col(c) > 0.0 for c in _PRICE_COLS).all(),
        high_ge_low=(pl.col("high") >= pl.col("low")).all(),
        volume_ok=((pl.col("volume") >= 0.0) & pl.col("volume").is_finite()).all(),
    ).row(0, named=True)

    if not checks["prices_finite"]:
        raise DataError(f"bars for {symbol!r} contain non-finite prices (NaN/inf)")
    if not checks["prices_positive"]:
        raise DataError(f"bars for {symbol!r} contain non-positive prices")
    if not checks["high_ge_low"]:
        raise DataError(f"bars for {symbol!r} violate high >= low")
    if not checks["volume_ok"]:
        raise DataError(f"bars for {symbol!r} contain negative or non-finite volume")

    ts = df.get_column("ts")
    if not isinstance(ts.dtype, pl.Datetime):
        raise DataError(f"bars for {symbol!r} have non-datetime ts column ({ts.dtype})")
    if not ts.is_sorted():
        raise DataError(f"bars for {symbol!r} are not ts-sorted ascending")
    if ts.n_unique() != df.height:
        raise DataError(f"bars for {symbol!r} contain duplicate timestamps")

    return df
