"""Metamorphic and differential oracles for the PIP pattern miner (alpha_research.pip_miner).

Primary sources: Arthur & Vassilvitskii, "k-means++: The Advantages of Careful Seeding" (SODA
2007) for D²-weighted seeding; Lloyd, "Least Squares Quantization in PCM" (IEEE Trans. Inf.
Theory 1982) for the fixed point (every centre is the mean of its members, every point is
nearest its own centre); Rousseeuw, "Silhouettes: a graphical aid to the interpretation and
validation of cluster analysis" (J. Comput. Appl. Math. 1987) for s(i) = (b - a) / max(a, b);
Martin & McCann, *The Investor's Guide to Fidelity Funds* (1989) for the Ulcer index
sqrt(mean(drawdown²)) and the Martin ratio return / UI. A wrong seeding weight, a mis-ordered
a/b, or a drawdown taken against the start rather than the running peak breaks a relation below.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_research.pip_miner import (
    fit_pip_clusters,
    kmeans_pp,
    martin_ratio,
    silhouette_score,
)
from tests.oracles._reference.tolerances import FLOAT64_REL

pytestmark = pytest.mark.oracle

_RNG = np.random.default_rng(11)


def _blobs(k: int, per: int, dim: int, spread: float) -> tuple[np.ndarray, np.ndarray]:
    centers = _RNG.normal(0.0, 10.0, size=(k, dim))
    rows = np.vstack([centers[c] + _RNG.normal(0.0, spread, size=(per, dim)) for c in range(k)])
    return rows, np.repeat(np.arange(k), per)


def _reference_silhouette(rows: np.ndarray, labels: np.ndarray) -> float:
    """Rousseeuw (1987) eq. (1)–(3) written out per point with explicit loops."""
    n = rows.shape[0]
    total = 0.0
    for i in range(n):
        same = [j for j in range(n) if j != i and labels[j] == labels[i]]
        if not same:
            continue  # singleton: s(i) = 0 by convention
        a = float(np.mean([np.linalg.norm(rows[i] - rows[j]) for j in same]))
        b = min(
            float(np.mean([np.linalg.norm(rows[i] - rows[j]) for j in range(n) if labels[j] == c]))
            for c in np.unique(labels)
            if c != labels[i]
        )
        total += (b - a) / max(a, b)
    return float(total / n)


# ---------------------------------------------------------------- k-means


def test_kmeans_result_is_a_lloyd_fixed_point() -> None:
    rows, _ = _blobs(4, 25, 3, 1.0)
    result = kmeans_pp(rows, 4, seed=3)
    for c in range(4):
        members = rows[result.labels == c]
        assert members.shape[0] > 0
        np.testing.assert_allclose(result.centers[c], members.mean(axis=0), rtol=FLOAT64_REL)
    dist = np.linalg.norm(rows[:, None, :] - result.centers[None, :, :], axis=2)
    assert np.array_equal(np.argmin(dist, axis=1), result.labels)


def test_kmeans_labels_are_invariant_to_positive_affine_maps_of_the_rows() -> None:
    """D² seeding weights and Euclidean nearest-centre rules are scale/shift invariant."""
    rows, _ = _blobs(3, 20, 4, 0.5)
    base = kmeans_pp(rows, 3, seed=5)
    mapped = kmeans_pp(rows * 2.5 + 7.0, 3, seed=5)
    assert np.array_equal(base.labels, mapped.labels)
    np.testing.assert_allclose(mapped.centers, base.centers * 2.5 + 7.0, rtol=1e-9)
    assert mapped.inertia == pytest.approx(base.inertia * 2.5**2, rel=FLOAT64_REL)


def test_kmeans_recovers_well_separated_planted_clusters_for_any_seed() -> None:
    rows, truth = _blobs(5, 30, 3, 0.2)
    for seed in range(6):
        result = kmeans_pp(rows, 5, seed=seed)
        pairs = {(int(a), int(b)) for a, b in zip(result.labels, truth, strict=True)}
        assert len(pairs) == 5  # one-to-one relabelling of the truth


# ---------------------------------------------------------------- silhouette


def test_silhouette_matches_the_loop_reference_and_stays_bounded() -> None:
    rows, truth = _blobs(3, 12, 2, 3.0)
    labels = kmeans_pp(rows, 3, seed=1).labels
    assert silhouette_score(rows, labels) == pytest.approx(
        _reference_silhouette(rows, labels), rel=FLOAT64_REL
    )
    for k in (2, 3, 5):
        score = silhouette_score(rows, kmeans_pp(rows, k, seed=2).labels)
        assert -1.0 <= score <= 1.0
    # arbitrary labels, including singletons, still obey the reference
    arbitrary = np.array([0] * 10 + [1] * 25 + [2])
    assert silhouette_score(rows, arbitrary) == pytest.approx(
        _reference_silhouette(rows, arbitrary), rel=FLOAT64_REL
    )
    assert silhouette_score(rows, truth) > silhouette_score(rows, arbitrary)


def test_silhouette_is_invariant_to_row_order() -> None:
    rows, truth = _blobs(3, 15, 2, 1.0)
    order = np.random.default_rng(4).permutation(rows.shape[0])
    assert silhouette_score(rows[order], truth[order]) == pytest.approx(
        silhouette_score(rows, truth), rel=FLOAT64_REL
    )


# ---------------------------------------------------------------- Martin ratio


def test_martin_ratio_equals_return_over_ulcer_index_from_running_peak() -> None:
    rets = _RNG.normal(0.001, 0.02, size=250)
    equity = np.exp(np.cumsum(rets))
    peak = np.maximum.accumulate(equity)
    ulcer = np.sqrt(np.mean(((equity - peak) / peak) ** 2))
    expected = float(rets.sum() / ulcer)
    value = martin_ratio(rets)
    assert value is not None and value == pytest.approx(expected, rel=FLOAT64_REL)
    # drawdown measured from the start value instead of the running peak is a different number
    from_start = np.sqrt(np.mean((np.minimum(equity - 1.0, 0.0)) ** 2))
    assert not np.isclose(expected, rets.sum() / from_start)


def test_martin_ratio_is_odd_under_return_negation() -> None:
    rets = _RNG.normal(0.0, 0.02, size=120)
    forward = martin_ratio(rets)
    mirrored = martin_ratio(-rets)
    assert forward is not None and mirrored is not None
    assert mirrored == pytest.approx(-forward, rel=FLOAT64_REL)


def test_martin_ratio_is_undefined_without_a_drawdown() -> None:
    assert martin_ratio(np.full(10, 0.01)) is None
    assert martin_ratio(np.zeros(10)) is None


# ---------------------------------------------------------------- fit


def test_fit_is_seed_deterministic_and_purges_boundary_crossing_labels() -> None:
    log_close = np.cumsum(_RNG.normal(0.0, 0.01, size=400))
    windows = _RNG.normal(size=(300, 5))
    ends = np.arange(30, 330)
    first = fit_pip_clusters(
        windows, ends, log_close, train_end=340, hold=8, k_range=(3, 5), seed=1
    )
    again = fit_pip_clusters(
        windows, ends, log_close, train_end=340, hold=8, k_range=(3, 5), seed=1
    )
    assert first == again
    with pytest.raises(DataError, match="end_index \\+ hold <= train_end"):
        fit_pip_clusters(windows, ends, log_close, seed=1, train_end=336, hold=8, k_range=(3, 5))
