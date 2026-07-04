"""``make_replay_surrogate``: bar-index signal replay for the Tier-1 null (kronos)."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_cli._surrogate import make_replay_surrogate, make_surrogate
from alpha_core import DataError
from alpha_validation import FloatArray


def test_matches_generic_surrogate_for_a_constant_signal() -> None:
    n = 40
    rng = np.random.default_rng(3)
    pr = rng.normal(0.001, 0.01, n)

    def always_long(_closes: FloatArray) -> int:
        return 1

    generic = make_surrogate(
        signal_fn=always_long, warmup=5, vol_window=4, target_vol=0.15, rebalance_every=3
    )
    replay = make_replay_surrogate(
        signals_by_bar=[1 if t >= 5 and (t - 5) % 3 == 0 else None for t in range(n)],
        warmup=5,
        vol_window=4,
        target_vol=0.15,
        rebalance_every=3,
    )
    assert np.allclose(generic(pr), replay(pr))


def test_fails_loud_on_uncovered_rebalance_index() -> None:
    replay = make_replay_surrogate(
        signals_by_bar=[None] * 20, warmup=5, vol_window=4, target_vol=0.15, rebalance_every=3
    )
    with pytest.raises(DataError, match="cover"):
        replay(np.full(20, 0.01))
