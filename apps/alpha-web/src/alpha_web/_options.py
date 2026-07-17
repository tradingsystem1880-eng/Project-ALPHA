"""Subprocess the CLI's Black-Scholes analytics (``alpha options ... --json``).

Pure calculators — no store access — so nothing is cached; the CLI stays the single source of the
pricing math the panel renders.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json


def greeks(
    *, data_dir: Path, spot: float, strike: float, vol: float, days: float, rate: float, kind: str
) -> dict[str, Any]:
    """Price + greeks for one European option."""
    args = [
        "options", "greeks", str(spot), str(strike),
        "--vol", str(vol), "--days", str(days), "--rate", str(rate), "--kind", kind, "--json",
    ]  # fmt: skip
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    return result


def iv(
    *, data_dir: Path, spot: float, strike: float, price: float, days: float, rate: float, kind: str
) -> dict[str, Any]:
    """Implied vol (+ greeks at that vol) from an observed option price."""
    args = [
        "options", "iv", str(spot), str(strike),
        "--price", str(price), "--days", str(days), "--rate", str(rate), "--kind", kind, "--json",
    ]  # fmt: skip
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    return result


def curve(
    *,
    data_dir: Path,
    strike: float,
    vol: float,
    days: float,
    rate: float,
    kind: str,
    width: float,
    points: int,
) -> dict[str, Any]:
    """Price + greeks across a range of spot prices (for the greeks-vs-spot chart)."""
    args = [
        "options", "curve", str(strike),
        "--vol", str(vol), "--days", str(days), "--rate", str(rate), "--kind", kind,
        "--width", str(width), "--points", str(points), "--json",
    ]  # fmt: skip
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    return result
