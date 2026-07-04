"""Pure signal rule over end-of-horizon close quantiles ({-1, 0, 1}, trailing-window only)."""

from __future__ import annotations

import math

from alpha_core import DataError


def kronos_signal(
    origin_close: float,
    q25_end: float,
    q50_end: float,
    q75_end: float,
    *,
    min_edge: float = 0.0,
    require_band_agreement: bool = False,
) -> int:
    """Direction of the forecast median end-close vs the origin close.

    ``min_edge`` is a dead-band on the median horizon return (|q50/origin - 1| must clear
    it). With ``require_band_agreement``, a long additionally needs the 25th-percentile end
    above the origin (and a short needs the 75th below) — the inner band must agree, not
    just the median.
    """
    if not math.isfinite(origin_close) or origin_close <= 0.0:
        raise DataError(f"origin_close must be finite and > 0, got {origin_close!r}")
    for name, v in (("q25_end", q25_end), ("q50_end", q50_end), ("q75_end", q75_end)):
        if not math.isfinite(v):
            raise DataError(f"{name} must be finite, got {v!r}")
    if min_edge < 0.0:
        raise DataError(f"min_edge must be >= 0, got {min_edge}")

    median_return = q50_end / origin_close - 1.0
    if abs(median_return) <= min_edge:
        return 0
    if median_return > 0.0:
        if require_band_agreement and q25_end <= origin_close:
            return 0
        return 1
    if require_band_agreement and q75_end >= origin_close:
        return 0
    return -1
