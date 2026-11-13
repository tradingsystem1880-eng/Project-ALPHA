"""Public routing contracts only: subprocess stubs are never browser acceptance."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import run_frontend_browser_lanes as lanes

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "apps/alpha-web/frontend"


def test_only_three_explicit_handoffs_keep_existing_projects() -> None:
    source = (FRONTEND / "playwright.config.ts").read_text()
    for name in lanes.HANDOFFS:
        assert f"'**/{name}'" in source
    ignore = source.split("testIgnore: [", 1)[1].split("]", 1)[0]
    assert ignore.count("'**/") == 3
    assert "grepInvert: /@reference-only/" in source
    assert "...(perfBudgets ? {} : { grepInvert: /@perf-budget/ })" in source
    assert "dependencies: ['chromium-minimum', 'chromium-reference', 'chromium-wide']" in source
    assert source.count("name: 'chromium-") == 4
    for config, name in zip(
        ("risk-basis", "risk-live", "native-result"), lanes.HANDOFFS, strict=True
    ):
        assert f"testMatch: '{name}'" in (FRONTEND / f"playwright.{config}.config.ts").read_text()


def test_native_junit_requires_one_exact_executed_case(tmp_path: Path) -> None:
    report = tmp_path / "native.xml"
    report.write_text(junit())
    lanes.validate_native_report(report)


def junit(case: str | None = None, *, count: int = 1, **counts: int) -> str:
    case = (
        case
        if case is not None
        else (f'<testcase classname="{lanes.NATIVE_CLASS}" name="{lanes.NATIVE_METHOD}"/>')
    )
    attrs = " ".join(f'{key}="{counts.get(key, 0)}"' for key in ("errors", "failures", "skipped"))
    return f'<testsuites><testsuite tests="{count}" {attrs}>{case}</testsuite></testsuites>'


@pytest.mark.parametrize(
    "body",
    [
        "",
        "not XML",
        "<testsuites/>",
        junit("", count=0),
        junit(count=2),
        junit(skipped=1),
        junit(errors=1),
        junit(failures=1),
        junit('<testcase classname="other" name="other"/>'),
        junit().replace("/>", "><skipped/></testcase>"),
        junit().replace("/>", "><error/></testcase>"),
        junit().replace("/>", "><failure/></testcase>"),
        junit(
            f'<testcase classname="{lanes.NATIVE_CLASS}" name="{lanes.NATIVE_METHOD}"/>' * 2,
            count=2,
        ),
        junit(
            f'<testcase classname="{lanes.NATIVE_CLASS}" name="{lanes.NATIVE_METHOD}"/>' * 2,
            count=1,
        ),
        junit().replace(lanes.NATIVE_METHOD, "wrong_method"),
    ],
)
def test_bad_native_report_cannot_pass(tmp_path: Path, body: str) -> None:
    report = tmp_path / "native.xml"
    report.write_text(body)
    with pytest.raises((ValueError, OSError)):
        lanes.validate_native_report(report)


def test_missing_native_report_cannot_pass(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        lanes.validate_native_report(tmp_path / "missing.xml")


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "repo"
    frontend = root / "apps/alpha-web/frontend"
    source = tmp_path / "stock-source"
    (source / "rdagent").mkdir(parents=True)
    runtime = tmp_path / "stock-runtime"
    python = runtime / "venv/bin/python"
    for path in (
        python,
        runtime / "venv/pyvenv.cfg",
        runtime / "dependencies.lock.txt",
        frontend / "node_modules/@playwright/test/cli.js",
        frontend / "node_modules/vite/bin/vite.js",
        frontend / "e2e/fixtures/riskMetricBasis.json",
        root / "apps/alpha-web/src/alpha_web/static/app/index.html",
        root / "scripts/run_owned_test.py",
        root / ".venv/bin/python",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic presence metadata only")
    python.chmod(0o700)
    (root / ".venv/bin/python").chmod(0o700)
    cache = tmp_path / "browsers"
    cache.mkdir()
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, **_: (
            f"/installed/{name}"
            if os.sep not in name
            else (name if os.access(name, os.X_OK) else None)
        ),
    )
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(sys, "platform", "linux")
    return root, {
        "ALPHA_RDAGENT_SOURCE": str(source),
        "ALPHA_STOCK_PYTHON": str(python),
        "PLAYWRIGHT_BROWSERS_PATH": str(cache),
        "PATH": "/installed",
    }


@pytest.mark.parametrize("key", ["ALPHA_RDAGENT_SOURCE", "ALPHA_STOCK_PYTHON"])
@pytest.mark.parametrize("value", [None, "", " "])
def test_one_missing_native_selector_fails_before_children(
    installed: tuple[Path, dict[str, str]],
    key: str,
    value: str | None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, env = installed
    if value is None:
        env.pop(key)
    else:
        env[key] = value
    monkeypatch.setattr(lanes, "run_child", lambda *args: pytest.fail("must not start child"))
    with pytest.raises(ValueError, match=key):
        lanes.run(root, env, tmp_path)
    summary = json.loads(next(tmp_path.glob("alpha-browser-lanes-*/summary.json")).read_text())
    assert summary["status"] == "failed" and summary["completed_lanes"] == []


@pytest.mark.parametrize("missing", ["venv/bin/python", "dependencies.lock.txt", "venv/pyvenv.cfg"])
def test_missing_native_runtime_files(
    installed: tuple[Path, dict[str, str]],
    missing: str,
) -> None:
    root, env = installed
    (Path(env["ALPHA_STOCK_PYTHON"]).parents[2] / missing).unlink()
    with pytest.raises(ValueError, match="Required installed input"):
        lanes.prerequisites(root, env)


@pytest.mark.parametrize(
    "missing",
    [
        "node_modules/@playwright/test/cli.js",
        "node_modules/vite/bin/vite.js",
        "e2e/fixtures/riskMetricBasis.json",
    ],
)
def test_missing_frontend_prerequisite(
    installed: tuple[Path, dict[str, str]],
    missing: str,
) -> None:
    root, env = installed
    (root / "apps/alpha-web/frontend" / missing).unlink()
    with pytest.raises(ValueError, match="Required installed input"):
        lanes.prerequisites(root, env)


@pytest.mark.parametrize("name", ["node", "uv", "python", "alpha"])
def test_missing_command(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    root, env = installed
    monkeypatch.setattr(shutil, "which", lambda item, **_: None if item == name else item)
    with pytest.raises(ValueError, match=name):
        lanes.prerequisites(root, env)


@pytest.mark.parametrize(
    "name", ["pytest", "polars", "starlette", "uvicorn", "alpha_cli", "alpha_web"]
)
def test_missing_controller_module(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    root, env = installed
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda item: None if item == name else object()
    )
    with pytest.raises(ValueError, match=name):
        lanes.prerequisites(root, env)


def test_non_linux_and_bad_browser_cache_fail(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, env = installed
    env["PLAYWRIGHT_BROWSERS_PATH"] = "relative-or-missing"
    with pytest.raises(ValueError, match="PLAYWRIGHT_BROWSERS_PATH"):
        lanes.prerequisites(root, env)
    monkeypatch.setattr(sys, "platform", "darwin")
    with pytest.raises(ValueError, match="Linux"):
        lanes.prerequisites(root, env)


def test_preserve_native_lexical_selector_and_bind_current_source(
    installed: tuple[Path, dict[str, str]],
) -> None:
    root, env = installed
    python = Path(env["ALPHA_STOCK_PYTHON"])
    python.unlink()
    python.symlink_to(Path(sys.executable))
    inherited = {
        **env,
        "PYTHONPATH": "/old/source",
        "PYTEST_ADDOPTS": "-k nothing",
        "ALPHA_NATIVE_WEB_EVIDENCE": "/old/receipt",
        "C04_RISK_LIVE_ROOT": "/old/live",
    }
    actual = lanes.prerequisites(root, inherited)
    assert actual["ALPHA_STOCK_PYTHON"] == str(python)
    assert actual["ALPHA_RDAGENT_SOURCE"] == env["ALPHA_RDAGENT_SOURCE"]
    assert actual["PYTHONPATH"].split(os.pathsep)[:2] == [str(root), str(root / "scripts")]
    assert "/old/source" not in actual["PYTHONPATH"]
    assert actual["UV_NO_SYNC"] == "1" and actual["UV_OFFLINE"] == "1"
    assert actual["UV_PYTHON_DOWNLOADS"] == "never"
    assert not {"PYTEST_ADDOPTS", "ALPHA_NATIVE_WEB_EVIDENCE", "C04_RISK_LIVE_ROOT"} & actual.keys()
    assert inherited["ALPHA_NATIVE_WEB_EVIDENCE"] == "/old/receipt"


def browser_report(
    frontend: Path, config: str, file: str, *, listing: bool = False
) -> dict[str, object]:
    names = (
        [""]
        if config != "playwright.config.ts"
        else [
            "chromium-minimum",
            "chromium-reference",
            "chromium-wide",
            "chromium-reference-only",
        ]
    )
    return {
        "errors": [],
        "config": {
            "configFile": str(frontend / config),
            "projects": [{"name": name} for name in names],
            "rootDir": str(frontend / "e2e"),
        },
        "stats": {"unexpected": 0, "expected": 0 if listing else len(names), "flaky": 0},
        "suites": [
            {
                "specs": [
                    {
                        "file": file,
                        "id": "synthetic-id",
                        "tests": [
                            {
                                "projectName": name,
                                "results": [] if listing else [{"status": "passed"}],
                            }
                            for name in names
                        ],
                    }
                ]
            }
        ],
    }


def stub_children(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_at: int = -1,
    native_body: str | None = None,
) -> list[tuple[list[str], Path, dict[str, str]]]:
    calls: list[tuple[list[str], Path, dict[str, str]]] = []

    def child(command: list[str], cwd: Path, env: dict[str, str], log: Path, root: Path) -> None:
        calls.append((command, cwd, env.copy()))
        log.write_text("STUB ONLY: no browser or native execution\n")
        if len(calls) == fail_at:
            raise RuntimeError("controlled child failure")
        if "PLAYWRIGHT_JSON_OUTPUT_FILE" in env:
            config = Path(command[command.index("--config") + 1]).name
            file = {
                "playwright.config.ts": "retained-bar-production.spec.ts",
                "playwright.risk-basis.config.ts": lanes.HANDOFFS[0],
                "playwright.risk-live.config.ts": lanes.HANDOFFS[1],
            }[config]
            report = Path(env["PLAYWRIGHT_JSON_OUTPUT_FILE"])
            assert not report.exists()
            report.write_text(
                json.dumps(browser_report(cwd, config, file, listing="--list" in command))
            )
        if "pytest" in command:
            evidence = Path(env["ALPHA_NATIVE_WEB_EVIDENCE"])
            assert not evidence.exists()
            assert lanes.NATIVE_NODE in command
            report = Path(
                next(arg.split("=", 1)[1] for arg in command if arg.startswith("--junitxml="))
            )
            assert not report.exists()
            if native_body is not None:
                report.write_text(native_body)
            else:
                report.write_text(junit())

    monkeypatch.setattr(lanes, "run_child", child)
    return calls


def test_fixed_routes_fresh_paths_raw_build_and_honest_aggregation(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, env = installed
    calls = stub_children(monkeypatch)
    first = lanes.run(root, env, tmp_path)
    second = lanes.run(root, env, tmp_path)
    assert first != second
    assert len(calls) == 20  # two prereqs, three listings, three browsers, build, native per run
    for offset, directory in ((0, first), (10, second)):
        current = calls[offset : offset + 10]
        summary = json.loads((directory / "summary.json").read_text())
        assert summary["status"] == "passed"
        assert summary["completed_lanes"] == ["default", "risk-basis", "risk-live", "native"]
        assert all("--list" in cmd for cmd, _, _ in current[2:5])
        run_commands = [current[i][0] for i in (5, 6, 8)]
        assert [Path(cmd[cmd.index("--config") + 1]).name for cmd in run_commands] == [
            "playwright.config.ts",
            "playwright.risk-basis.config.ts",
            "playwright.risk-live.config.ts",
        ]
        assert all(
            not {
                "--project",
                "--grep",
                "--retries",
                "--workers",
                "--timeout",
                "--pass-with-no-tests",
            }
            & set(cmd)
            for cmd in run_commands
        )
        outputs = [cmd[cmd.index("--output") + 1] for cmd in run_commands]
        assert len(set(outputs)) == 3 and all(str(directory) in p for p in outputs)
        build = current[7][0]
        assert build[-3:] == ["build", "--outDir", str(directory / "risk-live/spa")]
        assert "normalize-build" not in " ".join(build)
        assert current[8][2]["C04_RISK_LIVE_ROOT"] == str(directory / "risk-live")
        native = current[9]
        assert native[0][1:5] == ["-m", "pytest", "-q", lanes.NATIVE_NODE]
        assert native[2]["ALPHA_STOCK_PYTHON"] == env["ALPHA_STOCK_PYTHON"]
        assert native[2]["ALPHA_RDAGENT_SOURCE"] == env["ALPHA_RDAGENT_SOURCE"]
        assert native[2]["ALPHA_NATIVE_WEB_EVIDENCE"] == str(directory / "native/evidence")
        assert "ALPHA_STOCK_RECEIPTS" not in native[2]


def test_provisioned_native_is_not_reported_skipped(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, env = installed
    stub_children(monkeypatch)
    directory = lanes.run(root, env, tmp_path)
    summary = json.loads((directory / "summary.json").read_text())
    assert "skipped_lanes" not in summary
    assert "native lane skipped" not in capsys.readouterr().out


def unprovision(env: dict[str, str], value: str | None) -> dict[str, str]:
    for key in lanes.NATIVE_SELECTORS:
        if value is None:
            env.pop(key)
        else:
            env[key] = value
    return env


@pytest.mark.parametrize("value", [None, "", " "])
def test_unprovisioned_native_runs_asset_free_lanes_and_reports_skip(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    value: str | None,
) -> None:
    root, env = installed
    unprovision(env, value)
    calls = stub_children(monkeypatch)
    directory = lanes.run(root, env, tmp_path)
    out = capsys.readouterr().out
    assert out.count(lanes.NATIVE_SKIPPED) == 1
    assert "native lane skipped: ALPHA_RDAGENT_SOURCE/ALPHA_STOCK_PYTHON not provisioned" in out
    assert len(calls) == 8  # browser prereq, three listings, three browsers, risk-live build
    assert not any("pytest" in cmd or "StockFixtureLaunch" in " ".join(cmd) for cmd, _, _ in calls)
    run_commands = [cmd for cmd, _, _ in calls if "--output" in cmd]
    assert [Path(cmd[cmd.index("--config") + 1]).name for cmd in run_commands] == [
        "playwright.config.ts",
        "playwright.risk-basis.config.ts",
        "playwright.risk-live.config.ts",
    ]
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["status"] == "passed"
    assert summary["completed_lanes"] == ["default", "risk-basis", "risk-live"]
    assert summary["skipped_lanes"] == {"native": lanes.NATIVE_SKIPPED}
    assert not (directory / "native").exists()


def test_unprovisioned_native_skips_only_native_inputs(
    installed: tuple[Path, dict[str, str]],
) -> None:
    root, env = installed
    runtime = Path(env["ALPHA_STOCK_PYTHON"]).parents[2]
    unprovision(env, None)
    shutil.rmtree(runtime)
    assert (
        not {"ALPHA_RDAGENT_SOURCE", "ALPHA_STOCK_PYTHON"} & lanes.prerequisites(root, env).keys()
    )
    (root / "apps/alpha-web/frontend/node_modules/vite/bin/vite.js").unlink()
    with pytest.raises(ValueError, match="Required installed input"):
        lanes.prerequisites(root, env)


@pytest.mark.parametrize("fail_at", range(1, 9))
def test_unprovisioned_child_failure_prevents_aggregate_pass(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail_at: int,
) -> None:
    root, env = installed
    unprovision(env, "")
    calls = stub_children(monkeypatch, fail_at=fail_at)
    with pytest.raises(RuntimeError, match="controlled child failure"):
        lanes.run(root, env, tmp_path)
    assert len(calls) == fail_at
    summary = json.loads(next(tmp_path.glob("alpha-browser-lanes-*/summary.json")).read_text())
    assert summary["status"] == "failed" and "risk-live" not in summary["completed_lanes"]


@pytest.mark.parametrize("bad", ["relative/source", "/missing/source"])
def test_set_but_invalid_native_selector_still_fails(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bad: str,
) -> None:
    root, env = installed
    env["ALPHA_RDAGENT_SOURCE"] = bad
    monkeypatch.setattr(lanes, "run_child", lambda *args: pytest.fail("must not start child"))
    with pytest.raises(ValueError, match="ALPHA_RDAGENT_SOURCE must name"):
        lanes.run(root, env, tmp_path)


@pytest.mark.parametrize("fail_at", range(1, 11))
def test_every_child_failure_prevents_aggregate_pass(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail_at: int,
) -> None:
    root, env = installed
    calls = stub_children(monkeypatch, fail_at=fail_at)
    with pytest.raises(RuntimeError, match="controlled child failure"):
        lanes.run(root, env, tmp_path)
    assert len(calls) == fail_at
    summary = json.loads(next(tmp_path.glob("alpha-browser-lanes-*/summary.json")).read_text())
    assert summary["status"] == "failed" and "native" not in summary["completed_lanes"]


def test_skipped_native_exit_zero_is_not_success(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, env = installed
    stub_children(monkeypatch, native_body=junit(skipped=1))
    with pytest.raises(ValueError, match="exactly one"):
        lanes.run(root, env, tmp_path)
    summary = json.loads(next(tmp_path.glob("alpha-browser-lanes-*/summary.json")).read_text())
    assert summary["status"] == "failed"
    assert summary["completed_lanes"] == ["default", "risk-basis", "risk-live"]


@pytest.mark.parametrize(
    "bad",
    [
        "missing",
        "empty",
        "invalid",
        "zero",
        "wrong-config",
        "wrong-file",
        "error",
        "failed",
        "not-executed",
    ],
)
def test_browser_report_rejections(tmp_path: Path, bad: str) -> None:
    frontend = tmp_path / "frontend"
    report = tmp_path / "report.json"
    body = browser_report(frontend, "playwright.risk-basis.config.ts", lanes.HANDOFFS[0])
    if bad == "missing":
        pass
    elif bad in {"empty", "invalid"}:
        report.write_text("" if bad == "empty" else "bad JSON")
    else:
        if bad == "zero":
            body["suites"] = []
        elif bad == "wrong-config":
            body["config"] = {"configFile": "wrong"}
        elif bad == "wrong-file":
            body = browser_report(frontend, "playwright.risk-basis.config.ts", lanes.HANDOFFS[1])
        elif bad == "error":
            body["errors"] = ["collection error"]
        elif bad == "failed":
            body["stats"] = {"unexpected": 1, "expected": 0, "flaky": 0}
        elif bad == "not-executed":
            body = browser_report(
                frontend, "playwright.risk-basis.config.ts", lanes.HANDOFFS[0], listing=True
            )
        report.write_text(json.dumps(body))
    with pytest.raises((ValueError, OSError)):
        lanes.validate_browser_report(
            report, frontend, "playwright.risk-basis.config.ts", lanes.HANDOFFS[0]
        )


def test_listings_are_not_browser_passes_and_default_rejects_handoffs(tmp_path: Path) -> None:
    report = tmp_path / "selection.json"
    report.write_text(
        json.dumps(
            browser_report(tmp_path, "playwright.config.ts", lanes.HANDOFFS[0], listing=True)
        )
    )
    with pytest.raises(ValueError, match="handoff"):
        lanes.validate_browser_report(report, tmp_path, "playwright.config.ts", None, listing=True)
    report.write_text(
        json.dumps(
            browser_report(tmp_path, "playwright.config.ts", "ordinary.spec.ts", listing=True)
        )
    )
    lanes.validate_browser_report(report, tmp_path, "playwright.config.ts", None, listing=True)
    with pytest.raises(ValueError, match="empty"):
        lanes.validate_browser_report(report, tmp_path, "playwright.config.ts", None)


def test_refuse_source_output_and_existing_child_logs(
    installed: tuple[Path, dict[str, str]],
    tmp_path: Path,
) -> None:
    root, env = installed
    with pytest.raises(ValueError, match="outside"):
        lanes.run(root, env, root)
    log = tmp_path / "old.log"
    log.write_text("old evidence")
    with pytest.raises(FileExistsError):
        lanes.run_child(["must-not-start"], root, env, log, root)
    assert log.read_text() == "old evidence"


@pytest.mark.parametrize("change", ["config-project", "selected-project", "root", "duplicate"])
def test_browser_selection_preserves_project_membership(tmp_path: Path, change: str) -> None:
    body = browser_report(tmp_path, "playwright.config.ts", "ordinary.spec.ts", listing=True)
    # Deserialize a concrete test payload without weakening production type checking.
    payload = json.loads(json.dumps(body))
    if change == "config-project":
        payload["config"]["projects"].pop()
    elif change == "selected-project":
        payload["suites"][0]["specs"][0]["tests"].pop()
    elif change == "root":
        payload["config"]["rootDir"] = "/old/source/e2e"
    else:
        payload["suites"][0]["specs"].append(payload["suites"][0]["specs"][0])
    report = tmp_path / "selection.json"
    report.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        lanes.validate_browser_report(report, tmp_path, "playwright.config.ts", None, listing=True)


def test_execution_omission_cannot_match_listing(
    installed: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, env = installed
    stub_children(monkeypatch)
    original = lanes.run_child

    def changed(command: list[str], cwd: Path, env: dict[str, str], log: Path, root: Path) -> None:
        original(command, cwd, env, log, root)
        if "--list" in command:
            report = Path(env["PLAYWRIGHT_JSON_OUTPUT_FILE"])
            body = json.loads(report.read_text())
            other = json.loads(json.dumps(body["suites"][0]["specs"][0]))
            other["id"] = "additional-original-case"
            body["suites"][0]["specs"].append(other)
            report.write_text(json.dumps(body))

    monkeypatch.setattr(lanes, "run_child", changed)
    with pytest.raises(ValueError, match="differs from its fresh selection"):
        lanes.run(root, env, tmp_path)
    summary = json.loads(next(tmp_path.glob("alpha-browser-lanes-*/summary.json")).read_text())
    assert summary["completed_lanes"] == []
    assert summary["status"] == "failed"


def test_preexisting_performance_skips_and_retry_success_remain_valid(tmp_path: Path) -> None:
    body = json.loads(
        json.dumps(browser_report(tmp_path, "playwright.config.ts", "ordinary.spec.ts"))
    )
    body["stats"] = {"unexpected": 0, "expected": 0, "flaky": 1, "skipped": 1}
    tests = body["suites"][0]["specs"][0]["tests"]
    tests[0]["results"] = [{"status": "failed"}, {"status": "passed"}]
    tests[1]["results"] = [{"status": "skipped"}]
    report = tmp_path / "report.json"
    report.write_text(json.dumps(body))
    identities = lanes.validate_browser_report(report, tmp_path, "playwright.config.ts", None)
    assert len(identities) == 4


@pytest.mark.parametrize("status", [0, 2, -9])
def test_child_uses_existing_owner_and_propagates_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    calls: list[dict[str, object]] = []
    root = tmp_path / "repository with spaces"
    command = ["/installed/node with spaces", "/source/cli path.js", "test"]
    environment = {"PATH": "/installed", "SOURCE": "space in value"}

    def invoke(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, status)

    monkeypatch.setattr(subprocess, "run", invoke)
    log = tmp_path / "run.log"
    if status:
        with pytest.raises(RuntimeError, match=f"Child failed \\({status}\\)"):
            lanes.run_child(command, root, environment, log, root)
    else:
        lanes.run_child(command, root, environment, log, root)
    call = calls[0]
    assert call["argv"] == [sys.executable, str(root / "scripts/run_owned_test.py"), "--", *command]
    assert call["cwd"] == root and call["env"] == environment
    assert call["stdin"] == subprocess.DEVNULL
    assert call["stderr"] == subprocess.STDOUT and call["check"] is False
    assert "shell" not in call
    recorded = json.loads(log.read_text().splitlines()[0])
    assert recorded == {"argv": command, "cwd": str(root)}


def test_dispatcher_rejects_selection_arguments_before_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["run_frontend_browser_lanes.py", "e2e/specific.spec.ts"])
    monkeypatch.setattr(lanes, "run", lambda *args: pytest.fail("selector must fail before work"))
    with pytest.raises(SystemExit) as stopped:
        lanes.main()
    assert stopped.value.code == 2


def test_retained_interpreter_selector_is_checked_but_not_replaced(
    installed: tuple[Path, dict[str, str]],
) -> None:
    root, env = installed
    default = root / ".venv/bin/python"
    actual = lanes.prerequisites(root, env)
    assert "ALPHA_TEST_PYTHON" not in actual
    default.unlink()
    with pytest.raises(ValueError, match="Retained fixtures"):
        lanes.prerequisites(root, env)
    for value in ("", "/missing/fixture/python"):
        with pytest.raises(ValueError, match="Retained fixtures"):
            lanes.prerequisites(root, {**env, "ALPHA_TEST_PYTHON": value})
    explicit = {**env, "ALPHA_TEST_PYTHON": sys.executable}
    assert lanes.prerequisites(root, explicit)["ALPHA_TEST_PYTHON"] == sys.executable
    relative = root / "relative/bin/python"
    relative.parent.mkdir(parents=True)
    relative.write_text("test executable presence only")
    relative.chmod(0o700)
    for selector in ("relative/bin/python", "python"):
        selected = {**env, "ALPHA_TEST_PYTHON": selector}
        assert lanes.prerequisites(root, selected)["ALPHA_TEST_PYTHON"] == selector
