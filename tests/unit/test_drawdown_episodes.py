"""Drawdown decomposition: how often, how deep, how long, and did it come back."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_validation import drawdown_episodes, max_drawdown


def test_a_monotonically_rising_curve_has_no_episodes() -> None:
    assert drawdown_episodes([1.0, 1.1, 1.2, 1.3]) == ()


def test_the_worst_episode_matches_the_scalar_max_drawdown() -> None:
    equity = [1.0, 1.2, 0.9, 1.0, 1.3, 1.1, 1.4]
    worst = drawdown_episodes(equity)[0]
    assert worst.depth == pytest.approx(max_drawdown(equity))


def test_a_recovered_episode_reports_where_it_recovered() -> None:
    equity = [1.0, 1.2, 0.9, 1.25]
    (episode,) = drawdown_episodes(equity)
    assert (episode.peak_index, episode.trough_index, episode.recovery_index) == (1, 2, 3)
    assert episode.length == 1
    assert episode.recovery_length == 1
    assert episode.depth == pytest.approx(-0.25)


def test_an_unrecovered_episode_is_reported_as_open_rather_than_dropped() -> None:
    """The case a max-drawdown scalar hides, and the one that decides survivability."""
    equity = [1.0, 1.5, 1.2, 1.1, 1.3]
    (episode,) = drawdown_episodes(equity)
    assert episode.recovery_index is None
    assert episode.recovery_length is None
    assert episode.trough_index == 3


def test_episodes_are_ranked_worst_first_and_do_not_overlap() -> None:
    equity = [1.0, 1.5, 1.0, 1.6, 1.44, 1.7, 1.19, 1.8]
    episodes = drawdown_episodes(equity)
    assert [round(item.depth, 4) for item in episodes] == sorted(
        round(item.depth, 4) for item in episodes
    )
    spans = [(item.peak_index, item.recovery_index or len(equity)) for item in episodes]
    ordered = sorted(spans)
    assert all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:], strict=False))


def test_the_ranking_is_truncated_to_the_requested_depth() -> None:
    equity = [1.0, 1.5, 1.0, 1.6, 1.2, 1.7, 1.1, 1.8, 1.4, 1.9]
    assert len(drawdown_episodes(equity, top=2)) == 2


def test_a_non_positive_top_is_rejected() -> None:
    with pytest.raises(DataError, match="top must be a positive integer"):
        drawdown_episodes([1.0, 0.9, 1.1], top=0)


def test_degenerate_input_fails_loud() -> None:
    with pytest.raises(DataError, match="needs >= 2 equity points"):
        drawdown_episodes([1.0])
