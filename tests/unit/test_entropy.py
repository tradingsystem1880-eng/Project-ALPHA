"""Permutation entropy: regular series score 0, random orderings score near 1, and both the
pattern codes and the rolling entropy reproduce the pinned upstream implementation."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import geometric_brownian_series, ordinal_patterns, permutation_entropy

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


class TestOrdinalPatterns:
    def test_codes_are_in_range_with_nan_head(self) -> None:
        codes = ordinal_patterns(np.array([3.0, 1.0, 2.0, 5.0, 4.0, 0.0]), 3)
        assert np.isnan(codes[:2]).all()
        assert set(codes[2:].astype(int)) <= set(range(math.factorial(3)))

    def test_monotone_windows_share_one_code(self) -> None:
        codes = ordinal_patterns(np.arange(30, dtype=np.float64), 4)[3:]
        assert len(set(codes.astype(int))) == 1

    def test_guards(self) -> None:
        with pytest.raises(DataError, match="d must be >= 2"):
            ordinal_patterns(np.arange(10.0), 1)
        with pytest.raises(DataError, match="non-finite"):
            ordinal_patterns(np.array([1.0, np.nan, 2.0]), 2)


class TestPermutationEntropy:
    def test_regular_series_has_zero_entropy(self) -> None:
        out = permutation_entropy(np.arange(200, dtype=np.float64), d=3, mult=5)
        assert np.all(np.isnan(out[: 30 + 2])) and np.allclose(out[32:], 0.0)

    def test_random_orderings_approach_one(self) -> None:
        rng = np.random.default_rng(1)
        out = permutation_entropy(rng.normal(size=2000), d=3, mult=50)
        assert np.nanmean(out) > 0.95

    def test_guard(self) -> None:
        with pytest.raises(DataError, match="mult"):
            permutation_entropy(np.arange(50.0), d=3, mult=0)

    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "entropy.json").read_text())
        s = fx["series"]
        close = geometric_brownian_series(
            int(s["n_bars"]),
            vol_per_bar=float(s["vol_per_bar"]),
            seed=int(s["seed"]),
            start=float(s["start"]),
        ).close
        for case in fx["cases"]:
            codes = ordinal_patterns(close, int(case["d"]))
            np.testing.assert_allclose(
                codes,
                np.array([np.nan if v is None else v for v in case["ordinals"]]),
                equal_nan=True,
            )
            ent = permutation_entropy(close, d=int(case["d"]), mult=int(case["mult"]))
            np.testing.assert_allclose(
                ent,
                np.array([np.nan if v is None else v for v in case["entropy"]]),
                rtol=1e-12,
                equal_nan=True,
            )
