"""CLI-owned advisory session journal, isolated from admitted research evidence."""

from __future__ import annotations

import fcntl
import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alpha_cli.assistant_context import assemble_context
from alpha_cli.assistant_contracts import AssistantContext, AssistantTurnRequest
from alpha_core import DataError


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _db(root: Path) -> sqlite3.Connection:
    directory = root / "assistant_advisory"
    directory.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(directory / "sessions.sqlite3", timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
    return conn


def _save(root: Path, session: dict[str, Any]) -> None:
    with _db(root) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions VALUES (?,?)",
            (session["session_id"], _canonical(session)),
        )


def create_session(root: Path, context: AssistantContext) -> dict[str, Any]:
    sources = assemble_context(context, root)
    body = {
        "session_id": uuid.uuid4().hex,
        "context": context.model_dump(mode="json"),
        "context_hash": _hash(sources),
        "authority": "none",
        "attachments": [
            {"ref": s["ref"], "label": s["label"], "content_hash": _hash(s["data"])}
            for s in sources
        ],
        "turns": [],
        "created_at": datetime.now(UTC).isoformat(),
    }
    _save(root, body)
    return body


def _load_session(root: Path, session_id: str) -> dict[str, Any]:
    with _db(root) as conn:
        row = conn.execute("SELECT body FROM sessions WHERE id=?", (session_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown assistant session")
    body: dict[str, Any] = json.loads(row[0])
    return body


def get_session(root: Path, session_id: str) -> dict[str, Any]:
    # Prepare the journal before opening its sibling lock on first use.
    with _db(root):
        pass
    with (root / "assistant_advisory" / "active.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return _load_session(root, session_id)
        # Read only AFTER acquiring the lock. A worker may have just committed its answer.
        body = _load_session(root, session_id)
        changed = False
        for turn in body["turns"]:
            if turn["status"] == "running":
                turn.update(
                    status="interrupted", error="Assistant process ended; retry explicitly."
                )
                changed = True
        if changed:
            _save(root, body)
        return body


def validate_answer(raw: dict[str, Any], refs: set[str]) -> dict[str, Any]:
    if set(raw) != {"text", "citations", "rule_draft"}:
        raise ValueError("Invalid assistant answer fields")
    if not isinstance(raw["text"], str) or not 1 <= len(raw["text"]) <= 20000:
        raise ValueError("Invalid assistant answer text")
    citations = raw["citations"]
    if not isinstance(citations, list) or any(
        not isinstance(ref, str) or ref not in refs for ref in citations
    ):
        raise ValueError("Unknown assistant citation")
    if raw["rule_draft"] is not None:
        from alpha_strategies.rules import rule_spec_from_json

        raw["rule_draft"] = rule_spec_from_json(json.dumps(raw["rule_draft"])).to_json()
    return raw


def run_turn(root: Path, session_id: str, request: AssistantTurnRequest) -> dict[str, Any]:
    from alpha_cli.assistant_runtime import infer

    session = get_session(root, session_id)
    with (root / "assistant_advisory" / "active.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("An assistant turn is already active; wait or cancel it.") from exc
        session = get_session(root, session_id)
        sources = assemble_context(AssistantContext.model_validate(session["context"]), root)
        if _hash(sources) != session["context_hash"]:
            raise ValueError("Attached context changed; create a new session before continuing.")
        if len(session["turns"]) >= 100:
            raise ValueError("Session has reached 100 turns; create a new session.")
        turn = {
            "turn_id": uuid.uuid4().hex,
            **request.model_dump(),
            "status": "running",
            "context_hash": session["context_hash"],
            "answer": None,
            "error": None,
        }
        session["turns"].append(turn)
        _save(root, session)
        try:
            answer = infer(request, sources, session["turns"][-5:-1], lock_fd=lock.fileno())
            if request.action != "draft_rules" and answer.get("rule_draft") is not None:
                raise ValueError("Rule drafts require the draft_rules action")
            turn.update(
                status="completed", answer=validate_answer(answer, {s["ref"] for s in sources})
            )
        except KeyboardInterrupt:
            turn.update(status="cancelled", error="Cancelled by owner.")
        except (ValueError, RuntimeError, OSError, DataError, TypeError) as exc:
            turn.update(status="failed", error=str(exc)[:2000])
        finally:
            _save(root, session)
        return session


def check_session(root: Path, session_id: str) -> dict[str, Any]:
    session = get_session(root, session_id)
    sources = assemble_context(AssistantContext.model_validate(session["context"]), root)
    if _hash(sources) != session["context_hash"]:
        raise ValueError(
            "Attached context changed; create a new session before using this proposal."
        )
    return {"valid": True, "context_hash": session["context_hash"]}
