"""Fixed absolute-deadline container watchdog; scientific continuation stays in LoopBase."""

from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise ValueError("daily watchdog requires its fixed source and original deadline")
    source = Path(sys.argv[1])
    deadline = int(sys.argv[2])
    now = time.monotonic_ns()
    if not 0 < deadline - now <= 60_000_000_000 or source != source.resolve():
        raise ValueError("daily watchdog deadline/source is invalid or already expired")
    path = Path.cwd() / "daily-admission.json"
    if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("daily watchdog admission is unsafe")
    admission = json.loads(path.read_text())
    if (
        admission.get("schema") != "DailyNativeAdmissionV1"
        or admission.get("deadline_monotonic_ns") != deadline
        or Path.cwd().name != "payload-" + admission.get("job_id", "")
    ):
        raise ValueError("daily watchdog differs from original reserved deadline")
    stopped = False

    def stop(signum: int, frame: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    process = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-B",
            str(Path(__file__).with_name("fixture_entry.py")),
            str(source),
            "admitted",
            "@daily-admission.json",
        ],
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        while process.poll() is None:
            remaining = (deadline - time.monotonic_ns()) / 1_000_000_000
            if stopped or not math.isfinite(remaining) or remaining <= 0:
                return 124
            try:
                process.wait(timeout=min(remaining, 0.05))
            except subprocess.TimeoutExpired:
                continue
        return int(process.returncode)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
