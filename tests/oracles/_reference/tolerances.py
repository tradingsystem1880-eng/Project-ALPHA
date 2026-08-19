"""Named tolerances shared across the oracle suite.

Each constant names the *sense* of a tolerance literal that recurred, verbatim, across
oracle tests; the numeric value is unchanged from where it was previously inlined.
"""

from __future__ import annotations

import math

# Relative tolerance for float64 algebraic identities (scale/shift/annualisation invariances
# in test_metamorphic_metrics.py) that should round-trip to within double precision.
FLOAT64_REL = 1e-9

# Absolute dollar tolerance between the engine's equity curve and an independently
# rederived one (test_pnl_rederivation.py, test_metamorphic_engine.py).
ENGINE_MONEY_ABS = 1e-6

# Float slack allowed when asserting a statistic is monotone non-increasing across a
# parameter sweep (test_metamorphic_dsr.py).
MONOTONE_SLACK = 1e-12

_Z = 3.89  # two-sided alpha = 1e-4; see test_calibration_known_truth.py module docstring


def bernoulli_band(p: float, m: int) -> float:
    """Two-sided normal-approximation half-width for a Bernoulli(p) rate over m trials."""
    return _Z * math.sqrt(p * (1.0 - p) / m)
