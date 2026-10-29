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
# Ambient values must never reach the script under test (the full gate sets some of them).
FOUNDATION_VARS = {
    "ALPHA_CLOUD_FOUNDATION",
    "ALPHA_RDAGENT_PRISTINE",
    "ALPHA_RDAGENT_SOURCE",
    "ALPHA_RDAGENT_RETIRE_INTERRUPTED",
    "FAKE_PIN_REPO",
}


def expected_timeouts(steps: list[str]) -> list[str]:
    return [BOUNDED_COMMANDS[step] for step in steps if step in BOUNDED_COMMANDS]


def run_setup(
    tmp_path: Path, *, fail: str = "", overrides: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess[str], list[dict[str, object]], Path, list[str]]:
    root = tmp_path / "checkout with spaces"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "apps/alpha-web/frontend").mkdir(parents=True, exist_ok=True)
    script = root / "scripts/cloud_setup.sh"
    shutil.copyfile(Path(__file__).resolve().parents[2] / "scripts/cloud_setup.sh", script)
    binaries = tmp_path / "bin"
    binaries.mkdir(exist_ok=True)
    stub = (
        f"#!{sys.executable}\n"
        + """import json, os, sys
from pathlib import Path
command = " ".join([Path(sys.argv[0]).name, *sys.argv[1:]])
with open(os.environ["SETUP_LOG"], "a") as log:
    log.write(json.dumps({"command": command, "cwd": os.getcwd(),
                         "caches": {key: os.environ.get(key) for key in
                                    json.loads(os.environ["CACHE_KEYS"])}}) + "\\n")
if sys.argv[1:2] == ["venv"]:
    Path(sys.argv[-1]).mkdir(parents=True)
if "measure_rule_environment" in command and Path(
    f"workers/rdagent/.venv-{sys.argv[-1]}-qualified/invalid"
).exists():
    sys.exit(1)  # stands in for measure_rule_environment rejecting partial bytes
fail = os.environ["FAIL_STEP"]
if command == fail or (fail.startswith("*") and command.endswith(fail[1:])):
    print("fixture original failure: 403 cdn.playwright.dev", file=sys.stderr)
    sys.exit(23)
"""
    )
    for name in ("uv", "npm", "npx", "node"):
        executable = binaries / name
        executable.write_text(stub)
        executable.chmod(0o755)
    (root / ".venv/bin").mkdir(parents=True, exist_ok=True)
    (root / ".venv/bin/python").write_text(stub)
    (root / ".venv/bin/python").chmod(0o755)
    git_stub = binaries / "git"
    git_stub.write_text(
        f"#!{sys.executable}\n"
        + f"REAL = {shutil.which('git')!r}\n"
        + """import os, sys
args = sys.argv[1:]
fake = os.environ.get("FAKE_PIN_REPO")
if fake and args == ["-C", fake, "rev-parse", "HEAD"]:
    print("484776c211e4fbbeef03e0ec00d6bbee7362a4f4")
    sys.exit(0)
os.execv(REAL, [REAL, *args])
"""
    )
    git_stub.chmod(0o755)
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
    env = {
        key: value for key, value in os.environ.items() if key not in {*CACHES, *FOUNDATION_VARS}
    }
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


GUARD = "uv run --locked python -B scripts/git_guard.py install"
EXCLUDES = ["/workers/rdagent/.venv-rule-qualified/", "/workers/rdagent/.venv-economics-qualified/"]
IMAGE_RULE = Path("/etc/fonts/conf.d/56-prefer-inter.conf")


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
    }
    env["GIT_COMMITTER_EMAIL"] = "t@t"
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


def _checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    _git(root, "init", "--quiet")
    _git(root, "commit", "--quiet", "--allow-empty", "-m", "base")
    return root


def test_foundation_steps_are_opt_in_idempotent_and_never_fetch(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    opt_in = {"ALPHA_CLOUD_FOUNDATION": "1"}
    first, calls, _, _ = run_setup(tmp_path, overrides=opt_in)
    assert first.returncode == 0, first.stderr
    assert [call["command"] for call in calls] == [*STEPS, GUARD]
    assert "origin/main does not resolve; not fetched" in first.stdout
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    second, calls, _, _ = run_setup(tmp_path, overrides=opt_in)
    assert second.returncode == 0, second.stderr
    assert f"origin/main resolves to {_git(root, 'rev-parse', 'HEAD')}" in second.stdout
    exclude = (root / ".git/info/exclude").read_text().splitlines()
    assert [line for line in exclude if line in EXCLUDES] == EXCLUDES
    config = root / ".alpha/state/runtime/fontconfig/fonts.conf"
    if IMAGE_RULE.exists():
        assert f"export FONTCONFIG_FILE={config}" in second.stdout
        assert f"{config.parent}/conf.d</include>" in config.read_text()
        assert not (config.parent / "conf.d" / IMAGE_RULE.name).exists()
        assert len(list(config.parent.parent.iterdir())) == 1, "re-entry leaves no partial copies"
    else:
        assert "system fontconfig used unchanged" in second.stdout and not config.exists()
    assert "cloud-setup: ready" in second.stdout


def test_default_setup_runs_no_foundation_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in FOUNDATION_VARS:
        monkeypatch.setenv(name, "1" if name.startswith("ALPHA_CLOUD") else str(tmp_path / "x"))
    root = _checkout(tmp_path)
    result, calls, _, _ = run_setup(tmp_path)
    assert result.returncode == 0, result.stderr
    assert [call["command"] for call in calls] == STEPS
    assert not (root / ".alpha").exists()


@pytest.mark.skipif(not IMAGE_RULE.exists(), reason="image fontconfig rule absent on this host")
def test_drifted_fontconfig_fails_loud_without_replacing_it(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    config = root / ".alpha/state/runtime/fontconfig/fonts.conf"
    assert run_setup(tmp_path, overrides={"ALPHA_CLOUD_FOUNDATION": "1"})[0].returncode == 0
    config.write_text("drifted")
    result = run_setup(tmp_path, overrides={"ALPHA_CLOUD_FOUNDATION": "1"})[0]
    assert result.returncode != 0
    assert "differs from the verified recipe; inspect it, nothing replaced" in result.stderr
    assert config.read_text() == "drifted"
    assert "cloud-setup: ready" not in result.stdout


PIN = "484776c211e4fbbeef03e0ec00d6bbee7362a4f4"
VALIDATE = 'measure_rule_environment(sys.argv[1] == "economics")) '


def _pristine(tmp_path: Path) -> Path:
    pristine = tmp_path / "pristine"
    (pristine / "rdagent").mkdir(parents=True)
    (pristine / "rdagent/__init__.py").write_text("")
    (pristine / "LICENSE").write_text("license")
    (pristine / "pyproject.toml").write_text("[project]")
    (pristine / "test").mkdir()
    (pristine / "test/__init__.py").write_text("")
    _git(pristine, "init", "--quiet")
    _git(pristine, "add", "-A")
    _git(pristine, "commit", "--quiet", "-m", "stands in for the pin")
    return pristine


def _rdagent(tmp_path: Path, **extra: str) -> dict[str, str]:
    return {
        "ALPHA_CLOUD_FOUNDATION": "1",
        "ALPHA_RDAGENT_PRISTINE": str(tmp_path / "pristine"),
        "ALPHA_RDAGENT_SOURCE": str(tmp_path / "derived"),
        "FAKE_PIN_REPO": str(tmp_path / "pristine"),
        **extra,
    }


def _commands(calls: list[dict[str, object]], start: int = len(STEPS) + 1) -> list[str]:
    return [str(call["command"]) for call in calls][start:]


def _build(profile: str) -> list[str]:
    venv = f"workers/rdagent/.venv-{profile}-qualified"
    flag = " --economics" if profile == "economics" else ""
    return [
        f"uv venv --python 3.12 {venv}",
        f"uv pip install --python {venv}/bin/python --require-hashes --no-deps "
        f"-r workers/rdagent/{profile}-requirements.lock",
        f"python -B workers/rdagent/install_rule_profile.py{flag}",
    ]


def _validated(command: str, profile: str) -> bool:
    return command.endswith(VALIDATE + profile)


@pytest.mark.parametrize("problem", ["wrong_commit", "modified", "no_derived_root"])
def test_rdagent_requires_the_unmodified_pinned_checkout(tmp_path: Path, problem: str) -> None:
    _checkout(tmp_path)
    _pristine(tmp_path)
    overrides = _rdagent(tmp_path)
    if problem == "wrong_commit":
        del overrides["FAKE_PIN_REPO"]
    elif problem == "modified":  # HEAD reports the pin, so only the dirty-tree check can refuse
        (tmp_path / "pristine/rdagent/__init__.py").write_text("changed")
    else:
        del overrides["ALPHA_RDAGENT_SOURCE"]
    result, calls, _, _ = run_setup(tmp_path, overrides=overrides)
    assert result.returncode != 0
    expected = (
        "ALPHA_RDAGENT_SOURCE must name the derived RD-Agent root"
        if problem == "no_derived_root"
        else "is not the unmodified pinned commit"
    )
    assert expected in result.stderr
    assert [call["command"] for call in calls] == [*STEPS, GUARD]
    assert not (tmp_path / "derived").exists() and "cloud-setup: ready" not in result.stdout


def test_rdagent_builds_once_then_validates_existing_environments(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    _pristine(tmp_path)
    result, calls, _, _ = run_setup(tmp_path, overrides=_rdagent(tmp_path))
    assert result.returncode == 0, result.stderr
    commands = _commands(calls)
    assert "source_pin import verify_source" in commands[0]
    assert commands[1:4] == _build("rule") and _validated(commands[4], "rule")
    assert commands[5:8] == _build("economics") and _validated(commands[8], "economics")
    derived = tmp_path / "derived"
    assert sorted(path.name for path in derived.iterdir()) == [
        "LICENSE",
        "pyproject.toml",
        "rdagent",
    ]
    assert not list(tmp_path.glob("derived.partial.*"))
    runtime = root / ".alpha/state/runtime"
    assert not list(runtime.glob("*.incomplete"))
    assert {path.name.rsplit("-", 1)[0] for path in runtime.glob("rdagent-venv-*.built-*")} == {
        "rdagent-venv-rule.built",
        "rdagent-venv-economics.built",
    }
    again, calls, _, _ = run_setup(tmp_path, overrides=_rdagent(tmp_path))
    assert again.returncode == 0, again.stderr
    commands = _commands(calls, start=len(calls) - 3)
    assert "verify_source" in commands[0]
    assert _validated(commands[1], "rule") and _validated(commands[2], "economics")
    assert "cloud-setup: ready" in again.stdout


def test_existing_environment_that_fails_validation_is_left_untouched(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    _pristine(tmp_path)
    venv = root / "workers/rdagent/.venv-rule-qualified"
    venv.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("preserved")
    result, calls, _, _ = run_setup(
        tmp_path, fail="*" + VALIDATE + "rule", overrides=_rdagent(tmp_path)
    )
    assert result.returncode != 0 and "cloud-setup: ready" not in result.stdout
    assert not any(command.startswith("uv venv") for command in _commands(calls))
    assert (venv / "pyvenv.cfg").read_text() == "preserved"
    assert not (root / ".alpha/state/runtime/rdagent-venv-rule.incomplete").exists()


def test_interrupted_invalid_environment_is_preserved_until_explicitly_retired(
    tmp_path: Path,
) -> None:
    root = _checkout(tmp_path)
    _pristine(tmp_path)
    venv = root / "workers/rdagent/.venv-rule-qualified"
    marker = root / ".alpha/state/runtime/rdagent-venv-rule.incomplete"
    first, before, _, _ = run_setup(
        tmp_path, fail="*-r workers/rdagent/rule-requirements.lock", overrides=_rdagent(tmp_path)
    )
    assert first.returncode != 0 and marker.exists() and venv.is_dir()
    (venv / "partial-evidence").write_text("kept")
    (venv / "invalid").write_text("")
    refused, calls, _, _ = run_setup(tmp_path, overrides=_rdagent(tmp_path))
    assert refused.returncode != 0
    assert "setup was interrupted" in refused.stderr
    assert "ALPHA_RDAGENT_RETIRE_INTERRUPTED=1" in refused.stderr
    assert (venv / "partial-evidence").read_text() == "kept" and marker.exists()
    assert not any(command.startswith("uv venv") for command in _commands(calls, len(before)))
    retired = run_setup(
        tmp_path, overrides=_rdagent(tmp_path, ALPHA_RDAGENT_RETIRE_INTERRUPTED="1")
    )[0]
    assert retired.returncode == 0, retired.stderr
    [moved] = (root / ".alpha/state/runtime/interrupted").iterdir()
    assert (moved / "venv/partial-evidence").read_text() == "kept"
    assert (moved / "marker").read_text().startswith("build started ")
    assert venv.is_dir() and not (venv / "partial-evidence").exists() and not marker.exists()
    assert "not runnable" in retired.stdout and "cloud-setup: ready" in retired.stdout


def test_marked_environment_that_validates_is_never_moved(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    _pristine(tmp_path)
    venv = root / "workers/rdagent/.venv-rule-qualified"
    marker = root / ".alpha/state/runtime/rdagent-venv-rule.incomplete"
    first = run_setup(tmp_path, fail="*" + VALIDATE + "rule", overrides=_rdagent(tmp_path))[0]
    assert first.returncode != 0 and marker.exists()
    (venv / "built").write_text("kept")
    again = run_setup(tmp_path, overrides=_rdagent(tmp_path, ALPHA_RDAGENT_RETIRE_INTERRUPTED="1"))[
        0
    ]
    assert again.returncode == 0, again.stderr
    assert "validates despite an interrupted-build marker; kept in place" in again.stdout
    assert (venv / "built").read_text() == "kept" and not marker.exists()
    assert not (root / ".alpha/state/runtime/interrupted").exists()
    [record] = (root / ".alpha/state/runtime").glob("rdagent-venv-rule.built-*")
    assert "validated" in record.read_text()


@pytest.mark.parametrize("content", ["", "someone else's note\n", "build started x\nextra\n"])
def test_unowned_marker_fails_loud_and_moves_nothing(tmp_path: Path, content: str) -> None:
    root = _checkout(tmp_path)
    _pristine(tmp_path)
    venv = root / "workers/rdagent/.venv-rule-qualified"
    venv.mkdir(parents=True)
    (venv / "invalid").write_text("")
    marker = root / ".alpha/state/runtime/rdagent-venv-rule.incomplete"
    marker.parent.mkdir(parents=True)
    marker.write_text(content)
    result = run_setup(
        tmp_path, overrides=_rdagent(tmp_path, ALPHA_RDAGENT_RETIRE_INTERRUPTED="1")
    )[0]
    assert result.returncode != 0
    assert (
        "was not written by an interrupted build here; inspect it, nothing moved" in result.stderr
    )
    assert venv.is_dir() and marker.read_text() == content
    assert not (root / ".alpha/state/runtime/interrupted").exists()
