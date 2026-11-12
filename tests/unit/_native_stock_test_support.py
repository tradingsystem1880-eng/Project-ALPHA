"""Checked structural narrowing and disposable rows for deliberately varied JSON fixtures."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from typing import cast


def record(value: object) -> dict[str, object]:
    assert isinstance(value, dict), "fixture expected an object"
    assert all(isinstance(key, str) for key in value), "fixture expected string object keys"
    return cast(dict[str, object], value)


def array(value: object) -> list[object]:
    assert isinstance(value, list), "fixture expected an array"
    return cast(list[object], value)


@contextmanager
def event_rows(
    source: sqlite3.Connection, rows: Sequence[dict[str, object]], job: str
) -> Iterator[sqlite3.Connection]:
    """Exercise the real SQLite connection contract without touching a retained store."""
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.row_factory = sqlite3.Row
        source.backup(connection)
        # Shadow the copied event table only in this disposable connection.
        # Original store and copied main-schema append-only controls stay intact.
        connection.execute("CREATE TEMP TABLE job_events AS SELECT * FROM main.job_events LIMIT 0")
        for row in rows:
            kind, payload = row["event_type"], row["payload_json"]
            sequence, timestamp = row["sequence"], row["occurred_at"]
            assert isinstance(kind, str) and isinstance(payload, str)
            assert isinstance(sequence, int) and isinstance(timestamp, str)
            connection.execute(
                "INSERT INTO temp.job_events VALUES (?, ?, ?, ?, ?)",
                (job, sequence, kind, timestamp, payload),
            )
        yield connection
