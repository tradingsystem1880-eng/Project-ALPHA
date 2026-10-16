"""Cloud provisioning keeps locked installs and exposes the original failure."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CACHES = {
    "UV_CACHE_DIR": "/tmp/project-alpha-uv-cache",
    "UV_TOOL_DIR": "/tmp/project-alpha-uv-tools",
    "UV_LINK_MODE": "copy",
    "XDG_CONFIG_HOME": "/tmp/project-alpha-xdg",
    "npm_config_cache": "/tmp/project-alpha-npm-cache",
    "PLAYWRIGHT_BROWSERS_PATH": "/tmp/project-alpha-playwright-browsers",
    "SEMGREP_VERSION_CACHE_PATH": "/tmp/project-alpha-semgrep/semgrep_version",
}
STEPS = [
    "uv sync --locked",
    "npm ci",
    "npx --no-install playwright install chromium",
    "uv run --locked alpha info",
    "node --input-type=module",
]
BOUNDED_COMMANDS = {STEPS[3]: "30s", STEPS[4]: "35s"}


def expected_timeouts(steps: list[str]) -> list[str]:
    return [BOUNDED_COMMANDS[step] for step in steps if step in BOUNDED_COMMANDS]


def run_setup(
    tmp_path: Path, *, fail: str = "", overrides: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess[str], list[dict[str, object]], Path, list[str]]:
    root = tmp_path / "checkout with spaces"
    (root / "scripts").mkdir(parents=True)
    (root / "apps/alpha-web/frontend").mkdir(parents=True)
    script = root / "scripts/cloud_setup.sh"
    shutil.copyfile(Path(__file__).resolve().parents[2] / "scripts/cloud_setup.sh", script)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    stub = (
        f"#!{sys.executable}\n"
        + """import json, os, sys
from pathlib import Path
command = " ".join([Path(sys.argv[0]).name, *sys.argv[1:]])
with open(os.environ["SETUP_LOG"], "a") as log:
    log.write(json.dumps({"command": command, "cwd": os.getcwd(),
                         "caches": {key: os.environ.get(key) for key in
                                    json.loads(os.environ["CACHE_KEYS"])}}) + "\\n")
if command == os.environ["FAIL_STEP"]:
    print("fixture original failure: 403 cdn.playwright.dev", file=sys.stderr)
    sys.exit(23)
"""
    )
    for name in ("uv", "npm", "npx", "node"):
        executable = binaries / name
        executable.write_text(stub)
        executable.chmod(0o755)
    timeout = binaries / "timeout"
    timeout.write_text(
        f"#!{sys.executable}\n"
        + """import json, os, sys
with open(os.environ["TIMEOUT_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1]) + "\\n")
os.execvp(sys.argv[2], sys.argv[2:])
"""
    )
    timeout.chmod(0o755)
    mkdir = binaries / "mkdir"
    mkdir.write_text(
        f"#!{sys.executable}\n"
        + """import os, sys
from pathlib import Path
root = Path(os.environ["ISOLATED_MKDIR_ROOT"])
args = sys.argv[1:]
if args and args[0] == "-p":
    args = args[1:]
for raw in args:
    path = Path(raw)
    if raw.startswith("/tmp/project-alpha-"):
        path = root / path.name
    path.mkdir(parents=True, exist_ok=True)
"""
    )
    mkdir.chmod(0o755)
    log = tmp_path / "commands.jsonl"
    timeout_log = tmp_path / "timeouts.jsonl"
    env = {key: value for key, value in os.environ.items() if key not in CACHES}
    env.update(overrides or {})
    env.update(
        PATH=f"{binaries}:{os.environ['PATH']}",
        SETUP_LOG=str(log),
        TIMEOUT_LOG=str(timeout_log),
        ISOLATED_MKDIR_ROOT=str(tmp_path / "isolated-defaults"),
        CACHE_KEYS=json.dumps(list(CACHES)),
        FAIL_STEP=fail,
    )
    result = subprocess.run(
        ["bash", str(script)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    timeouts = (
        [json.loads(line) for line in timeout_log.read_text().splitlines()]
        if timeout_log.exists()
        else []
    )
    return result, calls, root, timeouts


def test_setup_uses_locked_installs_and_exports_defaults(tmp_path: Path) -> None:
    result, calls, root, timeouts = run_setup(tmp_path)
    assert result.returncode == 0, result.stderr
    assert [call["command"] for call in calls] == STEPS
    assert all(call["caches"] == CACHES for call in calls)
    assert timeouts == ["30s", "35s"]
    isolated = tmp_path / "isolated-defaults"
    assert all(
        (isolated / Path(value).name).is_dir()
        for key, value in CACHES.items()
        if key not in {"UV_LINK_MODE", "SEMGREP_VERSION_CACHE_PATH"}
    )
    assert (isolated / "project-alpha-semgrep").is_dir()
    assert [call["cwd"] for call in calls] == [
        str(root),
        str(root / "apps/alpha-web/frontend"),
        str(root / "apps/alpha-web/frontend"),
        str(root),
        str(root / "apps/alpha-web/frontend"),
    ]
    assert "cloud-setup: ready" in result.stdout


@pytest.mark.parametrize("step", STEPS)
def test_setup_stops_and_preserves_original_failure(tmp_path: Path, step: str) -> None:
    result, calls, _, timeouts = run_setup(tmp_path, fail=step)
    assert result.returncode == 23
    assert [call["command"] for call in calls] == STEPS[: STEPS.index(step) + 1]
    assert timeouts == expected_timeouts(STEPS[: STEPS.index(step) + 1])
    assert "fixture original failure: 403 cdn.playwright.dev" in result.stderr
    assert "cloud-setup: FAILED" in result.stderr
    assert "exit 23" in result.stderr
    assert "cloud-setup: ready" not in result.stdout


def test_setup_preserves_configured_paths(tmp_path: Path) -> None:
    configured = {key: str(tmp_path / key) for key in CACHES if key != "UV_LINK_MODE"}
    configured["UV_LINK_MODE"] = "copy"
    configured["SEMGREP_VERSION_CACHE_PATH"] = str(tmp_path / "semgrep" / "version")
    result, calls, _, timeouts = run_setup(tmp_path, overrides=configured)
    assert result.returncode == 0, result.stderr
    assert all(call["caches"] == configured for call in calls)
    assert timeouts == ["30s", "35s"]
    assert all(
        Path(value).is_dir()
        for key, value in configured.items()
        if key not in {"UV_LINK_MODE", "SEMGREP_VERSION_CACHE_PATH"}
    )
    assert Path(configured["SEMGREP_VERSION_CACHE_PATH"]).parent.is_dir()


@pytest.mark.parametrize("cache", ["UV_CACHE_DIR", "SEMGREP_VERSION_CACHE_PATH"])
def test_unusable_cache_path_fails_before_install(tmp_path: Path, cache: str) -> None:
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    result, calls, _, timeouts = run_setup(tmp_path, overrides={cache: str(blocked / "cache")})
    assert result.returncode != 0
    assert calls == []
    assert timeouts == []
    assert "cloud-setup: FAILED" in result.stderr
