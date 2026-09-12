"""Visibility graphs: the adjacency matches a brute-force definition and the pinned upstream
implementation (including the author's worked example), the average shortest path matches a
networkx-convention reference, and the rolling indicator is capped and honest about warm-up."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    average_shortest_path,
    geometric_brownian_series,
    rolling_vg_shortest_path,
    visibility_graph,
)
from alpha_patterns.visibility import MAX_VG_LOOKBACK

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


def _brute_force(x: np.ndarray, *, horizontal: bool) -> np.ndarray:
    n = x.size
    adj = np.zeros((n, n), dtype=bool)
    for a, b in combinations(range(n), 2):
        ok = True
        for c in range(a + 1, b):
            if horizontal:
                if x[c] >= min(x[a], x[b]):
                    ok = False
                    break
            elif x[c] >= x[a] + (x[b] - x[a]) * (c - a) / (b - a):
                ok = False
                break
        adj[a, b] = adj[b, a] = ok
    return adj


class TestAdjacency:
    @pytest.mark.parametrize("horizontal", [False, True])
    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_matches_brute_force_definition(self, horizontal: bool, seed: int) -> None:
        x = np.random.default_rng(seed).normal(size=40)
        np.testing.assert_array_equal(
            visibility_graph(x, horizontal=horizontal), _brute_force(x, horizontal=horizontal)
        )

    def test_consecutive_bars_always_see_each_other(self) -> None:
        adj = visibility_graph(np.random.default_rng(5).normal(size=30))
        assert all(adj[i, i + 1] for i in range(29)) and not adj.diagonal().any()

    def test_guards(self) -> None:
        with pytest.raises(DataError, match="cap the window"):
            visibility_graph(np.arange(MAX_VG_LOOKBACK + 1, dtype=np.float64))
        with pytest.raises(DataError, match="non-finite"):
            visibility_graph(np.array([1.0, np.nan, 2.0]))
        with pytest.raises(DataError, match="times"):
            visibility_graph(np.arange(5.0), times=np.arange(4.0))

    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "visibility.json").read_text())
        ex = fx["example"]
        np.testing.assert_array_equal(
            visibility_graph(np.array(ex["data"], dtype=float)).astype(int), ex["nvg"]
        )
        np.testing.assert_array_equal(
            visibility_graph(np.array(ex["data"], dtype=float), horizontal=True).astype(int),
            ex["hvg"],
        )
        s = fx["series"]
        close = geometric_brownian_series(
            int(s["n_bars"]),
            vol_per_bar=float(s["vol_per_bar"]),
            seed=int(s["seed"]),
            start=float(s["start"]),
        ).close
        for w in fx["windows"]:
            seg = close[w["start"] : w["start"] + w["n"]]
            np.testing.assert_array_equal(visibility_graph(seg).astype(int), w["nvg"])
            np.testing.assert_array_equal(
                visibility_graph(seg, horizontal=True).astype(int), w["hvg"]
            )


class TestShortestPath:
    def test_path_graph_and_star(self) -> None:
        path = np.zeros((4, 4), dtype=bool)
        for i in range(3):
            path[i, i + 1] = path[i + 1, i] = True
        # ordered pairs: 6 of distance 1, 4 of distance 2, 2 of distance 3 -> 20/12
        assert average_shortest_path(path) == pytest.approx(20 / 12)
        star = np.zeros((4, 4), dtype=bool)
        star[0, 1:] = star[1:, 0] = True
        assert average_shortest_path(star) == pytest.approx((6 * 1 + 6 * 2) / 12)

    def test_disconnected_fails_loud(self) -> None:
        with pytest.raises(DataError, match="disconnected"):
            average_shortest_path(np.zeros((3, 3), dtype=bool))

    def test_rolling_matches_pinned_reference(self) -> None:
        fx = json.loads((FIXTURES / "visibility.json").read_text())
        s = fx["series"]
        close = geometric_brownian_series(
            int(s["n_bars"]),
            vol_per_bar=float(s["vol_per_bar"]),
            seed=int(s["seed"]),
            start=float(s["start"]),
        ).close
        sp = fx["shortest_path"]
        pos, neg = rolling_vg_shortest_path(close, lookback=int(sp["lookback"]))
        np.testing.assert_allclose(
            pos, [np.nan if v is None else v for v in sp["pos"]], rtol=1e-12, equal_nan=True
        )
        np.testing.assert_allclose(
            neg, [np.nan if v is None else v for v in sp["neg"]], rtol=1e-12, equal_nan=True
        )

    def test_rolling_guards(self) -> None:
        with pytest.raises(DataError, match="lookback"):
            rolling_vg_shortest_path(np.arange(20.0), lookback=1)
