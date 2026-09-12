"""Irreversibility measures: reversible inputs score low, the asynchronous index behaves as
defined, and both measures reproduce the pinned upstream implementation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    async_index,
    perm_ts_reversibility,
    relative_async_index,
    rolling_perm_reversibility,
    rolling_relative_async_index,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


class TestAsyncIndex:
    def test_identical_order_is_zero_and_reversed_is_one(self) -> None:
        a = np.arange(10.0)
        assert async_index(a, a) == 0.0
        assert async_index(a, -a) == 1.0

    def test_guard(self) -> None:
        with pytest.raises(DataError):
            async_index(np.ones(3), np.ones(2))


class TestMeasures:
    def test_palindrome_window_is_perfectly_reversible(self) -> None:
        half = np.random.default_rng(3).normal(size=60)
        pal = np.concatenate([half, half[::-1]])
        kl = perm_ts_reversibility(pal)
        assert np.isnan(kl) or kl == pytest.approx(0.0, abs=1e-12)

    def test_deterministic_map_is_more_irreversible_than_a_sine(self) -> None:
        fx = json.loads((FIXTURES / "reversibility.json").read_text())
        vals = {c["name"]: np.array(c["values"]) for c in fx["cases"]}
        assert relative_async_index(vals["logistic"]) > relative_async_index(vals["sine"])

    def test_guards(self) -> None:
        with pytest.raises(DataError, match=">= 10"):
            perm_ts_reversibility(np.arange(5.0))
        with pytest.raises(DataError, match="window"):
            rolling_perm_reversibility(np.arange(50.0), window=5)
        with pytest.raises(DataError, match="window"):
            rolling_relative_async_index(np.arange(50.0), window=2)

    def test_rolling_variants_warm_up(self) -> None:
        x = np.random.default_rng(8).normal(size=120)
        a = rolling_perm_reversibility(x, window=40)
        b = rolling_relative_async_index(x, window=40)
        assert np.all(np.isnan(a[:39])) and np.all(np.isnan(b[:39]))
        assert np.isfinite(b[39:]).all()

    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "reversibility.json").read_text())
        for case in fx["cases"]:
            x = np.array(case["values"])
            kl = perm_ts_reversibility(x)
            if case["perm_reversibility"] is None:
                assert np.isnan(kl)
            else:
                assert kl == pytest.approx(case["perm_reversibility"], rel=1e-12)
            assert relative_async_index(x) == pytest.approx(case["rai"], rel=1e-12)
