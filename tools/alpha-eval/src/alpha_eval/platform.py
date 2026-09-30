"""Subprocess seam to the platform: the `alpha` CLI and the world builder.

The benchmark never imports alpha_*. Every call pins ALPHA_DATA_DIR/ALPHA_BULK_DATA_DIR to the
sandbox and runs with cwd = sandbox so the repository's `.env` is never read.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RUN_TOKEN = re.compile(r"-> run ([0-9a-f]{16})")
_TOOL_ROOT = Path(__file__).resolve().parents[2]


def tool_root() -> Path:
    return _TOOL_ROOT


def repo_root() -> Path:
    return _TOOL_ROOT.parents[1]


def alpha_bin() -> Path:
    path = repo_root() / ".venv" / "bin" / "alpha"
    if not path.exists():
        raise FileNotFoundError(f"platform CLI not installed at {path}; run `uv sync` at the repo")
    return path


def sandbox_env(sandbox: Path, workspace: Path | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ALPHA_")}
    env["ALPHA_DATA_DIR"] = str(sandbox)
    env["ALPHA_BULK_DATA_DIR"] = str(sandbox / "bulk")
    env["PATH"] = f"{(workspace or repo_root()) / '.venv' / 'bin'}:{env.get('PATH', '')}"
    return env


@dataclass(frozen=True)
class CliResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    seconds: float

    @property
    def run_id(self) -> str | None:
        match = RUN_TOKEN.search(self.stdout)
        return match.group(1) if match else None

    def json(self) -> Any:
        return json.loads(self.stdout)


def run_alpha(
    sandbox: Path, argv: list[str], timeout: float = 900.0, *, workspace: Path | None = None
) -> CliResult:
    start = time.monotonic()
    proc = subprocess.run(
        [str(workspace / ".venv/bin/alpha" if workspace else alpha_bin()), *argv],
        cwd=sandbox,
        env=sandbox_env(sandbox, workspace),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CliResult(argv, proc.returncode, proc.stdout, proc.stderr, time.monotonic() - start)


def _platform_python(
    script: str, args: list[str], cwd: Path, timeout: float, workspace: Path | None = None
) -> str:
    proc = subprocess.run(
        [str(workspace / ".venv/bin/python"), script, *args]
        if workspace
        else ["uv", "run", "--project", str(repo_root()), "python", script, *args],
        cwd=cwd,
        env={k: v for k, v in os.environ.items() if not k.startswith("ALPHA_")},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{script} {args[:1]} failed:\n{proc.stderr[-4000:]}")
    return proc.stdout


def build_world(
    spec: dict[str, Any],
    sandbox: Path,
    truth_out: Path,
    seed: int,
    timeout: float = 600.0,
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Build a world into `sandbox` (market data only); truth goes to `truth_out` (outside)."""
    sandbox.mkdir(parents=True, exist_ok=True)
    spec_path = truth_out.with_suffix(".spec.json")
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    _platform_python(
        str(tool_root() / "worlds" / "build.py"),
        [
            "build",
            "--spec",
            str(spec_path),
            "--out",
            str(sandbox),
            "--truth-out",
            str(truth_out),
            "--seed",
            str(seed),
        ],
        cwd=truth_out.parent,
        timeout=timeout,
        workspace=workspace,
    )
    truth: dict[str, Any] = json.loads(truth_out.read_text(encoding="utf-8"))
    return truth


def analyze_run(run_dir: Path, market_bars: Path | None = None) -> dict[str, Any]:
    """Independent statistics on a run's equity curve (top-k concentration, beta)."""
    args = ["analyze", "--run-dir", str(run_dir)]
    if market_bars is not None:
        args += ["--market-bars", str(market_bars)]
    out = _platform_python(
        str(tool_root() / "worlds" / "build.py"), args, cwd=run_dir, timeout=300.0
    )
    result: dict[str, Any] = json.loads(out)
    return result


def read_manifest(sandbox: Path, run_id: str, kind: str = "runs") -> dict[str, Any]:
    path = sandbox / kind / run_id / "manifest.json"
    manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return manifest
