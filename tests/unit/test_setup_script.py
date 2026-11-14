"""scripts/setup.sh: argument handling, step order and plain-English failures, with fake tools.

No network: uv, npm, npx, node and git are stand-ins that only record how they were called.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/setup.sh"
STUB = (
    f"#!{sys.executable}\n"
    + """import json, os, sys
from pathlib import Path
command = " ".join([Path(sys.argv[0]).name, *sys.argv[1:]])
if command == "git -C " + os.environ["CHECKOUT"] + " config --get core.hooksPath":
    hooks = os.environ.get("HOOKS_PATH", "")
    print(hooks)
    sys.exit(0 if hooks else 1)
with open(os.environ["SETUP_LOG"], "a") as log:
    log.write(json.dumps({"command": command, "cwd": os.getcwd(),
                          "browsers": os.environ.get("PLAYWRIGHT_BROWSERS_PATH")}) + "\\n")
if os.environ.get("FAIL_STEP") and command.startswith(os.environ["FAIL_STEP"]):
    print("fixture original failure", file=sys.stderr)
    sys.exit(23)
"""
)


class Run:
    def __init__(self, tmp_path: Path) -> None:
        self.checkout = tmp_path / "checkout with spaces"
        (self.checkout / "scripts").mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.checkout / "scripts/setup.sh")
        for folder in ("apps/alpha-web/frontend", "workers/qlib", "workers/literature"):
            (self.checkout / folder).mkdir(parents=True)
        (self.checkout / "scripts/setup_rdagent.sh").write_text(
            '#!/usr/bin/env bash\necho "$*" >>"$SETUP_LOG.rdagent"\n'
        )
        self.log = tmp_path / "setup.log"
        self.tools = tmp_path / "tools"
        self.tools.mkdir()
        self.basics = tmp_path / "basics"
        self.basics.mkdir()
        for name in ("bash", "sed", "dirname", "date", "env", "mkdir"):
            found = shutil.which(name)
            assert found
            (self.basics / name).symlink_to(found)
        for name in ("uv", "npm", "npx", "node", "git"):
            self.add_tool(name)

    def add_tool(self, name: str) -> None:
        (self.tools / name).write_text(STUB)
        (self.tools / name).chmod(0o755)

    def run(self, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
        environment = {
            "PATH": f"{self.tools}:{self.basics}",
            "HOME": str(self.checkout.parent / "home"),
            "SETUP_LOG": str(self.log),
            "CHECKOUT": str(self.checkout),
            **extra,
        }
        return subprocess.run(
            ["bash", str(self.checkout / "scripts/setup.sh"), *args],
            cwd=self.checkout.parent,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    def calls(self) -> list[dict[str, str]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def commands(self) -> list[str]:
        return [call["command"] for call in self.calls()]


@pytest.fixture()
def setup(tmp_path: Path) -> Run:
    return Run(tmp_path)


DEFAULT_COMMANDS = [
    "uv sync --locked",
    "npm ci",
    "npm run build",
    "npx --no-install playwright install chromium",
    "uv sync --locked",
    "uv sync --locked",
    "uv run python scripts/git_guard.py install",
]


def test_default_run_sets_up_everything_in_order_and_nothing_optional(setup: Run) -> None:
    result = setup.run()
    assert result.returncode == 0, result.stderr
    assert setup.commands() == DEFAULT_COMMANDS
    folders = [Path(call["cwd"]).relative_to(setup.checkout).as_posix() for call in setup.calls()]
    assert folders == [
        ".",
        "apps/alpha-web/frontend",
        "apps/alpha-web/frontend",
        "apps/alpha-web/frontend",
        "workers/qlib",
        "workers/literature",
        ".",
    ]
    assert not Path(f"{setup.log}.rdagent").exists()
    for line in (
        "Set up:",
        "+ root Python environment",
        "+ web app built",
        "Skipped:",
        "RD-Agent: not requested (add --with-rdagent)",
        "storage reserve: not requested",
        "Next: python3 scripts/gate.py doctor",
    ):
        assert line in result.stdout


def test_playwright_browser_goes_to_the_standard_cache_even_if_the_old_variable_is_set(
    setup: Run,
) -> None:
    result = setup.run(PLAYWRIGHT_BROWSERS_PATH="/home/old/runtime/browsers")
    assert result.returncode == 0, result.stderr
    install = next(c for c in setup.calls() if c["command"].startswith("npx"))
    assert install["browsers"] is None
    assert "PLAYWRIGHT_BROWSERS_PATH is set" in result.stdout


def test_hook_already_installed_is_skipped_and_the_rerun_is_quiet_about_it(setup: Run) -> None:
    result = setup.run(HOOKS_PATH=".githooks")
    assert result.returncode == 0, result.stderr
    assert setup.commands() == DEFAULT_COMMANDS[:-1]
    assert "git hook: already installed" in result.stdout


def test_dry_run_changes_nothing(setup: Run) -> None:
    result = setup.run("--dry-run", "--with-rdagent")
    assert result.returncode == 0
    assert setup.calls() == [] and not Path(f"{setup.log}.rdagent").exists()
    assert "Dry run: nothing was changed" in result.stdout
    assert "uv sync --locked" in result.stdout


@pytest.mark.parametrize(
    ("args", "expect"),
    [
        (["--with-rdagent"], ""),
        (["--with-stock-runtime"], "--with-stock-runtime"),
        (["--with-daily-container"], "--with-daily-container"),
        (["--with-factor-runtime"], "--with-factor-runtime"),
        (
            ["--with-stock-runtime", "--with-daily-container"],
            "--with-daily-container --with-stock-runtime",
        ),
    ],
)
def test_rdagent_options_are_passed_to_its_own_script(
    setup: Run, args: list[str], expect: str
) -> None:
    result = setup.run(*args)
    assert result.returncode == 0, result.stderr
    assert Path(f"{setup.log}.rdagent").read_text().strip() == expect
    assert "RD-Agent source and runtimes" in result.stdout


STORAGE_START = "uv run python scripts/storage_settings.py write --apply --data-dir "


def test_storage_reserve_runs_the_documented_command_for_the_named_folder(
    setup: Run, tmp_path: Path
) -> None:
    data = tmp_path / "owner data"
    result = setup.run("--data-dir", str(data), "--storage-reserve-gb", "10")
    assert result.returncode == 0, result.stderr
    command = setup.commands()[-1]
    assert command.startswith(f"{STORAGE_START}{data} --bulk-root {data}/bulk ")
    assert "--reserve-gb 10 --decided-by owner --decided-on " in command
    assert "ADR-0043" in command
    assert (data / "bulk").is_dir()
    assert "storage reserve 10 GB" in result.stdout


def test_existing_storage_settings_are_shown_never_rewritten(setup: Run, tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "crypto").mkdir(parents=True)
    (data / "crypto/storage-config.json").write_text("{}")
    result = setup.run(f"--data-dir={data}", "--storage-reserve-gb=12.5")
    assert result.returncode == 0, result.stderr
    assert (
        setup.commands()[-1] == f"uv run python scripts/storage_settings.py show --data-dir {data}"
    )
    assert not any("write" in command for command in setup.commands())
    assert "(kept)" in result.stdout


def test_storage_is_never_touched_without_the_flags(setup: Run) -> None:
    setup.run()
    assert not any("storage_settings" in command for command in setup.commands())


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--bogus"], "unknown option: --bogus"),
        (["--storage-reserve-gb", "10"], "needs --data-dir DIR"),
        (["--data-dir", "/home/x/data"], "only used together with --storage-reserve-gb"),
        (["--data-dir"], "--data-dir needs a folder"),
        (["--storage-reserve-gb"], "needs a number of gigabytes"),
        (["--data-dir", "relative/data", "--storage-reserve-gb", "10"], "must be an absolute path"),
        (["--data-dir", "/home/x/d", "--storage-reserve-gb", "ten"], "plain number of gigabytes"),
        (["--data-dir", "/home/x/d", "--storage-reserve-gb", "1.2.3"], "plain number of gigabytes"),
        (["--data-dir", "/home/x/d", "--storage-reserve-gb", ""], "plain number of gigabytes"),
    ],
)
def test_bad_arguments_stop_before_anything_runs(setup: Run, args: list[str], message: str) -> None:
    result = setup.run(*args)
    assert result.returncode == 2
    assert message in result.stderr
    assert "--help" in result.stderr
    assert setup.calls() == []


def test_help_lists_every_option_and_runs_nothing(setup: Run) -> None:
    result = setup.run("--help")
    assert result.returncode == 0 and setup.calls() == []
    for option in (
        "--with-rdagent",
        "--with-stock-runtime",
        "--with-daily-container",
        "--data-dir",
        "--storage-reserve-gb",
        "--dry-run",
    ):
        assert option in result.stdout


def test_a_failed_step_stops_with_a_plain_message_and_the_original_error(setup: Run) -> None:
    result = setup.run(FAIL_STEP="npm ci")
    assert result.returncode == 23
    assert "fixture original failure" in result.stderr
    assert "STOPPED while Web app: locked packages and build" in result.stderr
    assert "run scripts/setup.sh again" in result.stderr
    assert setup.commands() == ["uv sync --locked", "npm ci"]


@pytest.mark.parametrize(
    ("tool", "hint"),
    [("uv", "docs.astral.sh/uv"), ("npm", "Node.js"), ("git", "git")],
)
def test_a_missing_tool_is_named_before_anything_is_changed(
    setup: Run, tool: str, hint: str
) -> None:
    (setup.tools / tool).unlink()
    result = setup.run()
    assert result.returncode != 0
    assert f'missing tool "{tool}"' in result.stderr and hint in result.stderr
    assert setup.calls() == []


def test_the_script_has_no_sudo_and_never_reads_secrets_or_the_codex_folder() -> None:
    code = [
        line
        for line in SCRIPT.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    body = "\n".join(code)
    for forbidden in ("sudo", ".env", ".codex", "install-deps", "curl", "wget"):
        assert forbidden not in body, forbidden
    assert os.access(SCRIPT, os.X_OK)
