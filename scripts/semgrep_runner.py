"""Shared pinned and version-checked Semgrep invocation for repository tooling."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from typing import Any

SEMGREP_VERSION = "1.181.0"
_SEMGREP_COMMAND = ["uvx", "--from", f"semgrep=={SEMGREP_VERSION}", "semgrep"]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _output_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def combine_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    """Keep both streams readable when a caller needs one diagnostic string."""
    out, err = _output_text(stdout), _output_text(stderr)
    if out and err and not out.endswith(("\n", "\r")) and not err.startswith(("\n", "\r")):
        return f"{out}\n{err}"
    return f"{out}{err}"


def semgrep_command(arguments: Sequence[str]) -> list[str]:
    """Build the isolated uvx command with the exact Semgrep distribution pin."""
    return [*_SEMGREP_COMMAND, *arguments]


def run_semgrep(
    arguments: Sequence[str],
    *,
    runner: CommandRunner | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Verify the installed Semgrep version, then run the requested scan unchanged."""
    run = runner or subprocess.run
    command = semgrep_command(arguments)
    version_command = semgrep_command(["--version"])
    version_kwargs = {key: kwargs[key] for key in ("cwd", "env", "timeout") if key in kwargs}
    try:
        version_result = run(
            version_command,
            **version_kwargs,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            command, 127, "", f"OSError while checking Semgrep version: {exc}"
        )
    except subprocess.TimeoutExpired as exc:
        output = combine_output(exc.stdout, exc.stderr)
        return subprocess.CompletedProcess(
            command,
            124,
            "",
            f"TimeoutExpired while checking Semgrep version: {exc}\n{output}",
        )

    if version_result.returncode != 0:
        return subprocess.CompletedProcess(
            command,
            version_result.returncode,
            _output_text(version_result.stdout),
            _output_text(version_result.stderr),
        )

    probe_stdout = _output_text(version_result.stdout)
    probe_stderr = _output_text(version_result.stderr)
    actual_version = probe_stdout.strip()
    if actual_version != SEMGREP_VERSION:
        mismatch = (
            f"Semgrep version mismatch: expected {SEMGREP_VERSION}, "
            f"found {actual_version or 'empty output'}"
        )
        diagnostics = combine_output(probe_stdout, probe_stderr)
        details = f"{mismatch}\n{diagnostics}" if diagnostics else mismatch
        return subprocess.CompletedProcess(command, 2, "", details)

    scan_kwargs = {**kwargs, "check": False}
    try:
        scan_result = run(command, **scan_kwargs)
    except OSError as exc:
        return subprocess.CompletedProcess(
            command,
            127,
            "",
            combine_output(probe_stderr, f"OSError while running Semgrep: {exc}"),
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            124,
            "",
            combine_output(f"TimeoutExpired while running Semgrep: {exc}", probe_stderr),
        )

    if probe_stderr:
        return subprocess.CompletedProcess(
            scan_result.args,
            scan_result.returncode,
            _output_text(scan_result.stdout),
            combine_output(probe_stderr, scan_result.stderr),
        )
    return scan_result
