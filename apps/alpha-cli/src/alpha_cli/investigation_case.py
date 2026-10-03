"""Case-scoped advisory diagnostics; this sidecar has no governed research authority."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from alpha_cli.research_suggestions import suggest_investigations
from alpha_core import DataError

ACTIONS = ("inspect_execution", "inspect_losses", "suggest_followups")


def _encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_encode(value).encode()).hexdigest()


class _Identity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[2] = 2
    question: str = Field(min_length=1, max_length=8000, pattern=r"\S")
    model: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    run: str = Field(min_length=1, max_length=4096)
    cutoff: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    basis_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    max_calls: int = Field(ge=1, le=6)
    request_limit: Literal[12] = 12


class Case:
    """Immutable context plus SQLite action reservations, not a ControlStore replacement.

    ``max_calls`` bounds distinct tool attempts; the immutable request_limit of 12 also bounds
    cached reads and denied prerequisites. The transport separately bounds model turns. Every
    admitted request is reserved before dispatch; process death never replenishes either budget.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        database = self.path / "case.sqlite3"
        if database.is_symlink() or not database.is_file():
            raise DataError("investigation case database missing or symlinked")
        connection = sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @classmethod
    def create(
        cls, path: Path, run: Path, cutoff: str, question: str, model: str, max_calls: int = 6
    ) -> Case:
        packet = suggest_investigations(run, cutoff=cutoff)
        identity = _Identity(
            question=question,
            model=model,
            run=str(run.resolve()),
            cutoff=cutoff,
            basis_sha256=packet["basis_sha256"],
            max_calls=max_calls,
        ).model_dump()
        path.mkdir(parents=True, exist_ok=True)
        case = cls(path)
        database = case.path / "case.sqlite3"
        if database.is_symlink():
            raise DataError("investigation case database cannot be symlinked")
        payload = _encode({"identity": identity, "packet": packet, "case_id": _hash(identity)})
        if database.exists():
            if _encode(case._record()) != payload:
                raise DataError("investigation case identity mismatch")
            return case
        with closing(sqlite3.connect(database, timeout=10)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS context "
                "(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS attempts "
                "(action TEXT PRIMARY KEY, receipt TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS requests "
                "(sequence INTEGER PRIMARY KEY CHECK(sequence BETWEEN 1 AND 12), "
                "action TEXT NOT NULL)"
            )
            row = connection.execute("SELECT payload FROM context WHERE id=1").fetchone()
            if row is not None and row[0] != payload:
                raise DataError("investigation case identity mismatch")
            connection.execute("INSERT OR IGNORE INTO context VALUES (1, ?)", (payload,))
        return case

    @classmethod
    def open(cls, path: Path) -> Case:
        case = cls(path)
        case._record()
        return case

    def _record(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM context WHERE id=1").fetchone()
        if row is None:
            raise DataError("investigation case context missing")
        record: dict[str, Any] = json.loads(row[0])
        identity = _Identity.model_validate(record["identity"]).model_dump()
        if (
            record["case_id"] != _hash(identity)
            or record["packet"]["basis_sha256"] != identity["basis_sha256"]
        ):
            raise DataError("investigation case identity is corrupt")
        with self._connect() as connection:
            self._request_count(connection)
        return record

    @staticmethod
    def _request_count(connection: sqlite3.Connection) -> int:
        try:
            rows = connection.execute(
                "SELECT sequence, action FROM requests ORDER BY sequence LIMIT 13"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise DataError("investigation request ledger missing or corrupt") from exc
        if len(rows) > 12 or any(
            row["sequence"] != index or row["action"] not in ACTIONS
            for index, row in enumerate(rows, 1)
        ):
            raise DataError("investigation request ledger is corrupt")
        return len(rows)

    def _reserve_request(self, action: str, limit: int) -> None:
        # Commit independently: a denied action or evidence error must still consume its request.
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            count = self._request_count(connection)
            if count >= limit:
                raise DataError("investigation request budget exhausted")
            connection.execute("INSERT INTO requests VALUES (?, ?)", (count + 1, action))

    def _verify(self, record: dict[str, Any]) -> dict[str, Any]:
        identity = record["identity"]
        run = Path(identity["run"])
        if run.is_symlink() or any(item.is_symlink() for item in run.iterdir()):
            raise DataError("investigation run evidence cannot be symlinked")
        packet = suggest_investigations(run, cutoff=identity["cutoff"])
        if packet != record["packet"]:
            raise DataError("investigation case evidence or policy changed")
        return packet

    def verify(self) -> dict[str, Any]:
        """Reverify the exact frozen packet; this does not establish claim truth."""
        return self._verify(self._record())

    @staticmethod
    def _result(packet: dict[str, Any], action: str) -> dict[str, Any]:
        if action == "inspect_execution":
            return dict(packet["observations"]["execution"])
        if action == "inspect_losses":
            return {
                "drawdown_episodes": packet["observations"]["drawdown_episodes"],
                "macro_cause": "not_tested",
                "regime_effect": "not_tested",
            }
        return {"suggestions": packet["suggestions"], "executed_experiments": []}

    def _check_receipt(self, record: dict[str, Any], action: str, receipt: dict[str, Any]) -> None:
        expected_id = _hash({"case_id": record["case_id"], "action": action})
        if (
            action not in ACTIONS
            or receipt.get("action") != action
            or receipt.get("id") != expected_id
            or receipt.get("authority") != "none"
            or receipt.get("basis_sha256") != record["identity"]["basis_sha256"]
            or receipt.get("status") not in {"reserved", "failed", "succeeded"}
        ):
            raise DataError("investigation receipt identity mismatch")
        if receipt["status"] == "succeeded":
            result = self._result(record["packet"], action)
            if receipt.get("result") != result or receipt.get("evidence_sha256") != _hash(result):
                raise DataError("investigation receipt evidence mismatch")
        elif "result" in receipt or "evidence_sha256" in receipt:
            raise DataError("unfinished investigation receipt cannot contain evidence")

    def receipts(self) -> list[dict[str, Any]]:
        record = self._record()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT action, receipt FROM attempts ORDER BY rowid"
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            receipt = json.loads(row["receipt"])
            self._check_receipt(record, row["action"], receipt)
            results.append(receipt)
        if any(receipt["status"] == "succeeded" for receipt in results):
            self._verify(record)
        return results

    def context(self) -> dict[str, Any]:
        record = self._record()
        self._verify(record)
        identity = record["identity"]
        with self._connect() as connection:
            request_count = self._request_count(connection)
        return {
            "case_id": record["case_id"],
            "identity_sha256": record["case_id"],
            "question": identity["question"],
            "model": identity["model"],
            "run_id": record["packet"]["observations"]["execution"]["run_id"],
            "cutoff": identity["cutoff"],
            "basis_sha256": identity["basis_sha256"],
            "actions": list(ACTIONS),
            "max_calls": identity["max_calls"],
            "calls_remaining": identity["max_calls"] - len(self.receipts()),
            "request_limit": identity["request_limit"],
            "requests_remaining": identity["request_limit"] - request_count,
            "authority": "none",
            "admitted": False,
            "mode": "retrospective_diagnosis",
            "limitations": [
                "No new experiments or data collection.",
                "References bind evidence; they do not verify model claims.",
                "No agent-wide information isolation is established by this ledger.",
                "max_calls counts tool attempts; model turns need a separate transport budget.",
                "Every admitted tool request, including cached reads and denials, spends one "
                "of the case's 12 requests; report remaining requests before proposing more work.",
            ],
        }

    def call(self, action: str) -> dict[str, Any]:
        """Reserve once, reverify evidence, return a hash-bound result or retained failure."""
        if type(action) is not str or action not in ACTIONS:
            raise DataError("unsupported investigation action")
        record = self._record()
        self._reserve_request(action, record["identity"]["request_limit"])
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT receipt FROM attempts WHERE action=?", (action,)
            ).fetchone()
            if row is not None:
                cached: dict[str, Any] = json.loads(row[0])
            else:
                if action != "inspect_execution":
                    inspection = connection.execute(
                        "SELECT receipt FROM attempts WHERE action='inspect_execution'"
                    ).fetchone()
                    if inspection is None or json.loads(inspection[0])["status"] != "succeeded":
                        raise DataError(
                            "successful inspect_execution required before interpretation"
                        )
                count = connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
                if count >= record["identity"]["max_calls"]:
                    raise DataError("investigation tool budget exhausted")
                cached = {}
                receipt: dict[str, Any] = {
                    "id": _hash({"case_id": record["case_id"], "action": action}),
                    "action": action,
                    "status": "reserved",
                    "authority": "none",
                    "basis_sha256": record["identity"]["basis_sha256"],
                }
                connection.execute("INSERT INTO attempts VALUES (?, ?)", (action, _encode(receipt)))
        if cached:
            self._check_receipt(record, action, cached)
            if cached["status"] == "succeeded":
                self._verify(record)
            return cached
        try:
            packet = self._verify(record)
            result = self._result(packet, action)
            receipt.update(status="succeeded", result=result, evidence_sha256=_hash(result))
        except (DataError, ValueError, OSError, RuntimeError) as exc:
            receipt.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:2000])
        with self._connect() as connection:
            connection.execute(
                "UPDATE attempts SET receipt=? WHERE action=?", (_encode(receipt), action)
            )
        return receipt
