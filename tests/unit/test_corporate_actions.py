from datetime import date
from datetime import date as _date

import pytest
from pydantic import ValidationError

from alpha_core import ActionType, CorporateAction
from alpha_data.corporate import known_actions, split_factor


def test_split_requires_positive_ratio() -> None:
    a = CorporateAction(
        symbol="AAPL",
        action_type=ActionType.SPLIT,
        ex_date=date(2020, 8, 31),
        announce_date=date(2020, 7, 30),
        ratio=4.0,
    )
    assert a.ratio == 4.0
    with pytest.raises(ValidationError):
        CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT, ex_date=date(2020, 8, 31))


def test_split_ratio_and_dividend_amount_must_be_finite() -> None:
    for bad in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValidationError):
            CorporateAction(
                symbol="AAPL", action_type=ActionType.SPLIT, ex_date=date(2020, 8, 31), ratio=bad
            )
        with pytest.raises(ValidationError):
            CorporateAction(
                symbol="AAPL",
                action_type=ActionType.DIVIDEND,
                ex_date=date(2020, 8, 31),
                amount=bad,
            )


def test_knowledge_time_falls_back_to_ex_date_when_announce_missing() -> None:
    a = CorporateAction(
        symbol="X", action_type=ActionType.SPLIT, ex_date=date(2021, 1, 5), ratio=2.0
    )
    assert a.knowledge_time == date(2021, 1, 5)
    assert a.knowledge_is_estimated is True
    b = CorporateAction(
        symbol="X",
        action_type=ActionType.SPLIT,
        ex_date=date(2021, 1, 5),
        announce_date=date(2020, 12, 20),
        ratio=2.0,
    )
    assert b.knowledge_time == date(2020, 12, 20)
    assert b.knowledge_is_estimated is False


def _aapl_split() -> CorporateAction:
    return CorporateAction(
        symbol="AAPL",
        action_type=ActionType.SPLIT,
        ex_date=_date(2020, 8, 31),
        announce_date=_date(2020, 7, 30),
        ratio=4.0,
    )


def test_known_actions_gates_by_knowledge_time() -> None:
    a = _aapl_split()
    assert known_actions([a], _date(2020, 7, 29)) == []  # before announce → unknown
    assert known_actions([a], _date(2020, 7, 30)) == [a]  # on announce → known
    assert known_actions([a], _date(2020, 9, 1)) == [a]


def test_split_factor_applies_only_before_ex_date() -> None:
    splits = [_aapl_split()]
    assert split_factor(_date(2020, 8, 28), splits) == 0.25  # pre-ex → 1/4
    assert split_factor(_date(2020, 8, 31), splits) == 1.0  # ex day → unadjusted
    assert split_factor(_date(2020, 9, 1), splits) == 1.0


def test_multiple_splits_compound() -> None:
    s1 = CorporateAction(
        symbol="X", action_type=ActionType.SPLIT, ex_date=_date(2021, 1, 1), ratio=2.0
    )
    s2 = CorporateAction(
        symbol="X", action_type=ActionType.SPLIT, ex_date=_date(2022, 1, 1), ratio=3.0
    )
    # a bar before both is divided by 2*3 = 6
    assert split_factor(_date(2020, 6, 1), [s1, s2]) == pytest.approx(1 / 6)
    # a bar between them is divided by 3 only
    assert split_factor(_date(2021, 6, 1), [s1, s2]) == pytest.approx(1 / 3)


def test_announce_after_ex_date_rejected() -> None:
    with pytest.raises(ValidationError):
        CorporateAction(
            symbol="X",
            action_type=ActionType.SPLIT,
            ex_date=date(2021, 1, 5),
            announce_date=date(2021, 1, 6),
            ratio=2.0,
        )
