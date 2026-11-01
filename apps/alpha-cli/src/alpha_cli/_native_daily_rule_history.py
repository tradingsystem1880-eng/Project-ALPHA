"""Bounded routing/accounting metadata, never authority to replace a research root."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from alpha_core import DataError

if TYPE_CHECKING:
    from alpha_cli.control_store import ControlStore

from alpha_cli._native_daily_rule_identity import NAME

_MAX_CONTRACT_BYTES = 1_048_576
_MAX_HISTORY_RECORDS = 10_000
_MAX_METADATA_BYTES = 16 * 1024 * 1024
_MAX_SQLITE_OFFSET = 2**63 - 1
_CLASSIFIED = """
WITH bounded AS (
    SELECT contract_id, project_id, created_at,
        CASE WHEN length(CAST(payload_json AS BLOB)) > :max_bytes
                  OR instr(payload_json, char(0)) > 0 THEN NULL
             WHEN json_valid(payload_json) THEN payload_json ELSE NULL END AS document
    FROM research_contracts
), classified AS (
    SELECT contract_id, project_id, created_at,
        CASE WHEN json_type(document) = 'object'
                  AND (SELECT COUNT(*) FROM json_each(document) WHERE key='protocol') = 1
                  AND json_type(document, '$.protocol') = 'object'
                  AND (SELECT COUNT(*) FROM json_each(document, '$.protocol')
                       WHERE key='d0_operator') = 1
                  AND json_type(document, '$.protocol.d0_operator') = 'object'
                  AND (SELECT COUNT(*) FROM json_each(document, '$.protocol.d0_operator')
                       WHERE key='name') = 1
                  AND json_type(document, '$.protocol.d0_operator.name') = 'text'
                  AND instr(json_extract(document, '$.protocol.d0_operator.name'), char(0)) = 0
                  AND length(CAST(json_extract(document, '$.protocol.d0_operator.name') AS BLOB))
                      BETWEEN 1 AND 100
             THEN CASE WHEN json_extract(document, '$.protocol.d0_operator.name') = :daily_name
                       THEN 'daily' ELSE 'other' END
             ELSE 'unknown' END AS route
    FROM bounded
)
"""


def read_history(store: ControlStore, *, limit: int, offset: int) -> dict[str, object]:
    """Read one schema-checked snapshot without fetching contract or artifact payloads."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise DataError("daily history limit must be in 1..200")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or not 0 <= offset <= _MAX_SQLITE_OFFSET
    ):
        raise DataError(f"daily history offset must be in 0..{_MAX_SQLITE_OFFSET}")
    parameters = {
        "max_bytes": _MAX_CONTRACT_BYTES,
        "daily_name": NAME,
        "limit": limit + 1,
        "offset": offset,
    }
    with store._readonly_transaction() as connection:
        _require_columns(connection)
        for query in (
            "SELECT COUNT(*) FROM research_contracts",
            "SELECT COUNT(*) FROM research_launch_reservations",
            "SELECT COUNT(*) FROM jobs",
        ):
            count = connection.execute(query).fetchone()[0]
            if count > _MAX_HISTORY_RECORDS:
                raise DataError(
                    "daily history exceeds bounded metadata inspection; history is unknown"
                )
        payload_bytes = connection.execute(
            "SELECT COALESCE(SUM(length(CAST(payload_json AS BLOB))), 0) FROM research_contracts"
        ).fetchone()[0]
        if payload_bytes > _MAX_METADATA_BYTES:
            raise DataError("daily history exceeds metadata byte budget; history is unknown")
        row = connection.execute(
            _CLASSIFIED
            + """SELECT COUNT(*) AS contract_count,
                COALESCE(SUM(route='daily'), 0) AS daily_contract_count,
                COALESCE(SUM(route='unknown'), 0) AS unclassified_contract_count
            FROM classified""",
            parameters,
        ).fetchone()
        assert row is not None
        counts = {
            name: int(row[name])
            for name in ("contract_count", "daily_contract_count", "unclassified_contract_count")
        }
        row = connection.execute(
            _CLASSIFIED
            + """SELECT COUNT(*) AS reservation_count,
                COALESCE(SUM(r.phase='deep_research' AND c.route='daily'), 0)
                    AS daily_deep_reservation_count,
                COALESCE(SUM(r.phase='deep_research' AND
                    (c.route IS NULL OR c.route='unknown')), 0)
                    AS unclassified_deep_reservation_count
            FROM research_launch_reservations r LEFT JOIN classified c
                ON c.contract_id=r.contract_id AND c.project_id=r.project_id""",
            parameters,
        ).fetchone()
        assert row is not None
        counts.update(
            {
                name: int(row[name])
                for name in (
                    "reservation_count",
                    "daily_deep_reservation_count",
                    "unclassified_deep_reservation_count",
                )
            }
        )
        counts["attempt_count"] = int(
            connection.execute("SELECT COUNT(*) FROM research_attempt_records").fetchone()[0]
        )
        counts["event_study_job_count"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE kind='research:event-study'"
            ).fetchone()[0]
        )
        rows = connection.execute(
            _CLASSIFIED
            + """SELECT
                CASE WHEN length(CAST(contract_id AS BLOB)) BETWEEN 1 AND 100
                          AND instr(contract_id, char(0))=0 THEN contract_id END AS contract_id,
                CASE WHEN length(CAST(project_id AS BLOB)) BETWEEN 1 AND 100
                          AND instr(project_id, char(0))=0 THEN project_id END AS project_id,
                CASE WHEN length(CAST(created_at AS BLOB)) BETWEEN 1 AND 100
                          AND instr(created_at, char(0))=0 THEN created_at END AS created_at
            FROM classified WHERE route='daily'
            ORDER BY created_at, contract_id LIMIT :limit OFFSET :offset""",
            parameters,
        ).fetchall()
        if any(value is None for row in rows for value in row):
            raise DataError("daily history contains invalid or oversized identifier metadata")
        contracts = [dict(row) for row in rows[:limit]]
    truncated = offset > 0 or len(rows) > limit
    return {
        "schema": "DailyRuleHistoryMetadataV1",
        "authority": "none",
        "new_root_authorized": False,
        **counts,
        "limit": limit,
        "offset": offset,
        "truncated": truncated,
        "routing_metadata_complete": not truncated
        and counts["unclassified_contract_count"] == 0
        and counts["unclassified_deep_reservation_count"] == 0,
        "contracts": contracts,
        "aggregate_counts_truncated": False,
        "scope": "Metadata only; not contract validation or authority to move/initialize a store.",
        "exposure_guard_scope": "Daily deep reservations across the entire selected store.",
        "job_count_scope": "Event-study jobs include other routes and unlinked jobs; not liveness.",
        "next_action": "Keep this store; resolve prior/unknown history before selecting a root.",
    }


def _require_columns(connection: sqlite3.Connection) -> None:
    required = {
        "research_launch_reservations": {"contract_id", "project_id", "phase"},
        "research_attempt_records": {"attempt_id"},
        "jobs": {"kind"},
    }
    for table, columns in required.items():
        observed = {str(row["name"]) for row in connection.execute(f'PRAGMA table_info("{table}")')}
        if columns - observed:
            raise DataError("read-only daily history schema is missing required columns")
