"""PIP pattern miner: k-means++ clusters of z-scored PIP windows scored by the Martin ratio.

Provenance: github.com/neurotrader888/TechnicalAnalysisAutomation/pip_pattern_miner.py and
wf_pip_miner.py @ da99c20 (MIT). Adapted: takes pre-extracted PIP windows (``alpha_patterns``
cannot be imported here), replaces ``pyclustering`` with numpy k-means++ (Arthur & Vassilvitskii
2007) and a brute-force silhouette (Rousseeuw 1987), threads an explicit seed instead of global
state, and purges training labels that would cross ``train_end`` (upstream let the hold period
read past the training boundary). The walk-forward variant trains on a fixed trailing window of
``train_bars`` (upstream's slice grows because it subtracts the *next* retrain index) and does not
drop windows whose interior PIP positions repeat the previous window's — every row is a sample.
The Martin ratio is return sum over the Ulcer index (Martin & McCann 1989); it is ``None`` when
the equity curve never draws down, never a division by zero.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from alpha_core import DataError

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.intp]


@dataclass(frozen=True, slots=True)
class KMeansResult:
    centers: FloatArray  # shape (k, dim)
    labels: IntArray  # shape (n,)
    inertia: float


def _matrix(rows: npt.ArrayLike, label: str) -> FloatArray:
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise DataError(f"{label} must be a non-empty two-dimensional array")
    if not np.all(np.isfinite(matrix)):
        raise DataError(f"{label} must contain only finite values")
    return matrix


def _sq_dist(rows: FloatArray, centers: FloatArray) -> FloatArray:
    diff = rows[:, None, :] - centers[None, :, :]
    return np.asarray(np.einsum("ijk,ijk->ij", diff, diff), dtype=np.float64)


def kmeans_pp(rows: npt.ArrayLike, k: int, *, seed: int, max_iter: int = 300) -> KMeansResult:
    """Lloyd's k-means from a D²-sampled k-means++ initialisation (Arthur & Vassilvitskii 2007).

    Deterministic for a given ``seed``. An emptied cluster is re-seeded at the point farthest from
    its centre so ``k`` clusters always survive.
    """
    matrix = _matrix(rows, "k-means rows")
    n = matrix.shape[0]
    if k < 2 or k >= n:
        raise DataError(f"k must be in [2, {n - 1}], got {k}")
    rng = np.random.default_rng(seed)
    centers = np.empty((k, matrix.shape[1]), dtype=np.float64)
    centers[0] = matrix[rng.integers(n)]
    closest = _sq_dist(matrix, centers[:1])[:, 0]
    for c in range(1, k):
        total = float(closest.sum())
        if total == 0.0:
            raise DataError("k-means rows collapse onto fewer than k distinct points")
        centers[c] = matrix[rng.choice(n, p=closest / total)]
        closest = np.minimum(closest, _sq_dist(matrix, centers[c : c + 1])[:, 0])
    labels = np.zeros(n, dtype=np.intp)
    for _ in range(max_iter):
        dist = _sq_dist(matrix, centers)
        new_labels = np.argmin(dist, axis=1).astype(np.intp)
        for c in range(k):
            members = matrix[new_labels == c]
            if members.shape[0] == 0:
                farthest = int(np.argmax(dist[np.arange(n), new_labels]))
                centers[c] = matrix[farthest]
                new_labels[farthest] = c
            else:
                centers[c] = members.mean(axis=0)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
    inertia = float(np.sum((matrix - centers[labels]) ** 2))
    return KMeansResult(centers=centers, labels=labels, inertia=inertia)


def silhouette_score(rows: npt.ArrayLike, labels: npt.ArrayLike) -> float:
    """Mean silhouette (Rousseeuw 1987): s = (b - a) / max(a, b); singletons score 0."""
    matrix = _matrix(rows, "silhouette rows")
    tags = np.asarray(labels, dtype=np.intp)
    n = matrix.shape[0]
    if tags.shape != (n,):
        raise DataError("silhouette labels must have one entry per row")
    clusters = np.unique(tags)
    if clusters.size < 2 or clusters.size >= n:
        raise DataError("silhouette requires between 2 and n-1 clusters")
    dist = np.sqrt(_sq_dist(matrix, matrix))
    scores = np.zeros(n, dtype=np.float64)
    for i in range(n):
        own = tags == tags[i]
        size = int(own.sum())
        if size < 2:
            continue
        a = float(dist[i, own].sum() / (size - 1))
        b = min(float(dist[i, tags == c].mean()) for c in clusters if c != tags[i])
        scores[i] = (b - a) / max(a, b) if max(a, b) > 0.0 else 0.0
    return float(scores.mean())


def martin_ratio(log_returns: npt.ArrayLike) -> float | None:
    """Sum of log returns over the Ulcer index of the compounded equity.

    The denominator is Martin & McCann's (1989) Ulcer index, sqrt(mean(drawdown-from-running-
    peak²)). The numerator deviates from their Ulcer Performance Index, which divides the
    excess return over a risk-free rate: upstream (and this port) uses the raw sum of log
    returns with no risk-free term and no annualisation, so the value is a relative ranking
    of clusters, not a published performance statistic. A negative-sum series is mirrored
    before the index is taken and the sign restored, as upstream does, so long and short edges
    score symmetrically. ``None`` when the series is empty or the equity never draws down.
    """
    rets = np.asarray(log_returns, dtype=np.float64)
    if rets.ndim != 1:
        raise DataError("Martin ratio returns must be one-dimensional")
    if not np.all(np.isfinite(rets)):
        raise DataError("Martin ratio returns must be finite")
    if rets.size == 0:
        return None
    total = float(rets.sum())
    signed = -rets if total < 0.0 else rets
    equity = np.exp(np.cumsum(signed))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    ulcer = float(np.sqrt(np.mean(drawdown**2)))
    if ulcer == 0.0:
        return None
    ratio = abs(total) / ulcer
    return -ratio if total < 0.0 else ratio


@dataclass(frozen=True, slots=True)
class PipClusterModel:
    centers: FloatArray  # shape (k, n_pips), z-scored pattern space
    labels: IntArray  # cluster of each training window
    k: int
    silhouette: float
    cluster_martins: tuple[float | None, ...]
    long_cluster: int
    short_cluster: int
    fit_martin: float | None
    hold: int

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PipClusterModel):
            return NotImplemented
        return (
            np.array_equal(self.centers, other.centers)
            and np.array_equal(self.labels, other.labels)
            and (self.k, self.silhouette, self.cluster_martins, self.long_cluster)
            == (other.k, other.silhouette, other.cluster_martins, other.long_cluster)
            and (self.short_cluster, self.fit_martin, self.hold)
            == (other.short_cluster, other.fit_martin, other.hold)
        )


@dataclass(frozen=True, slots=True)
class PipPrediction:
    cluster: int
    signal: float  # +1 long cluster, -1 short cluster, 0 otherwise


def _zscore(pattern: npt.ArrayLike, width: int) -> FloatArray:
    values = np.asarray(pattern, dtype=np.float64)
    if values.shape != (width,) or not np.all(np.isfinite(values)):
        raise DataError(f"pattern must be {width} finite values")
    spread = float(np.std(values))
    if spread == 0.0:
        raise DataError("a flat pattern cannot be z-scored")
    return (values - float(np.mean(values))) / spread


def _select_k(matrix: FloatArray, k_range: tuple[int, int], seed: int) -> KMeansResult:
    k_min, k_max = k_range
    if k_min < 2 or k_max < k_min:
        raise DataError(f"k_range must satisfy 2 <= k_min <= k_max, got {k_range}")
    if k_max >= matrix.shape[0]:
        raise DataError(f"k_range upper bound {k_max} needs more than {k_max} windows")
    best: tuple[float, KMeansResult] | None = None
    for k in range(k_min, k_max + 1):
        result = kmeans_pp(matrix, k, seed=seed)
        score = silhouette_score(matrix, result.labels)
        if best is None or score > best[0]:
            best = (score, result)
    assert best is not None
    return best[1]


def _cluster_signals(
    labels: IntArray, ends: IntArray, k: int, hold: int, length: int
) -> FloatArray:
    signals = np.zeros((k, length), dtype=np.float64)
    for end, label in zip(ends, labels, strict=True):
        signals[label, end : end + hold] = 1.0
    return signals


def fit_pip_clusters(
    windows: npt.ArrayLike,
    end_index: npt.ArrayLike,
    log_close: npt.ArrayLike,
    *,
    train_end: int,
    hold: int,
    k_range: tuple[int, int] = (5, 40),
    seed: int,
) -> PipClusterModel:
    """Cluster training windows and pick the best-long / best-short cluster by Martin ratio.

    ``windows`` are z-scored PIP rows knowable at ``end_index``; ``log_close`` supplies the
    next-bar log returns. Every window must satisfy ``end_index + hold <= train_end`` so no
    training label reads a bar after the boundary; the function raises otherwise. Only
    ``log_close[: train_end + 1]`` is ever read.
    """
    matrix = _matrix(windows, "PIP windows")
    ends = np.asarray(end_index, dtype=np.intp)
    closes = np.asarray(log_close, dtype=np.float64)
    if closes.ndim != 1:
        raise DataError("log_close must be one-dimensional")
    if hold < 1:
        raise DataError(f"hold must be >= 1, got {hold}")
    if train_end < 0 or train_end >= closes.size:
        raise DataError(f"train_end must index log_close (size {closes.size}), got {train_end}")
    if ends.shape != (matrix.shape[0],):
        raise DataError("end_index must have one entry per window")
    if ends.size and (int(ends.min()) < 0 or int(ends.max()) + hold > train_end):
        raise DataError("every training window needs end_index + hold <= train_end")
    closes = closes[: train_end + 1]
    if not np.all(np.isfinite(closes)):
        raise DataError("log_close must be finite up to train_end")
    returns = np.diff(closes)  # returns[i] = close[i+1] - close[i], knowable at i+1
    clustering = _select_k(matrix, k_range, seed)
    k = clustering.centers.shape[0]
    signals = _cluster_signals(clustering.labels, ends, k, hold, returns.size)
    martins = tuple(martin_ratio(signals[c] * returns) for c in range(k))
    defined = [(m, c) for c, m in enumerate(martins) if m is not None]
    if len(defined) < 2:
        raise DataError("fewer than two clusters have a defined Martin ratio")
    long_cluster = max(defined)[1]
    short_cluster = min(defined)[1]
    combined = (signals[long_cluster] - signals[short_cluster]) * returns
    return PipClusterModel(
        centers=clustering.centers,
        labels=clustering.labels,
        k=k,
        silhouette=silhouette_score(matrix, clustering.labels),
        cluster_martins=martins,
        long_cluster=long_cluster,
        short_cluster=short_cluster,
        fit_martin=martin_ratio(combined),
        hold=hold,
    )


def predict_pip_cluster(model: PipClusterModel, pattern: npt.ArrayLike) -> PipPrediction:
    """Nearest cluster of a raw PIP price vector (z-scored here) and its directional signal."""
    row = _zscore(pattern, model.centers.shape[1])
    cluster = int(np.argmin(_sq_dist(row[None, :], model.centers)[0]))
    signal = 0.0
    if cluster == model.long_cluster:
        signal = 1.0
    elif cluster == model.short_cluster:
        signal = -1.0
    return PipPrediction(cluster=cluster, signal=signal)


def walk_forward_pip_signal(
    windows: npt.ArrayLike,
    end_index: npt.ArrayLike,
    log_close: npt.ArrayLike,
    *,
    train_bars: int,
    step_bars: int,
    hold: int,
    k_range: tuple[int, int] = (5, 40),
    seed: int,
) -> FloatArray:
    """Per-bar ±1/0 signal from models refit every ``step_bars`` on the trailing ``train_bars``.

    Requires stride-1 windows (one row per bar from the first full window). The first model is
    fit at bar ``train_bars - 1`` on bars ``[0, train_bars)``; a prediction at bar ``i`` uses the
    window ending at ``i`` and the latest model, and a non-zero signal is held for ``hold`` bars
    unless a new non-zero prediction replaces it.
    """
    matrix = _matrix(windows, "PIP windows")
    ends = np.asarray(end_index, dtype=np.intp)
    closes = np.asarray(log_close, dtype=np.float64)
    if closes.ndim != 1 or not np.all(np.isfinite(closes)):
        raise DataError("log_close must be a finite one-dimensional array")
    n = closes.size
    if ends.shape != (matrix.shape[0],) or ends.size == 0:
        raise DataError("end_index must have one entry per window")
    first = int(ends[0])
    if not np.array_equal(ends, np.arange(first, n, dtype=np.intp)):
        raise DataError("walk-forward requires stride-1 windows ending at every bar")
    if step_bars < 1 or train_bars < 2 or train_bars > n:
        raise DataError("train_bars must be in [2, len(log_close)] and step_bars >= 1")
    signal = np.zeros(n, dtype=np.float64)
    model: PipClusterModel | None = None
    next_train = train_bars - 1
    retrain = 0
    current = 0.0
    remaining = 0
    for i in range(n):
        if i >= next_train:
            start = i - train_bars + 1
            rows = (ends >= start) & (ends + hold <= i)
            fit_seed = int(np.random.SeedSequence([seed, retrain]).generate_state(1)[0])
            model = fit_pip_clusters(
                matrix[rows],
                ends[rows] - start,
                closes[start : i + 1],
                train_end=i - start,
                hold=hold,
                k_range=k_range,
                seed=fit_seed,
            )
            next_train += step_bars
            retrain += 1
        if model is None or i < first:
            continue
        if remaining > 0:
            remaining -= 1
        if remaining == 0:
            current = 0.0
        prediction = predict_pip_cluster(model, matrix[i - first])
        if prediction.signal != 0.0:
            current = prediction.signal
            remaining = hold
        signal[i] = current
    return signal


__all__ = [
    "KMeansResult",
    "PipClusterModel",
    "PipPrediction",
    "fit_pip_clusters",
    "kmeans_pp",
    "martin_ratio",
    "predict_pip_cluster",
    "silhouette_score",
    "walk_forward_pip_signal",
]
