"""Unit tests for the PIP pattern miner (alpha_research.pip_miner)."""

from __future__ import annotations

from functools import partial
from typing import Any, cast

import numpy as np
import pytest

from alpha_core import DataError
from alpha_research.pip_miner import (
    PipClusterModel,
    fit_pip_clusters,
    kmeans_pp,
    martin_ratio,
    predict_pip_cluster,
    silhouette_score,
    walk_forward_pip_signal,
)

_RNG = np.random.default_rng(7)


def _blobs(k: int = 3, per: int = 20, dim: int = 5) -> tuple[np.ndarray, np.ndarray]:
    centers = np.arange(k, dtype=np.float64)[:, None] * 10.0 * np.ones(dim)
    rows = np.vstack([centers[c] + _RNG.normal(0.0, 0.3, size=(per, dim)) for c in range(k)])
    truth = np.repeat(np.arange(k), per)
    return rows, truth


def _random_walk(n: int, seed: int = 3) -> np.ndarray:
    return np.cumsum(np.random.default_rng(seed).normal(0.0, 0.01, size=n))


def _windows(log_close: np.ndarray, lookback: int, n_pips: int) -> tuple[np.ndarray, np.ndarray]:
    from alpha_patterns import pip_windows

    pw = pip_windows(log_close, lookback=lookback, n_pips=n_pips)
    return pw.matrix, pw.end_index


# ---------------------------------------------------------------- kmeans_pp / silhouette


def test_kmeans_recovers_planted_blobs() -> None:
    rows, truth = _blobs()
    result = kmeans_pp(rows, 3, seed=1)
    assert result.centers.shape == (3, 5)
    # labels equal the truth up to a relabelling
    mapping = {int(result.labels[i]): int(truth[i]) for i in range(rows.shape[0])}
    assert len(mapping) == 3
    assert np.array_equal(np.vectorize(mapping.get)(result.labels), truth)
    assert result.inertia == pytest.approx(
        float(np.sum((rows - result.centers[result.labels]) ** 2))
    )


def test_kmeans_is_deterministic_per_seed_and_moves_with_it() -> None:
    rows = _RNG.normal(size=(60, 4))
    a = kmeans_pp(rows, 4, seed=11)
    b = kmeans_pp(rows, 4, seed=11)
    assert np.array_equal(a.labels, b.labels) and np.array_equal(a.centers, b.centers)
    assert a.inertia == b.inertia


def test_kmeans_rejects_degenerate_inputs() -> None:
    rows = _RNG.normal(size=(6, 2))
    with pytest.raises(DataError):
        kmeans_pp(rows, 1, seed=0)
    with pytest.raises(DataError):
        kmeans_pp(rows, 6, seed=0)
    with pytest.raises(DataError):
        kmeans_pp(rows[0], 2, seed=0)
    rows[2, 0] = np.nan
    with pytest.raises(DataError):
        kmeans_pp(rows, 2, seed=0)


def test_silhouette_of_planted_blobs_is_near_one_and_bounded() -> None:
    rows, truth = _blobs()
    score = silhouette_score(rows, truth)
    assert 0.9 < score <= 1.0
    shuffled = np.random.default_rng(0).permutation(truth)
    assert -1.0 <= silhouette_score(rows, shuffled) < score


def test_silhouette_rejects_single_cluster() -> None:
    rows, _ = _blobs()
    with pytest.raises(DataError):
        silhouette_score(rows, np.zeros(rows.shape[0], dtype=np.intp))


# ---------------------------------------------------------------- martin_ratio


def test_martin_ratio_matches_hand_computation() -> None:
    rets = np.array([0.02, -0.01, 0.03, -0.02, 0.01])
    eq = np.exp(np.cumsum(rets))
    dd = eq / np.maximum.accumulate(eq) - 1.0
    ulcer = np.sqrt(np.mean(dd**2))
    assert martin_ratio(rets) == pytest.approx(float(rets.sum() / ulcer))


def test_martin_ratio_is_antisymmetric_and_none_without_drawdown() -> None:
    rets = np.array([0.02, -0.01, 0.03, -0.02, 0.01])
    assert martin_ratio(-rets) == pytest.approx(-float(martin_ratio(rets) or 0.0))
    assert martin_ratio(np.array([0.01, 0.02, 0.0])) is None
    assert martin_ratio(np.array([])) is None
    with pytest.raises(DataError):
        martin_ratio(np.array([0.1, np.nan]))


# ---------------------------------------------------------------- fit / predict


def _fit(n: int = 600, hold: int = 6) -> tuple[PipClusterModel, np.ndarray, np.ndarray, np.ndarray]:
    log_close = _random_walk(n)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    train_end = n - 1
    keep = ends + hold <= train_end
    model = fit_pip_clusters(
        matrix[keep], ends[keep], log_close, train_end=train_end, hold=hold, k_range=(3, 6), seed=5
    )
    return model, log_close, matrix, ends


def test_fit_selects_k_within_range_and_labels_every_window() -> None:
    model, _, matrix, ends = _fit()
    assert 3 <= model.k <= 6
    assert model.centers.shape == (model.k, 5)
    assert model.labels.shape == (int(np.sum(ends + 6 <= 599)),)
    assert -1.0 <= model.silhouette <= 1.0
    assert len(model.cluster_martins) == model.k
    assert model.long_cluster != model.short_cluster
    defined = [m for m in model.cluster_martins if m is not None]
    assert model.cluster_martins[model.long_cluster] == max(defined)
    assert model.cluster_martins[model.short_cluster] == min(defined)


def test_fit_rejects_windows_whose_hold_crosses_train_end() -> None:
    log_close = _random_walk(200)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    with pytest.raises(DataError, match="hold"):
        fit_pip_clusters(matrix, ends, log_close, train_end=199, hold=6, k_range=(3, 4), seed=1)
    with pytest.raises(DataError):
        fit_pip_clusters(matrix, ends, log_close, train_end=400, hold=6, k_range=(3, 4), seed=1)
    with pytest.raises(DataError):
        fit_pip_clusters(
            matrix[:3], ends[:3], log_close, train_end=199, hold=6, k_range=(3, 4), seed=1
        )


def test_fit_reads_only_bars_up_to_train_end() -> None:
    log_close = _random_walk(600)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    train_end = 400
    keep = ends + 6 <= train_end
    base = fit_pip_clusters(
        matrix[keep], ends[keep], log_close, train_end=train_end, hold=6, k_range=(3, 5), seed=2
    )
    poisoned = log_close.copy()
    poisoned[train_end + 1 :] += 50.0
    again = fit_pip_clusters(
        matrix[keep], ends[keep], poisoned, train_end=train_end, hold=6, k_range=(3, 5), seed=2
    )
    assert again == base


def test_predict_returns_nearest_center_and_directional_signal() -> None:
    model, _, matrix, _ = _fit()
    long_center = model.centers[model.long_cluster]
    pred = predict_pip_cluster(model, long_center * 2.0 + 3.0)  # z-scoring undoes the affine map
    assert pred.cluster == model.long_cluster and pred.signal == 1.0
    pred = predict_pip_cluster(model, model.centers[model.short_cluster])
    assert pred.cluster == model.short_cluster and pred.signal == -1.0
    neutral = [c for c in range(model.k) if c not in (model.long_cluster, model.short_cluster)][0]
    assert predict_pip_cluster(model, model.centers[neutral]).signal == 0.0
    with pytest.raises(DataError):
        predict_pip_cluster(model, np.ones(5))
    with pytest.raises(DataError):
        predict_pip_cluster(model, np.arange(4.0))


# ---------------------------------------------------------------- walk-forward


def test_walk_forward_signal_is_zero_before_first_training_and_holds_after() -> None:
    log_close = _random_walk(700)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    signal = walk_forward_pip_signal(
        matrix, ends, log_close, train_bars=300, step_bars=100, hold=6, k_range=(3, 5), seed=9
    )
    assert signal.shape == log_close.shape
    assert not signal[:299].any()
    assert set(np.unique(signal)) <= {-1.0, 0.0, 1.0}
    assert signal[299:].any()
    # a non-zero signal persists for at most `hold` bars without a fresh prediction
    nonzero = np.flatnonzero(signal)
    assert nonzero.size > 0


def test_walk_forward_requires_stride_one_windows() -> None:
    log_close = _random_walk(400)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    with pytest.raises(DataError):
        walk_forward_pip_signal(
            matrix[::2],
            ends[::2],
            log_close,
            train_bars=200,
            step_bars=50,
            hold=6,
            k_range=(3, 4),
            seed=1,
        )
    with pytest.raises(DataError):
        walk_forward_pip_signal(
            matrix, ends, log_close, train_bars=500, step_bars=50, hold=6, k_range=(3, 4), seed=1
        )


# ---------------------------------------------------------------- mutation-hardening


def test_every_data_error_names_its_cause() -> None:
    rows = _RNG.normal(size=(8, 3))
    with pytest.raises(DataError, match=r"^k-means rows must be a non-empty two-dimensional"):
        kmeans_pp(np.empty((0, 3)), 2, seed=0)
    with pytest.raises(DataError, match=r"^k-means rows must contain only finite"):
        kmeans_pp(np.full((8, 3), np.inf), 2, seed=0)
    with pytest.raises(DataError, match=r"^k must be in \[2, 7\], got 8"):
        kmeans_pp(rows, 8, seed=0)
    with pytest.raises(
        DataError, match=r"^k-means rows collapse onto fewer than k distinct points$"
    ):
        kmeans_pp(np.ones((8, 3)), 2, seed=0)
    with pytest.raises(DataError, match=r"^silhouette rows must be a non-empty"):
        silhouette_score(rows[0], [0])
    with pytest.raises(DataError, match=r"^silhouette labels must have one entry per row"):
        silhouette_score(rows, [0, 1])
    with pytest.raises(DataError, match=r"^silhouette requires between 2 and n-1 clusters"):
        silhouette_score(rows, np.arange(8))
    with pytest.raises(DataError, match=r"^Martin ratio returns must be one-dimensional"):
        martin_ratio(rows)
    with pytest.raises(DataError, match=r"^Martin ratio returns must be finite"):
        martin_ratio([0.1, np.inf])
    log_close = _random_walk(120)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    keep = ends + 6 <= 100
    fit = partial(fit_pip_clusters, train_end=100, hold=6, k_range=(3, 4), seed=1)
    with pytest.raises(DataError, match=r"^PIP windows must be a non-empty two-dimensional"):
        fit(matrix[0], ends[:1], log_close)
    with pytest.raises(DataError, match=r"^PIP windows must contain only finite"):
        fit(np.full_like(matrix, np.nan), ends, log_close)
    with pytest.raises(DataError, match=r"^log_close must be one-dimensional"):
        fit(matrix[keep], ends[keep], np.c_[log_close, log_close])
    with pytest.raises(DataError, match=r"^hold must be >= 1, got 0"):
        fit(matrix[keep], ends[keep], log_close, hold=0)
    with pytest.raises(DataError, match=r"^train_end must index log_close \(size 120\), got 120"):
        fit(matrix[keep], ends[keep], log_close, train_end=120)
    with pytest.raises(DataError, match=r"^train_end must index log_close \(size 120\), got -1"):
        fit(matrix[keep], ends[keep], log_close, train_end=-1)
    with pytest.raises(DataError, match=r"^end_index must have one entry per window"):
        fit(matrix[keep], ends[keep][:-1], log_close)
    with pytest.raises(
        DataError, match=r"^every training window needs end_index \+ hold <= train_end$"
    ):
        fit(matrix[keep], ends[keep] - 30, log_close)
    with pytest.raises(DataError, match=r"^log_close must be finite up to train_end"):
        poisoned = log_close.copy()
        poisoned[50] = np.nan
        fit(matrix[keep], ends[keep], poisoned)
    with pytest.raises(DataError, match=r"^k_range must satisfy 2 <= k_min <= k_max, got \(1, 4\)"):
        fit(matrix[keep], ends[keep], log_close, k_range=(1, 4))
    with pytest.raises(DataError, match=r"^k_range must satisfy 2 <= k_min <= k_max, got \(4, 3\)"):
        fit(matrix[keep], ends[keep], log_close, k_range=(4, 3))
    n_keep = int(keep.sum())
    with pytest.raises(DataError, match=rf"^k_range upper bound {n_keep} needs more than {n_keep}"):
        fit(matrix[keep], ends[keep], log_close, k_range=(3, n_keep))
    model = _fit()[0]
    with pytest.raises(DataError, match=r"^pattern must be 5 finite values"):
        predict_pip_cluster(model, [1.0, 2.0, np.nan, 4.0, 5.0])
    with pytest.raises(DataError, match=r"^a flat pattern cannot be z-scored"):
        predict_pip_cluster(model, [2.0] * 5)
    with pytest.raises(DataError, match=r"^log_close must be a finite one-dimensional array"):
        walk_forward_pip_signal(
            matrix,
            ends,
            np.c_[log_close, log_close],
            train_bars=60,
            step_bars=10,
            hold=3,
            k_range=(3, 4),
            seed=1,
        )
    with pytest.raises(DataError, match=r"^end_index must have one entry per window"):
        walk_forward_pip_signal(
            matrix,
            ends[:-1],
            log_close,
            train_bars=60,
            step_bars=10,
            hold=3,
            k_range=(3, 4),
            seed=1,
        )
    with pytest.raises(
        DataError, match=r"^walk-forward requires stride-1 windows ending at every bar$"
    ):
        walk_forward_pip_signal(
            matrix[:-1],
            ends[:-1],
            log_close,
            train_bars=60,
            step_bars=10,
            hold=3,
            k_range=(3, 4),
            seed=1,
        )
    for train_bars, step_bars in ((1, 10), (121, 10), (60, 0)):
        with pytest.raises(DataError, match=r"^train_bars must be in \[2, len\(log_close\)\]"):
            walk_forward_pip_signal(
                matrix,
                ends,
                log_close,
                train_bars=train_bars,
                step_bars=step_bars,
                hold=3,
                k_range=(3, 4),
                seed=1,
            )
    with pytest.raises(DataError, match=r"^PIP windows must be a non-empty two-dimensional"):
        walk_forward_pip_signal(
            matrix[0],
            ends[:1],
            log_close,
            train_bars=60,
            step_bars=10,
            hold=3,
            k_range=(3, 4),
            seed=1,
        )
    rising = np.linspace(0.0, 1.0, 120) + np.sin(np.arange(120)) * 0.001  # every return > 0
    r_matrix, r_ends = _windows(rising, lookback=24, n_pips=5)
    with pytest.raises(DataError, match=r"^fewer than two clusters have a defined Martin ratio$"):
        fit(r_matrix[keep], r_ends[keep], rising)


def test_integer_inputs_are_promoted_to_float() -> None:
    rows = [[0, 0], [0, 1], [10, 10], [10, 11], [20, 20], [20, 21]]
    result = kmeans_pp(rows, 3, seed=0)
    assert result.centers.dtype == np.float64 and result.labels.dtype == np.intp
    assert sorted(result.centers[:, 0].tolist()) == [0.0, 10.0, 20.0]
    assert silhouette_score(rows, [0, 0, 1, 1, 2, 2]) > 0.9
    assert martin_ratio([1, -1, 1]) == pytest.approx(
        float(martin_ratio(np.array([1.0, -1.0, 1.0])) or 0.0)
    )
    one_feature = kmeans_pp([[0], [1], [10], [11]], 2, seed=0)
    assert one_feature.centers.shape == (2, 1)


def test_kmeans_golden_labels_pin_the_seeding_rule() -> None:
    """Exact labels for a fixed seed: any change to D² seeding or Lloyd updates moves them."""
    rows = np.random.default_rng(21).normal(size=(12, 2))
    result = kmeans_pp(rows, 3, seed=4)
    assert result.labels.tolist() == _KMEANS_GOLDEN_LABELS
    assert result.inertia == pytest.approx(_KMEANS_GOLDEN_INERTIA, rel=1e-9)


_KMEANS_GOLDEN_LABELS = [1, 2, 2, 2, 1, 1, 2, 0, 0, 2, 1, 2]
_KMEANS_GOLDEN_INERTIA = 12.37676696894881


def test_silhouette_handles_two_member_clusters_and_coincident_points() -> None:
    rows = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [5.0, 5.0], [5.0, 5.1]])
    # cluster 0: three coincident points (a = 0), cluster 1: two members
    score = silhouette_score(rows, [0, 0, 0, 1, 1])
    b0 = float(np.mean(np.linalg.norm(rows[3:] - rows[0], axis=1)))
    s0 = (b0 - 0.0) / b0
    a3 = float(np.linalg.norm(rows[3] - rows[4]))
    b3 = float(np.mean(np.linalg.norm(rows[:3] - rows[3], axis=1)))
    b4 = float(np.mean(np.linalg.norm(rows[:3] - rows[4], axis=1)))
    expected = (3 * s0 + (b3 - a3) / max(a3, b3) + (b4 - a3) / max(a3, b4)) / 5
    assert score == pytest.approx(expected, rel=1e-12)
    # every point coincident with every other: a = b = 0 ⇒ s = 0 (never NaN)
    assert silhouette_score(np.zeros((4, 2)), [0, 0, 1, 1]) == 0.0


def test_fit_recomputes_cluster_martins_from_hold_period_signals() -> None:
    model, log_close, matrix, ends = _fit(n=400, hold=4)
    keep = ends + 4 <= 399
    returns = np.diff(log_close)
    for c in range(model.k):
        signal = np.zeros(returns.size)
        for end in ends[keep][model.labels == c]:
            signal[end : end + 4] = 1.0
        assert model.cluster_martins[c] == martin_ratio(signal * returns)
    long_signal = np.zeros(returns.size)
    short_signal = np.zeros(returns.size)
    for end, label in zip(ends[keep], model.labels, strict=True):
        if label == model.long_cluster:
            long_signal[end : end + 4] = 1.0
        elif label == model.short_cluster:
            short_signal[end : end + 4] = 1.0
    assert model.fit_martin == martin_ratio((long_signal - short_signal) * returns)
    assert model.hold == 4


def test_fit_boundary_bar_is_read_and_two_clusters_are_enough() -> None:
    log_close = _random_walk(300)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    train_end = 250
    keep = ends + 1 <= train_end
    base = fit_pip_clusters(
        matrix[keep], ends[keep], log_close, train_end=train_end, hold=1, k_range=(2, 2), seed=3
    )
    assert base.k == 2 and base.labels.size == int(keep.sum())
    moved = log_close.copy()
    moved[train_end] += 0.5  # the last bar inside the boundary feeds the final return
    changed = fit_pip_clusters(
        matrix[keep], ends[keep], moved, train_end=train_end, hold=1, k_range=(2, 2), seed=3
    )
    assert changed.cluster_martins != base.cluster_martins
    moved = log_close.copy()
    moved[train_end + 1] = np.nan  # the first bar outside is never read, not even for finiteness
    assert (
        fit_pip_clusters(
            matrix[keep], ends[keep], moved, train_end=train_end, hold=1, k_range=(2, 2), seed=3
        )
        == base
    )


def test_select_k_prefers_the_silhouette_maximum_inside_the_range() -> None:
    rows, _ = _blobs(k=4, per=15, dim=3)
    ends = np.arange(60) * 3
    log_close = _random_walk(200)
    model = fit_pip_clusters(rows, ends, log_close, train_end=199, hold=2, k_range=(2, 3), seed=0)
    assert model.k == 3
    model = fit_pip_clusters(rows, ends, log_close, train_end=199, hold=2, k_range=(2, 5), seed=0)
    assert model.k == 4
    model = fit_pip_clusters(rows, ends, log_close, train_end=199, hold=2, k_range=(5, 5), seed=0)
    assert model.k == 5


def test_model_equality_compares_every_field() -> None:
    import dataclasses

    model = _fit(n=300)[0]
    assert model == model
    assert model != object()
    for field, value in (
        ("centers", model.centers + 1.0),
        ("labels", (model.labels + 1) % model.k),
        ("k", model.k + 1),
        ("silhouette", model.silhouette + 0.1),
        ("cluster_martins", tuple(reversed(model.cluster_martins))),
        ("long_cluster", model.short_cluster),
        ("short_cluster", model.long_cluster),
        ("fit_martin", None),
        ("hold", model.hold + 1),
    ):
        assert dataclasses.replace(model, **cast(dict[str, Any], {field: value})) != model, field


def test_predict_zscores_the_raw_pattern_before_matching() -> None:
    model = _fit()[0]
    for c in range(model.k):
        tiny = model.centers[c] * 0.001 + 100.0
        assert predict_pip_cluster(model, tiny).cluster == c
        assert predict_pip_cluster(model, [int(v) for v in model.centers[c] * 1000]).cluster == c


def test_walk_forward_replays_the_first_model_and_hold_state_machine() -> None:
    log_close = _random_walk(500)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    first = int(ends[0])
    train_bars, step_bars, hold, seed = 300, 150, 4, 9
    signal = walk_forward_pip_signal(
        matrix,
        ends,
        log_close,
        train_bars=train_bars,
        step_bars=step_bars,
        hold=hold,
        k_range=(3, 5),
        seed=seed,
    )
    # replicate the first refit exactly (bars [0, train_bars), seed SeedSequence([seed, 0]))
    i0 = train_bars - 1
    rows = (ends >= 0) & (ends + hold <= i0)
    model = fit_pip_clusters(
        matrix[rows],
        ends[rows],
        log_close[: i0 + 1],
        train_end=i0,
        hold=hold,
        k_range=(3, 5),
        seed=int(np.random.SeedSequence([seed, 0]).generate_state(1)[0]),
    )
    current, remaining = 0.0, 0
    for i in range(i0, i0 + step_bars):
        if remaining > 0:
            remaining -= 1
        if remaining == 0:
            current = 0.0
        pred = predict_pip_cluster(model, matrix[i - first]).signal
        if pred != 0.0:
            current, remaining = pred, hold
        assert signal[i] == current, i
    assert signal[i0 + step_bars :].any()


def test_walk_forward_hold_one_equals_raw_predictions_and_retrains_on_the_trailing_window() -> None:
    log_close = _random_walk(420)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    first = int(ends[0])
    signal = walk_forward_pip_signal(
        matrix, ends, log_close, train_bars=200, step_bars=100, hold=1, k_range=(3, 4), seed=2
    )
    for retrain, i0 in enumerate((199, 299, 399)):
        start = i0 - 200 + 1
        rows = (ends >= start) & (ends + 1 <= i0)
        model = fit_pip_clusters(
            matrix[rows],
            ends[rows] - start,
            log_close[start : i0 + 1],
            train_end=i0 - start,
            hold=1,
            k_range=(3, 4),
            seed=int(np.random.SeedSequence([2, retrain]).generate_state(1)[0]),
        )
        for i in range(i0, min(i0 + 100, 420)):
            assert signal[i] == predict_pip_cluster(model, matrix[i - first]).signal
    assert signal[first:199].tolist() == [0.0] * (199 - first)


def test_walk_forward_accepts_the_boundary_train_and_step_sizes() -> None:
    log_close = _random_walk(110)
    matrix, ends = _windows(log_close, lookback=24, n_pips=5)
    whole = walk_forward_pip_signal(
        matrix, ends, log_close, train_bars=110, step_bars=5, hold=2, k_range=(2, 3), seed=1
    )
    assert not whole[:109].any()
    stepping = walk_forward_pip_signal(
        matrix, ends, log_close, train_bars=100, step_bars=1, hold=2, k_range=(2, 3), seed=1
    )
    assert stepping.shape == (110,) and not stepping[:99].any()
