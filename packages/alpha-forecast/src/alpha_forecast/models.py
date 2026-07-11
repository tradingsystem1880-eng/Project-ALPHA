"""Kronos model registry + pure timestamp/leakage helpers. No torch imports here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from alpha_core import DataError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from alpha_core import Bar


@dataclass(frozen=True)
class ModelSpec:
    """One published Kronos checkpoint and the tokenizer it pairs with."""

    name: str
    model_repo: str
    tokenizer_repo: str
    params_m: float  # millions of parameters, for display + cost warnings
    max_context: int
    # Pinned HF commit shas (repo-specific: a model pin can never be reused for its
    # tokenizer repo). Pinned from the HF main branches on 2026-07-11; the base pair was
    # additionally verified on disk by the first networked `alpha forecast pull`.
    revision: str | None = None
    tokenizer_revision: str | None = None


_TOKENIZER_2K_REV = "26966d0035065a0cae0ebad7af8ece35bc1fb51c"
_TOKENIZER_BASE_REV = "0e0117387f39004a9016484a186a908917e22426"

MODEL_SPECS: dict[str, ModelSpec] = {
    "mini": ModelSpec(
        name="mini",
        model_repo="NeoQuasar/Kronos-mini",
        tokenizer_repo="NeoQuasar/Kronos-Tokenizer-2k",
        params_m=4.1,
        max_context=2048,
        revision="f4e68697d9d5aed55cef5c96aabc3376bcad9f81",
        tokenizer_revision=_TOKENIZER_2K_REV,
    ),
    "small": ModelSpec(
        name="small",
        model_repo="NeoQuasar/Kronos-small",
        tokenizer_repo="NeoQuasar/Kronos-Tokenizer-base",
        params_m=24.7,
        max_context=512,
        revision="901c26c1332695a2a8f243eb2f37243a37bea320",
        tokenizer_revision=_TOKENIZER_BASE_REV,
    ),
    "base": ModelSpec(
        name="base",
        model_repo="NeoQuasar/Kronos-base",
        tokenizer_repo="NeoQuasar/Kronos-Tokenizer-base",
        params_m=102.3,
        max_context=512,
        revision="2b554741eca47781b64468546e77fef3e85130e6",
        tokenizer_revision=_TOKENIZER_BASE_REV,
    ),
}

# Kronos weights were released 2025-08 and trained on market data up to roughly then.
# Backtests over earlier windows carry weight-level look-ahead that accessor-level PIT
# guards cannot catch.
KRONOS_TRAINING_CUTOFF = date(2025, 8, 1)


def resolve_model(name: str) -> ModelSpec:
    """Look up a model size by name; fail loud listing the known names."""
    try:
        return MODEL_SPECS[name]
    except KeyError:
        raise DataError(f"unknown Kronos model {name!r}; known: {sorted(MODEL_SPECS)}") from None


def training_overlap_warning(first_ts: datetime, last_ts: datetime) -> str | None:
    """A loud, copy-ready warning when [first_ts, last_ts] overlaps the pre-cutoff window.

    Returns None only when the whole window is at/after the training cutoff.
    """
    if first_ts > last_ts:
        raise DataError(f"window is disordered: first_ts {first_ts} > last_ts {last_ts}")
    if first_ts.date() >= KRONOS_TRAINING_CUTOFF:
        return None
    return (
        "WARNING: Kronos pretrained weights were trained on market data up to "
        f"~{KRONOS_TRAINING_CUTOFF.isoformat()}. This window begins "
        f"{first_ts.date().isoformat()} - inside the training window. Results carry "
        "weight-level look-ahead that accessor-level PIT guards CANNOT catch; treat every "
        "gauntlet verdict on this window as an UPPER BOUND, not evidence of edge."
    )


def future_timestamps(bars: Sequence[Bar], horizon: int) -> list[datetime]:
    """Deterministic future session axis extending the bar series.

    Spacing is inferred from the last two bars. Exactly-one-day spacing (daily bars,
    stamped 00:00 UTC) steps weekdays only (Mon-Fri); any other spacing steps uniformly.
    """
    if horizon < 1:
        raise DataError(f"horizon must be >= 1, got {horizon}")
    if len(bars) < 2:
        raise DataError(f"need >= 2 bars to infer bar spacing, got {len(bars)}")
    spacing = bars[-1].ts - bars[-2].ts
    if spacing <= timedelta(0):
        raise DataError(f"bars are disordered: non-positive spacing {spacing}")
    out: list[datetime] = []
    current = bars[-1].ts
    if spacing == timedelta(days=1):
        while len(out) < horizon:
            current = current + timedelta(days=1)
            if current.weekday() < 5:
                out.append(current)
    else:
        for _ in range(horizon):
            current = current + spacing
            out.append(current)
    return out
