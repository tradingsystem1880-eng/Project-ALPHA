"""Reconcile realized fills against the modeled friction assumptions.

In the sandbox a market order fills against the live quote, so realized slippage is observable: the
signed adverse move of the fill price away from a reference (the decision bar's open, the price a
backtest assumes it transacts at). Comparing realized vs modeled ``slippage_bps`` validates that the
backtest's friction model is calibrated to the sandbox matcher — and surfaces the known fee gap (the
sandbox hard-codes ``MakerTakerFeeModel`` rather than the backtest's ``BpsFeeModel``).

Pure functions only (no nautilus): callers pass plain floats extracted from filled orders.
"""

from __future__ import annotations

from dataclasses import dataclass

from alpha_paper.errors import PaperError


def realized_slippage_bps(side: str, fill_px: float, ref_px: float) -> float:
    """Signed adverse slippage in basis points (positive = worse than ``ref_px``).

    A BUY filling above the reference and a SELL filling below it are both costs (positive bps).
    """
    if ref_px <= 0.0:
        raise PaperError(f"reference price must be positive, got {ref_px}")
    direction = 1.0 if side.upper() == "BUY" else -1.0
    return direction * (fill_px - ref_px) / ref_px * 10_000.0


@dataclass(frozen=True)
class Reconciliation:
    """One fill reconciled: realized vs modeled slippage and their difference (all in bps)."""

    side: str
    fill_px: float
    ref_px: float
    realized_bps: float
    modeled_bps: float

    @property
    def delta_bps(self) -> float:
        """Realized minus modeled — near zero means the friction model matches the sandbox."""
        return self.realized_bps - self.modeled_bps


def reconcile(fills: list[tuple[str, float, float]], modeled_bps: float) -> list[Reconciliation]:
    """Reconcile ``(side, fill_px, ref_px)`` fills against the modeled ``slippage_bps``."""
    return [
        Reconciliation(
            side=side,
            fill_px=fill_px,
            ref_px=ref_px,
            realized_bps=realized_slippage_bps(side, fill_px, ref_px),
            modeled_bps=modeled_bps,
        )
        for side, fill_px, ref_px in fills
    ]
