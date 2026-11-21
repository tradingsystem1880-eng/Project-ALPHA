"""Errors raised by the bounded crypto acquisition command."""

from alpha_core import DataError


class FixtureAccountingBlocked(DataError):
    """An acquisition option was refused; the command never turns it into a bad parameter."""

    def __init__(self, code: str) -> None:
        super().__init__(f"synthetic backfill accounting blocked: {code}")
        self.reason_code = code
