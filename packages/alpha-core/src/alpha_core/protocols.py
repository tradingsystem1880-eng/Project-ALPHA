"""Structural interfaces. Concrete implementations live in higher packages."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime

from alpha_core.types import Bar, ValidationOutcome


@runtime_checkable
class DataSource(Protocol):
    """A point-in-time source of market data. Implementations must never return future data."""

    def available_symbols(self) -> list[str]: ...

    def as_of(self, symbol: str, when: AwareDatetime) -> list[Bar]:
        """Return bars for `symbol` whose data was knowable no later than `when`."""
        ...


@runtime_checkable
class Validator(Protocol):
    """A statistical validation gate applied to a backtest result."""

    name: str

    def validate(self, result: object) -> ValidationOutcome: ...
