"""Test-only, diagnostic phase capture for an owner run by a test's own ``-c`` launcher script.

Records ``time.monotonic()`` (system-wide CLOCK_MONOTONIC, comparable with the test process)
around the owner's start-up calls: ``_Owner`` initialisation (which measures its runtime hash
inside the deadline window), control-socket bind, every control-store open, ``BEGIN`` and commit,
the claim, the cancellation read, the first deadline check, spawn and the no-spawn closure.
It wraps the calls without changing their arguments, results or exceptions, and only ever appends
to its own JSON-lines file. It never decides an outcome and is not production code.
"""

from __future__ import annotations

import functools
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

PHASES = "owner-phases.jsonl"


class _TimedConnection:
    """Delegates to a real sqlite3 connection, timing only BEGIN and commit."""

    def __init__(self, connection: Any, mark: Callable[..., None]) -> None:
        self._connection = connection
        self._mark = mark

    def execute(self, sql: str, *args: Any) -> Any:
        if not sql.startswith("BEGIN"):
            return self._connection.execute(sql, *args)
        self._mark("sqlite_begin_enter", sql=sql)
        try:
            return self._connection.execute(sql, *args)
        finally:
            self._mark("sqlite_begin_exit", sql=sql)

    def commit(self) -> None:
        self._mark("sqlite_commit_enter")
        try:
            self._connection.commit()
        finally:
            self._mark("sqlite_commit_exit")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


def install(root: Path, *, script_start: float) -> None:
    """Install the timing wrappers in this owner process; call before ``_run_owner``."""
    from alpha_cli import native_supervisor
    from alpha_cli.control_store import ControlStore

    sink = (root / PHASES).open("a", buffering=1)

    def mark(phase: str, **extra: object) -> None:
        sink.write(json.dumps({"phase": phase, "t": time.monotonic(), **extra}) + "\n")

    sink.write(json.dumps({"phase": "script_start", "t": script_start}) + "\n")
    mark("supervisor_imported")

    def around(owner: Any, name: str, *, once: bool = False) -> None:
        original = getattr(owner, name)
        seen: list[bool] = []

        @functools.wraps(original)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if once and seen:
                return original(*args, **kwargs)
            seen.append(True)
            mark(f"{name}_enter")
            try:
                return original(*args, **kwargs)
            finally:
                mark(f"{name}_exit")

        setattr(owner, name, wrapper)

    owner_init = native_supervisor._Owner.__init__

    @functools.wraps(owner_init)
    def init(self: Any, *args: Any, **kwargs: Any) -> None:
        mark("owner_init_enter")
        owner_init(self, *args, **kwargs)
        # ``started`` opens the deadline window; the runtime hash follows it inside __init__.
        mark("owner_init_exit", started=self.started, deadline=self.deadline)

    native_supervisor._Owner.__init__ = init  # type: ignore[method-assign]
    for name in ("open_control", "spawn", "without_child"):
        around(native_supervisor._Owner, name)
    around(native_supervisor._Owner, "poll_stop", once=True)
    for name in ("claim_native_fixture", "job_cancellation_requested"):
        around(ControlStore, name)

    store_open = ControlStore._open

    @functools.wraps(store_open)
    def timed_open(self: Any) -> Any:
        mark("store_open_enter")
        try:
            return _TimedConnection(store_open(self), mark)
        finally:
            mark("store_open_exit")

    ControlStore._open = timed_open  # type: ignore[method-assign]


def read(root: Path) -> list[dict[str, object]] | None:
    """The captured phases, if this owner recorded any; diagnostic evidence only."""
    path = root / PHASES
    if not path.exists():
        return None
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# Prepended to a test's ``-c`` owner script; ``root`` must be defined before PHASE_INSTALL.
PHASE_PRELUDE = "import time as _phase_time\n_PHASE_T0 = _phase_time.monotonic()\n"
PHASE_INSTALL = (
    "from tests.unit._native_phase_capture import install as _install_phases\n"
    "_install_phases(root, script_start=_PHASE_T0)\n"
)
