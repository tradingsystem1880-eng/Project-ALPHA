"""Reading run artifacts into the plain tuples the figure contract accepts.

Every fault here is one that would otherwise become a silently wrong figure: a null
treated as zero, a NaN plotted as a gap, a series rebased against nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_cli.figures import _sources as src
from alpha_core import DataError


def test_a_missing_artifact_is_none_not_an_exception(tmp_path: Path) -> None:
    assert src.frame(tmp_path, "absent.parquet") is None


def test_requiring_a_missing_artifact_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="missing or empty"):
        src.require(tmp_path, "absent.parquet")


def test_requiring_an_empty_artifact_fails_loud(tmp_path: Path) -> None:
    pl.DataFrame({"ts": []}).write_parquet(tmp_path / "empty.parquet")
    with pytest.raises(DataError, match="missing or empty"):
        src.require(tmp_path, "empty.parquet")


def test_a_symlinked_artifact_is_ignored(tmp_path: Path) -> None:
    """Run directories are immutable; a symlink in one is not a file we will read."""
    real = tmp_path / "real.parquet"
    pl.DataFrame({"a": [1]}).write_parquet(real)
    link = tmp_path / "link.parquet"
    link.symlink_to(real)
    assert src.frame(tmp_path, "link.parquet") is None


class TestSampling:
    def test_a_short_series_is_returned_whole(self) -> None:
        assert src.sample(5, 100) == [0, 1, 2, 3, 4]

    def test_a_capped_series_keeps_its_endpoints(self) -> None:
        picked = src.sample(1000, 10)
        assert picked[0] == 0
        assert picked[-1] == 999
        assert len(picked) == 10

    def test_a_single_point_cap_takes_the_first(self) -> None:
        assert src.sample(1000, 1) == [0]


class TestConversion:
    def test_timestamps_become_epoch_seconds(self) -> None:
        series = pl.Series([datetime(2024, 1, 1, tzinfo=UTC)])
        assert src.epochs(series) == (1_704_067_200.0,)

    def test_a_numeric_timestamp_column_passes_through(self) -> None:
        assert src.epochs(pl.Series([1.5, 2.5])) == (1.5, 2.5)

    def test_a_non_timestamp_is_refused(self) -> None:
        with pytest.raises(DataError, match="expected a timestamp"):
            src.epochs(pl.Series(["nope"]))

    def test_a_null_in_a_required_series_is_refused_rather_than_zeroed(self) -> None:
        with pytest.raises(DataError, match="non-numeric"):
            src.floats(pl.Series([1.0, None]), name="equity")

    def test_a_non_finite_value_is_refused(self) -> None:
        with pytest.raises(DataError, match="non-finite"):
            src.floats(pl.Series([1.0, float("inf")]), name="equity")

    def test_a_nullable_series_keeps_its_nulls(self) -> None:
        """A missing exposure is missing, not zero exposure."""
        assert src.optional_floats(pl.Series([1.0, None])) == (1.0, None)

    def test_a_non_finite_optional_becomes_none(self) -> None:
        assert src.optional_floats(pl.Series([float("nan")])) == (None,)

    def test_strings_render_nulls_as_empty(self) -> None:
        assert src.strings(pl.Series(["a", None])) == ("a", "")


class TestDerived:
    def test_drawdown_is_zero_on_a_rising_curve(self) -> None:
        assert src.drawdown((1.0, 1.1, 1.2)) == (0.0, 0.0, 0.0)

    def test_drawdown_measures_against_the_running_peak(self) -> None:
        assert src.drawdown((1.0, 2.0, 1.0))[2] == pytest.approx(-0.5)

    def test_rebasing_normalises_to_the_first_point(self) -> None:
        assert src.rebase((200.0, 300.0))[0] == 1.0

    def test_rebasing_against_zero_is_refused(self) -> None:
        with pytest.raises(DataError, match="first value is zero"):
            src.rebase((0.0, 1.0))

    def test_rebasing_an_empty_series_is_refused(self) -> None:
        with pytest.raises(DataError, match="first value is zero"):
            src.rebase(())


class TestBars:
    def test_a_run_without_a_symbol_is_not_applicable(self, tmp_path: Path) -> None:
        rows, reason = src.bars({}, data_dir=tmp_path)
        assert rows == []
        assert reason == "not_applicable"

    def test_a_run_without_a_snapshot_cannot_reproduce_its_bars(self, tmp_path: Path) -> None:
        rows, reason = src.bars({"symbol": "TEST"}, data_dir=tmp_path)
        assert rows == []
        assert reason == "snapshot_unavailable"
