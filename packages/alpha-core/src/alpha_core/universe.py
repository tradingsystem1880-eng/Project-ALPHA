"""Point-in-time universe membership (Phase B B3).

A cross-sectional study is only interpretable over the names that were *members* as of each
decision date, including names that later left (delisted, acquired, dropped from the index).
``UniverseMembership`` records one membership interval with the same two-clock discipline as
corporate actions: ``effective_from`` is inclusive, ``effective_to`` is exclusive and ``None``
while the name is still a member. ``members_as_of`` is the only sanctioned read.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator


class UniverseMembership(BaseModel):
    """One membership interval ``[effective_from, effective_to)`` for ``symbol``."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    effective_from: date
    effective_to: date | None = None
    delisting_return: float | None = None  # final-day return when the name left via delisting
    reason: str | None = None  # e.g. "index_add", "index_drop", "delisted", "acquired"

    @model_validator(mode="after")
    def _check_interval(self) -> UniverseMembership:
        if not self.symbol.strip():
            raise ValueError("membership symbol must not be blank")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        if self.delisting_return is not None:
            if not math.isfinite(self.delisting_return):
                raise ValueError("delisting_return must be finite")
            if self.effective_to is None:
                raise ValueError("delisting_return requires an effective_to")
        return self


def members_as_of(memberships: Iterable[UniverseMembership], when: date) -> list[str]:
    """Symbols whose interval covers ``when``; sorted, deduplicated. Never looks past ``when``."""
    names = {
        m.symbol
        for m in memberships
        if m.effective_from <= when and (m.effective_to is None or when < m.effective_to)
    }
    return sorted(names)
