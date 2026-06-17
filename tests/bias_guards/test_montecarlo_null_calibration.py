"""The randomized-price null must not certify structureless noise as a real edge (spec §8, §10).

This is the gauntlet's last line of defence against false discovery: if the null rubber-stamped
random charts, every overfit strategy would "pass". We assert the gate's behaviour on pure noise
*distributionally* — over many independent noise series, not one lucky seed — so the calibration is
earned, not frozen into a hand-picked seed.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_validation.montecarlo import randomized_price_null
from tests.fixtures.validation_fixtures import causal_momentum

pytestmark = pytest.mark.bias_guard


def test_pure_noise_does_not_pass_the_null() -> None:
    percentiles = [
        randomized_price_null(
            np.random.default_rng(data_seed).normal(0.0, 0.01, size=200),
            causal_momentum,
            n_paths=200,
            threshold=0.95,
            seed=data_seed + 1,
        ).percentile
        for data_seed in range(30)
    ]
    # no exploitable structure -> observed is an unremarkable draw -> percentiles ~ Uniform(0, 1)
    assert 0.35 < float(np.mean(percentiles)) < 0.65  # centred, no spurious edge
    false_positives = float(np.mean([p >= 0.95 for p in percentiles]))
    assert false_positives <= 0.2  # ~5% expected at threshold 0.95; never a rubber stamp
