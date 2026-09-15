"""Visibility graphs of a price window and their average shortest path.

A natural visibility graph joins two bars when the straight line between their values clears
every bar in between; the horizontal variant joins them when every bar in between is lower than
both. Consecutive bars are always joined, so the graph is connected and the average shortest path
(mean over ordered pairs) is defined. ``rolling_vg_shortest_path`` computes it on each trailing
window for the series and its negative, which the upstream study compares as a trend read.

Provenance: github.com/neurotrader888/TimeSeriesVisibilityGraphs/{ts_to_vg,network_indicators}.py
@d646293 (MIT); adapted: a boolean adjacency, a breadth-first average shortest path instead of
``networkx``/``ts2vg``, ``DataError`` validation, and a ``lookback`` cap because the divide-and-
conquer construction is quadratic per window. The visibility rules are unchanged (parity fixture
``tests/fixtures/neurotrader/visibility.json``). Lacasa et al. (2008); Luque et al. (2009).
"""

from __future__ import annotations

from collections import deque

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import FloatArray

MAX_VG_LOOKBACK = 500


def visibility_graph(
    values: FloatArray, *, horizontal: bool = False, times: FloatArray | None = None
) -> np.ndarray:
    """Symmetric boolean adjacency of the (natural or horizontal) visibility graph."""
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:
        raise DataError(f"visibility graph needs a 1-D array of >= 2 values, got shape {x.shape}")
    if not bool(np.all(np.isfinite(x))):
        raise DataError("visibility graph input contains non-finite values")
    if x.size > MAX_VG_LOOKBACK:
        raise DataError(f"visibility graph is quadratic; cap the window at {MAX_VG_LOOKBACK} bars")
    t = (
        np.arange(x.size, dtype=np.float64)
        if times is None
        else np.asarray(times, dtype=np.float64)
    )
    if t.shape != x.shape:
        raise DataError("times must match values in length")
    adj = np.zeros((x.size, x.size), dtype=bool)

    def divide(left: int, right: int) -> None:
        if left >= right:
            return
        k = int(np.argmax(x[left : right + 1])) + left
        for i in range(left, right + 1):
            if i == k:
                continue
            visible = True
            for j in range(min(i + 1, k + 1), max(i, k)):
                if horizontal:
                    blocked = x[j] >= x[i]
                else:
                    blocked = x[j] >= x[i] + (x[k] - x[i]) * ((t[j] - t[i]) / (t[k] - t[i]))
                if blocked:
                    visible = False
                    break
            if visible:
                adj[k, i] = adj[i, k] = True
        divide(left, k - 1)
        divide(k + 1, right)

    divide(0, x.size - 1)
    return adj


def average_shortest_path(adjacency: np.ndarray) -> float:
    """Mean shortest-path length over ordered node pairs (``networkx`` convention)."""
    adj = np.asarray(adjacency, dtype=bool)
    n = int(adj.shape[0])
    if adj.ndim != 2 or adj.shape != (n, n) or n < 2:
        raise DataError(f"adjacency must be square with >= 2 nodes, got {adj.shape}")
    total = 0
    for source in range(n):
        dist = np.full(n, -1, dtype=np.intp)
        dist[source] = 0
        queue: deque[int] = deque([source])
        while queue:
            u = queue.popleft()
            for v in np.nonzero(adj[u])[0]:
                if dist[v] < 0:
                    dist[v] = dist[u] + 1
                    queue.append(int(v))
        if bool(np.any(dist < 0)):
            raise DataError("graph is disconnected; average shortest path is undefined")
        total += int(dist.sum())
    return float(total) / float(n * (n - 1))


def rolling_vg_shortest_path(close: FloatArray, *, lookback: int) -> tuple[FloatArray, FloatArray]:
    """``(on price, on -price)`` average shortest paths of the natural visibility graph over
    ``[i-lookback+1, i]``; NaN before ``lookback`` bars exist (upstream starts at ``lookback``)."""
    c = np.asarray(close, dtype=np.float64)
    if c.ndim != 1 or c.size < 2:
        raise DataError(f"need a 1-D array of >= 2 closes, got shape {c.shape}")
    if lookback < 2 or lookback > MAX_VG_LOOKBACK or lookback >= c.size:
        raise DataError(
            f"lookback must be in [2, {min(MAX_VG_LOOKBACK, c.size - 1)}], got {lookback}"
        )
    pos = np.full(c.size, np.nan)
    neg = np.full(c.size, np.nan)
    for i in range(lookback, c.size):
        window = c[i - lookback + 1 : i + 1]
        pos[i] = average_shortest_path(visibility_graph(window))
        neg[i] = average_shortest_path(visibility_graph(-window))
    return pos, neg
