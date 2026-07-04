"""``kronos_signal``: {-1, 0, 1} from end-of-horizon close quantiles (pure, table-driven)."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_forecast import kronos_signal


@pytest.mark.parametrize(
    ("q25", "q50", "q75", "min_edge", "band", "expected"),
    [
        # plain median direction
        (99.0, 103.0, 108.0, 0.0, False, 1),
        (92.0, 97.0, 101.0, 0.0, False, -1),
        (99.0, 100.0, 101.0, 0.0, False, 0),
        # dead-band on |median return|
        (99.0, 101.0, 108.0, 0.02, False, 0),  # +1% < 2% edge
        (99.0, 103.0, 108.0, 0.02, False, 1),  # +3% clears it
        (92.0, 97.0, 101.0, 0.02, False, -1),  # -3% clears it
        (98.0, 99.0, 101.0, 0.02, False, 0),  # -1% inside the band
        # band agreement: q25 must confirm longs, q75 must confirm shorts
        (99.0, 103.0, 108.0, 0.0, True, 0),  # long unconfirmed: q25 < origin
        (101.0, 103.0, 108.0, 0.0, True, 1),  # long confirmed
        (92.0, 97.0, 101.0, 0.0, True, 0),  # short unconfirmed: q75 > origin
        (92.0, 97.0, 99.5, 0.0, True, -1),  # short confirmed
    ],
)
def test_signal_table(
    q25: float, q50: float, q75: float, min_edge: float, band: bool, expected: int
) -> None:
    got = kronos_signal(
        100.0, q25, q50, q75, min_edge=min_edge, require_band_agreement=band
    )
    assert got == expected


def test_rejects_nonpositive_origin_and_nonfinite() -> None:
    with pytest.raises(DataError, match="origin_close"):
        kronos_signal(0.0, 1.0, 1.0, 1.0)
    with pytest.raises(DataError, match="finite"):
        kronos_signal(100.0, 99.0, float("nan"), 101.0)
    with pytest.raises(DataError, match="min_edge"):
        kronos_signal(100.0, 99.0, 100.0, 101.0, min_edge=-0.01)
