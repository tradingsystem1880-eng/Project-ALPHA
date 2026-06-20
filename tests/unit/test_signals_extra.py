"""Unit tests for the added pure signals: MA crossover, z-score reversion, Donchian breakout."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_strategies.signals import (
    breakout_signal,
    ma_crossover_signal,
    zscore_reversion_signal,
)


class TestMaCrossover:
    def test_uptrend_is_long(self) -> None:
        closes = [float(i) for i in range(1, 11)]  # 1..10 rising
        assert ma_crossover_signal(closes, fast=2, slow=4) == 1

    def test_downtrend_is_short(self) -> None:
        closes = [float(i) for i in range(10, 0, -1)]  # 10..1 falling
        assert ma_crossover_signal(closes, fast=2, slow=4) == -1

    def test_insufficient_history_is_flat(self) -> None:
        assert ma_crossover_signal([1.0, 2.0, 3.0], fast=2, slow=4) == 0

    def test_bad_params_fail_loud(self) -> None:
        with pytest.raises(DataError):
            ma_crossover_signal([1.0] * 5, fast=0, slow=4)
        with pytest.raises(DataError):
            ma_crossover_signal([1.0] * 5, fast=4, slow=4)  # slow must exceed fast

    def test_non_positive_price_in_window_fails_loud(self) -> None:
        with pytest.raises(DataError):
            ma_crossover_signal([1.0, 2.0, -3.0, 4.0], fast=2, slow=4)


class TestZScoreReversion:
    def test_overbought_fades_short(self) -> None:
        assert zscore_reversion_signal([10.0, 10.0, 10.0, 10.0, 20.0], window=5, entry_z=1.5) == -1

    def test_oversold_buys(self) -> None:
        assert zscore_reversion_signal([20.0, 20.0, 20.0, 20.0, 10.0], window=5, entry_z=1.5) == 1

    def test_within_band_is_flat(self) -> None:
        assert zscore_reversion_signal([10.0, 11.0, 10.0, 11.0, 10.0], window=5, entry_z=1.5) == 0

    def test_flat_window_is_flat(self) -> None:
        assert zscore_reversion_signal([10.0] * 5, window=5, entry_z=1.5) == 0

    def test_insufficient_history_is_flat(self) -> None:
        assert zscore_reversion_signal([10.0, 11.0], window=5, entry_z=1.5) == 0

    def test_bad_params_fail_loud(self) -> None:
        with pytest.raises(DataError):
            zscore_reversion_signal([10.0] * 5, window=1, entry_z=1.5)
        with pytest.raises(DataError):
            zscore_reversion_signal([10.0] * 5, window=5, entry_z=0.0)


class TestBreakout:
    def test_new_high_breaks_out_long(self) -> None:
        closes = [10.0, 11.0, 12.0, 13.0, 20.0]
        assert breakout_signal(closes, closes, closes, window=3) == 1

    def test_new_low_breaks_out_short(self) -> None:
        closes = [20.0, 13.0, 12.0, 11.0, 5.0]
        assert breakout_signal(closes, closes, closes, window=3) == -1

    def test_inside_channel_is_flat(self) -> None:
        closes = [10.0, 11.0, 12.0, 11.0, 11.5]
        assert breakout_signal(closes, closes, closes, window=3) == 0

    def test_current_bar_excluded_from_its_own_channel(self) -> None:
        # the current bar's own high must not define the channel it breaks (uses prior bars only)
        closes = [10.0, 11.0, 12.0, 13.0]
        highs = [10.0, 11.0, 12.0, 99.0]  # only the current bar is extreme
        assert breakout_signal(highs, closes, closes, window=3) == 1  # last close 13 > prior max 12

    def test_insufficient_history_is_flat(self) -> None:
        closes = [10.0, 11.0, 12.0]
        assert breakout_signal(closes, closes, closes, window=3) == 0

    def test_length_mismatch_fails_loud(self) -> None:
        with pytest.raises(DataError):
            breakout_signal([1.0, 2.0], [1.0], [1.0, 2.0], window=1)

    def test_bad_window_fails_loud(self) -> None:
        with pytest.raises(DataError):
            breakout_signal([1.0, 2.0], [1.0, 2.0], [1.0, 2.0], window=0)
