"""Options & derivatives analytics — Black-Scholes pricing, greeks, implied volatility.

Pure, fail-loud numeric primitives (numpy/scipy) that import nothing internal but ``alpha_core``
(for the typed error). The CLI (``alpha options ...``) exposes these as ``--json`` projections the
workstation renders; no look-ahead surface (these are point-in-time calculators, not backtests).
"""

from __future__ import annotations

from importlib.metadata import version

from alpha_options.black_scholes import Greeks, bs_greeks, bs_price, implied_vol

__version__ = version("alpha-options")
__all__ = ["Greeks", "bs_greeks", "bs_price", "implied_vol"]
