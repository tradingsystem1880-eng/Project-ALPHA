from datetime import date

import pytest
from pydantic import ValidationError

from alpha_core import ActionType, CorporateAction


def test_split_requires_positive_ratio() -> None:
    a = CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT,
                        ex_date=date(2020, 8, 31), announce_date=date(2020, 7, 30), ratio=4.0)
    assert a.ratio == 4.0
    with pytest.raises(ValidationError):
        CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT, ex_date=date(2020, 8, 31))


def test_knowledge_time_falls_back_to_ex_date_when_announce_missing() -> None:
    a = CorporateAction(symbol="X", action_type=ActionType.SPLIT, ex_date=date(2021, 1, 5), ratio=2.0)
    assert a.knowledge_time == date(2021, 1, 5)
    assert a.knowledge_is_estimated is True
    b = CorporateAction(symbol="X", action_type=ActionType.SPLIT, ex_date=date(2021, 1, 5),
                        announce_date=date(2020, 12, 20), ratio=2.0)
    assert b.knowledge_time == date(2020, 12, 20)
    assert b.knowledge_is_estimated is False
