"""Typed specification of one paper-trading session.

``PaperSpec`` mirrors the pre-registered strategy/cost parameters of the backtest ``RunSpec`` (so a
paper session and a backtest are configured identically — the basis of parity) plus the paper-only
fields (symbol/exchange/venue, optional run duration). It carries no walk-forward geometry; that is
a validation-only concern. ``account_type`` is a plain string (``"CASH"``/``"MARGIN"``) so the spec
stays nautilus-free and trivially serializable into the session manifest.
"""

from __future__ import annotations

from dataclasses import dataclass

from alpha_core.config import AlphaSettings


@dataclass(frozen=True)
class PaperSpec:
    """The full specification of one paper-trading session.

    Defaults follow the v1 crypto convention: long-short on a MARGIN account, a 365-day year (crypto
    trades every calendar day), and the literature-backed time-series-momentum parameters.
    """

    symbol: str
    exchange: str
    venue: str
    lookback: int = 252
    skip: int = 21
    vol_window: int = 63
    target_vol: float = 0.15
    rebalance_every: int = 21
    max_leverage: float = 1.0
    allow_short: bool = True
    periods_per_year: int = 365
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    starting_cash: float = 1_000_000.0
    account_type: str = "MARGIN"
    duration_seconds: float | None = None  # None = run until stopped (Ctrl-C / kill-switch)

    @property
    def min_train(self) -> int:
        """Warmup floor: bars of history needed before the first signal + vol estimate are valid.

        Identical to ``RunSpec.min_train`` — used to prime the live strategy with enough historical
        bars on startup so its first live decision matches the backtest's.
        """
        return max(self.lookback + self.skip + 1, self.vol_window + 1)


def paper_spec_from_settings(settings: AlphaSettings, **overrides: object) -> PaperSpec:
    """Build a ``PaperSpec`` from resolved ``AlphaSettings`` (symbol/exchange/venue), then apply
    any explicit ``overrides`` (e.g. strategy params from CLI flags). Secrets are never copied in.
    """
    base: dict[str, object] = {
        "symbol": settings.paper_symbol,
        "exchange": settings.paper_exchange,
        "venue": settings.paper_venue,
    }
    base.update(overrides)
    return PaperSpec(**base)  # type: ignore[arg-type]  # validated by the dataclass field types
