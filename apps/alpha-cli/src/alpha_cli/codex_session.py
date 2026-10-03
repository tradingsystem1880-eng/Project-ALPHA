"""Local advisory conversation journal; never a source of research authority."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import stat
import uuid
from pathlib import Path
from types import TracebackType
from typing import Any

_STATE = "codex-session.json"
_LIMIT = 1_048_576


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate session JSON field")
        result[key] = value
    return result


class Session:
    """One host owns a session lock; every reserved attempt consumes its fixed budget."""

    def __init__(self, case_path: Path, identity_sha256: str, model: str) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", identity_sha256) is None or not model.strip():
            raise ValueError("invalid session binding")
        self.path, self.identity, self.model = case_path, identity_sha256, model
        self._directory: int | None = None
        self._lock: int | None = None
        self._state: dict[str, Any] = {}
        self._active: int | None = None

    @property
    def state(self) -> dict[str, Any]:
        return copy.deepcopy(self._state)

    def _open(self, name: str, flags: int) -> int:
        if self._directory is None:
            raise ValueError("session is not open")
        fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=self._directory)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise ValueError("session files must be regular files")
        return fd

    def _read(self, name: str) -> dict[str, Any]:
        with os.fdopen(self._open(name, os.O_RDONLY), "rb") as source:
            raw = source.read(_LIMIT + 1)
        if len(raw) > _LIMIT:
            raise ValueError("session file exceeds size limit")
        value = json.loads(raw, object_pairs_hook=_unique)
        if not isinstance(value, dict):
            raise ValueError("session must contain an object")
        json.dumps(value, allow_nan=False)
        return value

    def _write(self, name: str, value: dict[str, Any], *, immutable: bool = False) -> None:
        raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
        if len(raw) > _LIMIT:
            raise ValueError("session file exceeds size limit")
        temporary = name if immutable else f".codex-session-{uuid.uuid4().hex}.tmp"
        with os.fdopen(self._open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as dest:
            dest.write(raw)
            dest.flush()
            os.fsync(dest.fileno())
        if not immutable:
            os.replace(temporary, name, src_dir_fd=self._directory, dst_dir_fd=self._directory)
        assert self._directory is not None
        os.fsync(self._directory)

    def __enter__(self) -> Session:
        if self._directory is not None:
            raise ValueError("session is already open")
        try:
            self._directory = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self._lock = self._open("codex-session.lock", os.O_RDWR | os.O_CREAT)
            try:
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("another session owner is active") from exc
            names = {name for name in os.listdir(self._directory) if name.startswith("codex-turn-")}
            try:
                self._state = self._read(_STATE)
            except FileNotFoundError:
                if names:
                    raise ValueError("session missing despite existing reservations") from None
                self._state = {
                    "schema_version": 1,
                    "identity_sha256": self.identity,
                    "model": self.model,
                    "max_turns": 4,
                    "thread_id": None,
                    "turns": [],
                    "latest_report": None,
                }
                self._write(_STATE, self._state)
            self._validate(names)
        except BaseException:
            self._release()
            raise
        return self

    def _validate(self, names: set[str]) -> None:
        state = self._state
        if (
            set(state)
            != {
                "schema_version",
                "identity_sha256",
                "model",
                "max_turns",
                "thread_id",
                "turns",
                "latest_report",
            }
            or type(state["schema_version"]) is not int
            or state["schema_version"] != 1
            or (type(state["max_turns"]) is not int or state["max_turns"] != 4)
        ):
            raise ValueError("invalid session schema or fixed budget")
        if state["identity_sha256"] != self.identity or state["model"] != self.model:
            raise ValueError("session binding changed")
        thread = state["thread_id"]
        if thread is not None and (not isinstance(thread, str) or not 1 <= len(thread) <= 256):
            raise ValueError("invalid session thread")
        turns = state["turns"]
        if not isinstance(turns, list) or len(turns) > 4:
            raise ValueError("invalid session turns or budget")
        if names != {f"codex-turn-{n}.json" for n in range(1, len(turns) + 1)}:
            raise ValueError("session reservation ledger mismatch")
        for number, turn in enumerate(turns, 1):
            if (
                not isinstance(turn, dict)
                or set(turn) != {"number", "status", "turn_id"}
                or type(turn["number"]) is not int
                or turn["number"] != number
                or not isinstance(turn["status"], str)
                or turn["status"]
                not in {"reserved", "running", "completed", "failed", "interrupted"}
            ):
                raise ValueError("invalid session turn")
            identity = turn["turn_id"]
            if identity is not None and (
                not isinstance(identity, str) or not 1 <= len(identity) <= 256
            ):
                raise ValueError("invalid turn identifier")
            if turn["status"] in {"running", "completed"} and (identity is None or thread is None):
                raise ValueError("dispatched turn lacks thread or turn identifier")
            if turn["status"] == "reserved" and identity is not None:
                raise ValueError("reserved turn already has a server identifier")
            if turn["status"] in {"reserved", "running"} and number != len(turns):
                raise ValueError("ambiguous attempt precedes another reservation")
            if self._read(f"codex-turn-{number}.json") != self._reservation(number):
                raise ValueError("session reservation binding mismatch")
        if state["latest_report"] is not None and not isinstance(state["latest_report"], dict):
            raise ValueError("invalid latest report")

    def _reservation(self, number: int) -> dict[str, Any]:
        return {"identity_sha256": self.identity, "model": self.model, "number": number}

    def bind_thread(self, thread_id: str) -> None:
        if not isinstance(thread_id, str) or not 1 <= len(thread_id) <= 256:
            raise ValueError("invalid thread identifier")
        if self._state["thread_id"] not in (None, thread_id):
            raise ValueError("session thread binding cannot change")
        self._state["thread_id"] = thread_id
        self._write(_STATE, self._state)

    def reserve_turn(self) -> int:
        turns = self._state["turns"]
        if turns and turns[-1]["status"] in {"reserved", "running"}:
            raise ValueError("ambiguous prior attempt; no automatic retry")
        number = len(turns) + 1
        if number > 4:
            raise ValueError("session turn budget exhausted")
        # Marker first: a crash before state publication fails closed rather than resetting budget.
        self._write(f"codex-turn-{number}.json", self._reservation(number), immutable=True)
        turns.append({"number": number, "status": "reserved", "turn_id": None})
        self._write(_STATE, self._state)
        self._active = number
        return number

    def start_turn(self, turn_id: str) -> None:
        turn = self._current()
        if turn["status"] != "reserved" or self._state["thread_id"] is None:
            raise ValueError("reserved attempt and bound thread required")
        if not isinstance(turn_id, str) or not 1 <= len(turn_id) <= 256:
            raise ValueError("invalid turn identifier")
        turn.update(status="running", turn_id=turn_id)
        self._write(_STATE, self._state)

    def _current(self) -> dict[str, Any]:
        if self._active is None or self._directory is None:
            raise ValueError("no locally reserved turn")
        turn: dict[str, Any] = self._state["turns"][self._active - 1]
        return turn

    def finish_turn(self, status: str, report: dict[str, Any] | None = None) -> None:
        turn = self._current()
        if status not in {"completed", "failed", "interrupted"}:
            raise ValueError("invalid terminal turn status")
        if status == "completed" and turn["status"] != "running":
            raise ValueError("only a dispatched turn can complete")
        if report is not None and not isinstance(report, dict):
            raise ValueError("report must be a JSON object")
        # Check serialization before changing state; arbitrary non-JSON model output fails loud.
        json.dumps(report, allow_nan=False)
        turn["status"] = status
        if report is not None:
            self._state["latest_report"] = copy.deepcopy(report)
        self._write(_STATE, self._state)
        self._active = None

    def _release(self) -> None:
        self._active = None
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None
        if self._directory is not None:
            os.close(self._directory)
            self._directory = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self._active is not None and self._current()["status"] == "running":
                self.finish_turn("interrupted")
        finally:
            self._release()
