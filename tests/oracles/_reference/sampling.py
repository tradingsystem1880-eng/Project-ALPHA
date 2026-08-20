"""Shared zero-skill noise-matrix sampling for the oracle suite's Monte Carlo tolerance tests."""

from __future__ import annotations

import numpy as np


def noise_matrix(rng: np.random.Generator, t: int = 256, s: int = 12) -> np.ndarray:
    """Zero-skill Gaussian noise, mean 0.0 / std 0.01, shaped (t sessions, s configs)."""
    return rng.normal(0.0, 0.01, size=(t, s))
