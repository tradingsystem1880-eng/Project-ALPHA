from datetime import date
from pathlib import Path

import pytest

from alpha_core import ActionType, CorporateAction, DataError
from alpha_data.store import ParquetStore


def _actions() -> list[CorporateAction]:
    return [
        CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT,
                        ex_date=date(2020, 8, 31), ratio=4.0),
        CorporateAction(symbol="AAPL", action_type=ActionType.DIVIDEND,
                        ex_date=date(2020, 8, 7), amount=0.82),
    ]


def test_actions_round_trip(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_actions("AAPL", _actions())
    out = store.read_actions("AAPL")
    assert out == _actions()  # exact pydantic equality


def test_read_actions_missing_returns_empty(tmp_path: Path) -> None:
    # absence of actions is normal (e.g. crypto) — return [], not an error
    assert ParquetStore(tmp_path).read_actions("NONE") == []


def test_actions_symbol_sanitized(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    with pytest.raises(DataError):
        store.write_actions("../x", [])
