"""Small, dependency-free statistics for benchmark reporting."""

from __future__ import annotations

import math
from collections.abc import Sequence

_Z95 = 1.959963984540054


def wilson(successes: int, n: int, z: float = _Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (Wilson 1927)."""
    if n <= 0:
        raise ValueError("wilson interval needs n > 0")
    if not 0 <= successes <= n:
        raise ValueError(f"successes {successes} outside [0, {n}]")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def pass_hat_k(successes: int, n: int, k: int) -> float:
    """Unbiased estimate of P(all k i.i.d. trials succeed) = C(c,k)/C(n,k) (tau-bench pass^k)."""
    if k <= 0 or k > n:
        raise ValueError(f"pass^k needs 1 <= k <= n (k={k}, n={n})")
    if not 0 <= successes <= n:
        raise ValueError(f"successes {successes} outside [0, {n}]")
    return math.comb(successes, k) / math.comb(n, k)


def zero_failure_upper_bound(n: int, confidence: float = 0.95) -> float:
    """One-sided exact upper bound on a failure rate after n trials with zero failures."""
    if n <= 0:
        raise ValueError("n must be positive")
    return float(1.0 - (1.0 - confidence) ** (1.0 / n))


def mean_ci(values: Sequence[float], z: float = _Z95) -> tuple[float, float, float]:
    """Mean with a normal-approximation CI; degenerate (n<2) gives a zero-width interval."""
    if not values:
        raise ValueError("mean_ci needs at least one value")
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, mean, mean
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    half = z * math.sqrt(var / n)
    return mean, mean - half, mean + half


def paired_delta(before: Sequence[float], after: Sequence[float]) -> tuple[float, float, float]:
    """Mean paired difference (after - before) with a normal CI."""
    if len(before) != len(after):
        raise ValueError("paired_delta needs equal-length samples")
    return mean_ci([a - b for a, b in zip(before, after, strict=True)])
