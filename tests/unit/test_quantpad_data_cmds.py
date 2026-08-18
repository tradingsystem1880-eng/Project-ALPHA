from __future__ import annotations

import pytest

from alpha_cli.quantpad_data_cmds import _bounds
from alpha_core import DataError


def test_bounds_accepts_only_one_complete_date_or_epoch_ms_pair() -> None:
    assert _bounds("2026-08-14", "2026-08-15", None, None) == (
        1_786_665_600_000,
        1_786_752_000_000,
    )
    assert _bounds(None, None, 1_786_665_600_000, 1_786_752_000_000) == (
        1_786_665_600_000,
        1_786_752_000_000,
    )


@pytest.mark.parametrize(
    "values",
    [
        ("2026-08-14", None, None, None),
        (None, None, 1, None),
        ("2026-08-14", "2026-08-15", 1, 2),
        (None, None, 2, 1),
    ],
)
def test_bounds_rejects_mixed_or_incomplete_pairs(
    values: tuple[str | None, str | None, int | None, int | None],
) -> None:
    with pytest.raises(DataError):
        _bounds(*values)
