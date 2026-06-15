"""Corporate-action / instrument-lifecycle types. See spec §6.1 (two-clock model)."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class ActionType(StrEnum):
    SPLIT = "split"
    DIVIDEND = "dividend"
    REDENOMINATION = "redenomination"
    SYMBOL_MIGRATION = "symbol_migration"


class CorporateAction(BaseModel):
    """A point-in-time instrument-lifecycle event.

    Two clocks: ``ex_date`` (valid time — when the price mechanically adjusts) and
    knowledge time (``announce_date`` if present, else a conservative ``ex_date`` fallback).
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    action_type: ActionType
    ex_date: date
    announce_date: date | None = None
    record_date: date | None = None
    pay_date: date | None = None
    ratio: float | None = None  # SPLIT: new/old shares (a 4-for-1 split → 4.0)
    amount: float | None = None  # DIVIDEND: cash per share

    @property
    def knowledge_time(self) -> date:
        return self.announce_date if self.announce_date is not None else self.ex_date

    @property
    def knowledge_is_estimated(self) -> bool:
        return self.announce_date is None

    @model_validator(mode="after")
    def _check_payload(self) -> CorporateAction:
        if self.action_type is ActionType.SPLIT and (self.ratio is None or self.ratio <= 0):
            raise ValueError("SPLIT requires ratio > 0")
        if self.action_type is ActionType.DIVIDEND and (self.amount is None or self.amount <= 0):
            raise ValueError("DIVIDEND requires amount > 0")
        if self.announce_date is not None and self.announce_date > self.ex_date:
            raise ValueError("announce_date cannot be after ex_date")
        return self
