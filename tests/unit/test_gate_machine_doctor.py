"""The doctor's plain-English section: can this machine do synthetic-data development?

Everything runs against a throwaway tree with fake probes: no Docker, Codex, network or real
browser is touched.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import namedtuple
from pathlib import Path
from typing import Any

import gate
import pytest

ROOT = Path(__file__).resolve().parents[2]
DIGEST = "sha256:" + "a" * 64
IMAGE = "sha256:" + "b" * 64
Disk = namedtuple("Disk", "total used free")
GB = 1_000_000_000

REQUIRED = [
    "Root Python environment",
    "Built web app",
    "Browser for the web app's tests (Playwright Chromium)",
    "Qlib worker environment",
    "Literature worker environment",
]
OPTIONAL = [
    "RD-Agent source (pinned)",
    "RD-Agent rule and economics environments",
    "RD-Agent stock runtime (Python 3.11)",
    "Docker",
    "Daily-study Docker image (pinned)",
    "Codex CLI, signed in",
    "Free disk space above the storage reserve",
]


def touch(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    """A checkout with every item present."""
    root = tmp_path / "checkout"
    touch(root / ".venv/bin/python")
    touch(root / gate._WEB_BUNDLE, "<html></html>")
    touch(
        root / "apps/alpha-web/frontend/node_modules/playwright-core/browsers.json",
        json.dumps(
            {
                "browsers": [
                    {"name": "chromium", "revision": "1228"},
                    {"name": "chromium-headless-shell", "revision": "1228"},
                    {"name": "firefox", "revision": "9"},
                ]
            }
        ),
    )
    for folder in ("chromium-1228", "chromium_headless_shell-1228"):
        (tmp_path / "home/.cache/ms-playwright" / folder).mkdir(parents=True)
    touch(root / "workers/qlib/.venv/bin/python")
    touch(root / "workers/literature/.venv/bin/python")
    (root / ".alpha/state/runtime/rdagent-source/rdagent").mkdir(parents=True)
    touch(root / ".alpha/state/runtime/rdagent-stock-py311/venv/bin/python")
    for profile in (".venv-rule-qualified", ".venv-economics-qualified"):
        touch(root / "workers/rdagent" / profile / "bin/python")
    touch(
        root / "scripts/setup_rdagent.sh",
        f"daily_digest={DIGEST}\ndaily_image={IMAGE}\n",
    )
    return root


class Fakes:
    def __init__(self, tmp_path: Path) -> None:
        self.env = {"HOME": str(tmp_path / "home")}
        self.docker = True
        self.image_id = IMAGE
        self.alpha_cli = True
        self.calls: list[list[str]] = []
        self.codex = (True, "/bin/codex: Logged in using ChatGPT")
        self.free = 500 * GB

    def run(self, argv: list[str], cwd: Path) -> tuple[int, str]:
        self.calls.append(argv)
        if argv[0].endswith("/python"):
            return (0 if self.alpha_cli else 1, "")
        if argv[:2] == ["docker", "version"]:
            return (0, "29.1.3") if self.docker else (1, "Cannot connect to the Docker daemon")
        if argv[:3] == ["docker", "image", "inspect"]:
            return (0, self.image_id) if self.image_id else (1, "No such image")
        raise AssertionError(f"unexpected probe {argv}")

    def items(self, root: Path) -> dict[str, dict[str, Any]]:
        found = gate.machine_readiness(
            root,
            self.env,
            run=self.run,
            which=lambda name: "/usr/bin/docker" if self.docker else None,
            usage=lambda path: Disk(1000 * GB, 1000 * GB - self.free, self.free),
            codex=lambda: self.codex,
        )
        return {item["name"]: item for item in found}


@pytest.fixture()
def fakes(tmp_path: Path) -> Fakes:
    return Fakes(tmp_path)


def test_everything_present(tree: Path, fakes: Fakes) -> None:
    items = fakes.items(tree)
    assert list(items) == REQUIRED + OPTIONAL
    assert all(item["status"] == "present" and item["fix"] == "" for item in items.values())
    assert [item["required"] for item in items.values()] == [True] * 5 + [False] * 7
    assert gate.machine_summary(list(items.values()), {})["ready"] is True


@pytest.mark.parametrize(
    ("name", "remove", "fix"),
    [
        ("Root Python environment", ".venv/bin/python", "uv sync --locked"),
        (
            "Built web app",
            str(gate._WEB_BUNDLE),
            "cd apps/alpha-web/frontend && npm ci && npm run build",
        ),
        (
            "Browser for the web app's tests (Playwright Chromium)",
            "apps/alpha-web/frontend/node_modules/playwright-core/browsers.json",
            "cd apps/alpha-web/frontend && npm ci && npx --no-install playwright install chromium",
        ),
        (
            "Qlib worker environment",
            "workers/qlib/.venv/bin/python",
            "cd workers/qlib && uv sync --locked",
        ),
        (
            "Literature worker environment",
            "workers/literature/.venv/bin/python",
            "cd workers/literature && uv sync --locked",
        ),
    ],
)
def test_a_missing_required_item_names_its_fix_and_fails_the_doctor(
    tree: Path, fakes: Fakes, name: str, remove: str, fix: str
) -> None:
    (tree / remove).unlink()
    item = fakes.items(tree)[name]
    assert (item["status"], item["fix"], item["required"]) == ("missing", fix, True)
    summary = gate.machine_summary(list(fakes.items(tree).values()), {})
    assert summary["ready"] is False and summary["missing_required"] == [name]


def test_root_environment_without_the_alpha_packages_is_missing(tree: Path, fakes: Fakes) -> None:
    fakes.alpha_cli = False
    assert fakes.items(tree)["Root Python environment"]["status"] == "missing"


def test_missing_optional_items_do_not_make_the_machine_not_ready(tree: Path, fakes: Fakes) -> None:
    shutil.rmtree(tree / ".alpha")
    shutil.rmtree(tree / "workers/rdagent")
    fakes.docker = False
    fakes.codex = (False, "codex CLI not on PATH (second-model review unavailable)")
    fakes.free = 1 * GB
    items = fakes.items(tree)
    assert [n for n, i in items.items() if i["status"] == "missing"] == OPTIONAL
    summary = gate.machine_summary(list(items.values()), {})
    assert summary["ready"] is True and summary["missing_required"] == []
    fixes = {n: items[n]["fix"] for n in OPTIONAL}
    assert fixes["RD-Agent source (pinned)"] == "bash scripts/setup.sh --with-rdagent"
    assert fixes["RD-Agent stock runtime (Python 3.11)"].endswith("--with-stock-runtime")
    assert fixes["Codex CLI, signed in"].endswith("then run: codex login")
    assert "--storage-reserve-gb" in fixes["Free disk space above the storage reserve"]
    assert "needs Docker first" in items["Daily-study Docker image (pinned)"]["detail"]


def test_codex_installed_but_signed_out_says_to_log_in(tree: Path, fakes: Fakes) -> None:
    fakes.codex = (False, "codex present but not logged in: Not logged in")
    item = fakes.items(tree)["Codex CLI, signed in"]
    assert (item["status"], item["fix"]) == ("missing", "codex login")


def test_a_different_docker_image_is_not_the_pinned_one(tree: Path, fakes: Fakes) -> None:
    fakes.image_id = "sha256:" + "c" * 64
    item = fakes.items(tree)["Daily-study Docker image (pinned)"]
    assert item["status"] == "missing" and item["fix"].endswith("--with-daily-container")
    assert ["docker", "image", "inspect", "--format", "{{.Id}}", f"python@{DIGEST}"] in fakes.calls


def test_the_browser_must_be_the_pinned_revision_in_the_standard_cache(
    tree: Path, fakes: Fakes, tmp_path: Path
) -> None:
    shutil.rmtree(tmp_path / "home/.cache/ms-playwright/chromium_headless_shell-1228")
    detail = fakes.items(tree)["Browser for the web app's tests (Playwright Chromium)"]["detail"]
    assert "chromium_headless_shell-1228" in detail
    # An old, different cache is not used unless the owner points at it explicitly.
    old = tmp_path / "old-browsers"
    for folder in ("chromium-1228", "chromium_headless_shell-1228"):
        (old / folder).mkdir(parents=True)
    name = "Browser for the web app's tests (Playwright Chromium)"
    assert fakes.items(tree)[name]["status"] == "missing"
    fakes.env["PLAYWRIGHT_BROWSERS_PATH"] = str(old)
    assert fakes.items(tree)[name]["status"] == "present"
    fakes.env["XDG_CACHE_HOME"] = str(tmp_path / "xdg")
    del fakes.env["PLAYWRIGHT_BROWSERS_PATH"]
    assert fakes.items(tree)[name]["status"] == "missing"


def test_the_pinned_image_comes_from_the_rdagent_setup_script() -> None:
    pin = gate._daily_image_pin(ROOT)
    assert pin is not None
    text = (ROOT / gate.RDAGENT_SETUP_SCRIPT).read_text()
    assert pin[0] in text and pin[1] in text


class TestDoctorVerdict:
    def readiness(self, *, required_missing: bool) -> Any:
        def build(root: Path) -> list[dict[str, Any]]:
            return [
                gate._item("Needed", True, not required_missing, "d", "run-me"),
                gate._item("Nice to have", False, False, "d", "run-me-too"),
            ]

        return build

    @pytest.fixture(autouse=True)
    def _wired(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from tests.unit.test_claude_harness_gate import _wire_minimal_harness

        _wire_minimal_harness(repo)
        monkeypatch.delenv("CI", raising=False)

    def test_only_optional_missing_still_passes(self, repo: Path) -> None:
        code, report = gate.doctor(repo, readiness=self.readiness(required_missing=False))
        assert code == 0 and report["ok"] is True
        assert report["machine"]["ready"] is True
        assert report["machine"]["missing_optional"] == ["Nice to have"]

    def test_a_required_item_missing_fails(self, repo: Path) -> None:
        code, report = gate.doctor(repo, readiness=self.readiness(required_missing=True))
        assert code == 1 and report["ok"] is False
        assert all(check["ok"] for check in report["checks"]), "harness checks are unchanged"
        assert report["machine"]["missing_required"] == ["Needed"]

    def test_a_hosted_ci_runner_lists_but_does_not_enforce(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CI", "true")
        code, report = gate.doctor(repo, readiness=self.readiness(required_missing=True))
        assert code == 0 and report["machine"]["enforced"] is False

    def test_text_names_the_fix_and_the_one_command(self, repo: Path) -> None:
        _, report = gate.doctor(repo, readiness=self.readiness(required_missing=True))
        text = "\n".join(gate.format_machine_section(report["machine"]))
        assert "Can this machine do synthetic-data development?" in text
        assert "[MISSING] Needed (required)" in text and "fix: run-me" in text
        assert "One command fixes them all: bash scripts/setup.sh." in text
        assert "Optional items missing: Nice to have." in text

    def test_report_is_json_and_keeps_the_harness_schema(self, repo: Path) -> None:
        _, report = gate.doctor(repo, readiness=self.readiness(required_missing=False))
        again = json.loads(json.dumps(report))
        assert set(again) == {"created_at", "checks", "ok", "machine"}
        assert set(again["machine"]["items"][0]) == {
            "name",
            "required",
            "status",
            "detail",
            "fix",
        }


def test_the_real_command_prints_the_section_and_json_with_the_standard_library_only() -> None:
    command = [sys.executable, "-I", str(ROOT / "scripts/gate.py"), "doctor"]
    text = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert "Can this machine do synthetic-data development?" in text.stdout
    as_json = subprocess.run([*command, "--json"], cwd=ROOT, capture_output=True, text=True)
    report = json.loads(as_json.stdout)
    assert [i["name"] for i in report["machine"]["items"]] == REQUIRED + OPTIONAL
    assert as_json.returncode == text.returncode
