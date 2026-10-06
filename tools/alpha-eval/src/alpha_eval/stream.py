"""Bounded subprocess streaming that retains partial evidence on every exit path."""

from __future__ import annotations

import contextlib
import os
import queue
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any


def stream_process(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    seconds: float,
    raw: IO[str],
    consume: Callable[[str], bool],
) -> dict[str, Any]:
    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()
    errors: list[str] = []
    deadline = time.monotonic() + seconds
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    def read(pipe: IO[str], name: str) -> None:
        try:
            for line in pipe:
                lines.put((name, line))
        finally:
            lines.put((name, None))

    assert proc.stdout is not None and proc.stderr is not None
    threads = [
        threading.Thread(target=read, args=(pipe, name), daemon=True)
        for pipe, name in [(proc.stdout, "out"), (proc.stderr, "err")]
    ]
    for thread in threads:
        thread.start()
    stop = "completed"
    closed = 0
    try:
        while closed < 2:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop = "timeout"
                break
            try:
                name, line = lines.get(timeout=min(remaining, 0.2))
            except queue.Empty:
                continue
            if line is None:
                closed += 1
            elif name == "out":
                raw.write(line)
                raw.flush()
                if not consume(line):
                    stop = "tool_call_cap"
                    break
            else:
                errors.append(line)
                errors[:] = errors[-50:]
    finally:
        # Kill the process group, including MCP/command children, on interrupted turns.
        if stop != "completed" or proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
        # A parent can exit while a child ignores SIGTERM. Reap the entire group.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        for thread in threads:
            thread.join(timeout=1)
        while not lines.empty():
            name, line = lines.get_nowait()
            if line is not None and name == "out":
                raw.write(line)
                consume(line)
            elif line is not None:
                errors.append(line)
        raw.flush()
        proc.stdout.close()
        proc.stderr.close()
    if stop == "completed" and proc.returncode:
        stop = f"exit:{proc.returncode}"
    return {"stop": stop, "stderr_tail": "".join(errors)[-2000:], "returncode": proc.returncode}
