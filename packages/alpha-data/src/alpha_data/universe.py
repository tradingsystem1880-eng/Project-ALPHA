"""CSV import for point-in-time universe membership (Phase B B3). Pure; fails loud."""

from __future__ import annotations

import csv
import io
from datetime import date

from pydantic import ValidationError

from alpha_core import DataError, UniverseMembership

REQUIRED_COLUMNS = ("symbol", "effective_from", "effective_to", "delisting_return", "reason")


def _optional_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def parse_universe_csv(text: str) -> list[UniverseMembership]:
    """Parse ``symbol,effective_from,effective_to,delisting_return,reason`` rows.

    Blank ``effective_to`` means still a member; blank ``delisting_return``/``reason`` are None.
    """
    reader = csv.DictReader(io.StringIO(text))
    header = tuple(reader.fieldnames or ())
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise DataError(f"universe CSV is missing column(s): {', '.join(missing)}")
    rows: list[UniverseMembership] = []
    for number, raw in enumerate(reader, start=2):
        try:
            rows.append(
                UniverseMembership(
                    symbol=raw["symbol"].strip(),
                    effective_from=date.fromisoformat(raw["effective_from"].strip()),
                    effective_to=_optional_date(raw["effective_to"].strip()),
                    delisting_return=(
                        float(raw["delisting_return"]) if raw["delisting_return"].strip() else None
                    ),
                    reason=raw["reason"].strip() or None,
                )
            )
        except (ValueError, ValidationError) as exc:
            raise DataError(f"universe CSV row {number} is invalid: {exc}") from exc
    if not rows:
        raise DataError("universe CSV has no membership rows")
    return rows
