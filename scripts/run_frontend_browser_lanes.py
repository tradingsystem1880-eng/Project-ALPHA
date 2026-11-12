"""Run the four mandatory browser fixtures, without changing their test policies.

Requires already installed assets. Every run retains fresh evidence outside source;
failed prerequisites or a skipped native driver never count as aggregate success.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HANDOFFS = ("risk-metric-basis.spec.ts", "risk-live.spec.ts", "native-result-real.spec.ts")
NATIVE_CLASS = "tests.unit.test_native_result_web.NativeWebJourney"
NATIVE_METHOD = "test_built_spa_reads_native_owner_receipt_without_interception"
NATIVE_NODE = f"tests/unit/test_native_result_web.py::NativeWebJourney::{NATIVE_METHOD}"


def prerequisites(root: Path, inherited: dict[str, str]) -> dict[str, str]:
    """Presence checks only; the existing native validator measures the selected pins."""
    if sys.platform != "linux":
        raise ValueError("Browser lanes require Linux retained-child ownership")
    env = dict(inherited)
    for name in ("ALPHA_RDAGENT_SOURCE", "ALPHA_STOCK_PYTHON"):
        if not env.get(name, "").strip():
            raise ValueError(f"Required installed selector is missing or empty: {name}")
    source = Path(env["ALPHA_RDAGENT_SOURCE"])
    python = Path(env["ALPHA_STOCK_PYTHON"])
    if not source.is_absolute() or not (source / "rdagent").is_dir():
        raise ValueError("ALPHA_RDAGENT_SOURCE must name an existing absolute source root")
    if not python.is_absolute() or python.parts[-3:] != ("venv", "bin", "python"):
        raise ValueError("ALPHA_STOCK_PYTHON must name the installed runtime/venv/bin/python")
    runtime = python.parents[2]
    frontend = root / "apps/alpha-web/frontend"
    for path in (
        python,
        runtime / "dependencies.lock.txt",
        runtime / "venv/pyvenv.cfg",
        frontend / "node_modules/@playwright/test/cli.js",
        frontend / "node_modules/vite/bin/vite.js",
        frontend / "e2e/fixtures/riskMetricBasis.json",
        root / "apps/alpha-web/src/alpha_web/static/app/index.html",
        root / "scripts/run_owned_test.py",
    ):
        if not path.is_file():
            raise ValueError(f"Required installed input is absent: {path}")
    if not os.access(python, os.X_OK):
        raise ValueError(f"Native interpreter is not executable: {python}")
    # Direct Python and the existing configs' `python`, `alpha`, and `uv run python`
    # must resolve the current controller, never an older editable checkout.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", os.defpath)
    for name in ("node", "uv", "python", "alpha"):
        if not shutil.which(name, path=env["PATH"]):
            raise ValueError(f"Required installed executable is absent: {name}")
    # Retained specs own their interpreter choice independently of this controller.
    retained = env.get("ALPHA_TEST_PYTHON", str(root / ".venv/bin/python"))
    executable = (
        str(root / retained)
        if os.sep in retained and not Path(retained).is_absolute()
        else retained
    )
    if not retained or not shutil.which(executable, path=env["PATH"]):
        raise ValueError(
            "Retained fixtures require executable ALPHA_TEST_PYTHON or root/.venv/bin/python"
        )
    for name in ("pytest", "polars", "starlette", "uvicorn", "alpha_cli", "alpha_web"):
        if importlib.util.find_spec(name) is None:
            raise ValueError(f"Required controller module is absent: {name}")
    env["PYTHONPATH"] = os.pathsep.join(
        map(
            str,
            [
                root,
                root / "scripts",
                *sorted(root.glob("packages/*/src")),
                *sorted(root.glob("apps/*/src")),
            ],
        )
    )
    env["UV_PROJECT_ENVIRONMENT"] = sys.prefix
    env["UV_NO_SYNC"] = "1"
    env["UV_OFFLINE"] = "1"
    env["UV_PYTHON_DOWNLOADS"] = "never"
    # Native's existing browser owner changes HOME. Make the installed cache
    # explicit so all lanes use the same installation; never download a browser.
    cache = env.get("PLAYWRIGHT_BROWSERS_PATH")
    if not cache:
        cache = str(Path(env.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "ms-playwright")
    if cache != "0" and (not Path(cache).is_absolute() or not Path(cache).is_dir()):
        raise ValueError("PLAYWRIGHT_BROWSERS_PATH must name an existing absolute cache (or 0)")
    env["PLAYWRIGHT_BROWSERS_PATH"] = cache
    # No inherited fixture/evidence directory or pytest filter may weaken a lane.
    for key in (
        "ALPHA_NATIVE_WEB_FIXTURE",
        "ALPHA_NATIVE_WEB_EVIDENCE",
        "ALPHA_NATIVE_WEB_OUTPUT",
        "C04_RISK_LIVE_ROOT",
        "PYTEST_ADDOPTS",
        "PLAYWRIGHT_JSON_OUTPUT_NAME",
        "PLAYWRIGHT_JSON_OUTPUT_DIR",
        "PLAYWRIGHT_JSON_OUTPUT_FILE",
    ):
        env.pop(key, None)
    return env


def run_child(command: list[str], cwd: Path, env: dict[str, str], log: Path, root: Path) -> None:
    """Delegate descendant cleanup to the existing owner, retaining both streams."""
    with log.open("x") as stream:
        stream.write(json.dumps({"argv": command, "cwd": str(cwd)}) + "\n")
        stream.flush()
        completed = subprocess.run(
            [sys.executable, str(root / "scripts/run_owned_test.py"), "--", *command],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if completed.returncode:
        raise RuntimeError(f"Child failed ({completed.returncode}); retained log: {log}")


def validate_browser_report(
    path: Path, frontend: Path, config: str, file: str | None, *, listing: bool = False
) -> set[tuple[str, str, str]]:
    """Check handoff membership and actual execution, without changing skip/retry policy."""
    report = json.loads(path.read_text())
    if (
        report["errors"]
        or report["config"]["configFile"] != str(frontend / config)
        or (
            not listing
            and (
                report["stats"]["unexpected"] != 0
                or report["stats"]["expected"] + report["stats"]["flaky"] <= 0
            )
        )
    ):
        raise ValueError(f"Failed, empty or mismatched browser report: {path}")
    projects = {project["name"] for project in report["config"]["projects"]}
    expected_projects = (
        {""}
        if file
        else {
            "chromium-minimum",
            "chromium-reference",
            "chromium-wide",
            "chromium-reference-only",
        }
    )
    if projects != expected_projects or report["config"]["rootDir"] != str(frontend / "e2e"):
        raise ValueError("Browser config projects/root differ from the existing lanes")
    selected: set[str] = set()
    identities: set[tuple[str, str, str]] = set()
    executed = False

    def visit(suites: list[dict[str, Any]]) -> None:
        nonlocal executed
        for suite in suites:
            for spec in suite.get("specs", []):
                if not spec["tests"]:
                    raise ValueError("Browser spec has no configured project tests")
                selected.add(spec["file"])
                for test in spec["tests"]:
                    identity = (test["projectName"], spec["id"], spec["file"])
                    if not spec["id"] or identity in identities:
                        raise ValueError("Empty or duplicate browser case identity")
                    identities.add(identity)
                    executed |= any(result["status"] == "passed" for result in test["results"])
            visit(suite.get("suites", []))

    visit(report["suites"])
    if {item[0] for item in identities} != projects:
        raise ValueError("Browser selection omits a configured project")
    if (
        (not listing and not executed)
        or not selected
        or (file and selected != {file})
        or (file is None and selected.intersection(HANDOFFS))
    ):
        raise ValueError(f"Browser handoff selection or execution is invalid: {path}")
    return identities


def validate_native_report(path: Path) -> None:
    try:
        document = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError("Invalid native JUnit report") from exc
    suites = list(document.iter("testsuite"))
    cases = list(document.iter("testcase"))
    if (
        document.tag not in {"testsuites", "testsuite"}
        or len(suites) != 1
        or len(cases) != 1
        or cases[0].get("classname") != NATIVE_CLASS
        or cases[0].get("name") != NATIVE_METHOD
        or any(list(document.iter(tag)) for tag in ("skipped", "failure", "error"))
        or suites[0].get("tests") != "1"
        or any(s.get(key) != "0" for s in suites for key in ("skipped", "failures", "errors"))
    ):
        raise ValueError("Native lane requires exactly one executed, passing, exact-node testcase")


def run(root: Path, inherited: dict[str, str], output_parent: Path) -> Path:
    parent = output_parent.resolve(strict=True)
    if parent.is_relative_to(root.resolve()):
        raise ValueError("Browser evidence parent must be outside the source checkout")
    run_dir = Path(tempfile.mkdtemp(prefix="alpha-browser-lanes-", dir=parent))
    summary: dict[str, Any] = {"status": "failed", "completed_lanes": [], "run_dir": str(run_dir)}
    print(f"Browser lane evidence: {run_dir}", flush=True)
    try:
        env = prerequisites(root, inherited)
        frontend = root / "apps/alpha-web/frontend"
        node = shutil.which("node", path=env["PATH"])
        assert node is not None
        # Validate the native pin with the existing implementation, without a
        # fixture, worker launch, owner store, model invocation or duplicate policy.
        run_child(
            [
                sys.executable,
                "-c",
                "import os; from pathlib import Path; "
                "from alpha_cli._native_stock_launch import StockFixtureLaunch; "
                "StockFixtureLaunch(Path(os.environ['ALPHA_RDAGENT_SOURCE']), 'resume', "
                "stock_runtime=Path(os.environ['ALPHA_STOCK_PYTHON']).parents[2])",
            ],
            root,
            env,
            run_dir / "native-prerequisites.log",
            root,
        )
        run_child(
            [
                node,
                "-e",
                "const fs=require('node:fs'); "
                "const {chromium}=require('@playwright/test'); "
                "fs.accessSync(chromium.executablePath(),fs.constants.X_OK)",
            ],
            frontend,
            env,
            run_dir / "browser-prerequisites.log",
            root,
        )
        cli = str(frontend / "node_modules/@playwright/test/cli.js")
        routes = (
            ("default", "playwright.config.ts", None),
            ("risk-basis", "playwright.risk-basis.config.ts", HANDOFFS[0]),
            ("risk-live", "playwright.risk-live.config.ts", HANDOFFS[1]),
        )
        # Playwright itself resolves config/grep/project membership. Listing imports
        # these public specs but starts no server or browser. Native needs its real
        # descriptor and is selected only by the exact existing pytest method.
        selections: dict[str, set[tuple[str, str, str]]] = {}
        for lane, config, file in routes:
            directory = run_dir / lane
            directory.mkdir()
            listing = directory / "selection.json"
            listing_env = {**env, "PLAYWRIGHT_JSON_OUTPUT_FILE": str(listing)}
            if lane == "risk-live":
                listing_env["C04_RISK_LIVE_ROOT"] = str(directory)
            run_child(
                [
                    node,
                    cli,
                    "test",
                    "--config",
                    str(frontend / config),
                    "--list",
                    "--reporter=json",
                ],
                frontend,
                listing_env,
                directory / "selection.log",
                root,
            )
            selections[lane] = validate_browser_report(
                listing, frontend, config, file, listing=True
            )
        for lane, config, file in routes:
            directory = run_dir / lane
            lane_env = dict(env)
            if lane == "risk-live":
                lane_env["C04_RISK_LIVE_ROOT"] = str(directory)
                run_child(
                    [
                        node,
                        str(frontend / "node_modules/vite/bin/vite.js"),
                        "build",
                        "--outDir",
                        str(directory / "spa"),
                    ],
                    frontend,
                    lane_env,
                    directory / "build.log",
                    root,
                )
            report = directory / "report.json"
            lane_env["PLAYWRIGHT_JSON_OUTPUT_FILE"] = str(report)
            reporter = "github,list,json" if lane == "default" and env.get("CI") else "list,json"
            run_child(
                [
                    node,
                    cli,
                    "test",
                    "--config",
                    str(frontend / config),
                    "--output",
                    str(directory / "artifacts"),
                    "--reporter",
                    reporter,
                ],
                frontend,
                lane_env,
                directory / "run.log",
                root,
            )
            if validate_browser_report(report, frontend, config, file) != selections[lane]:
                raise ValueError(f"Browser execution differs from its fresh selection: {lane}")
            summary["completed_lanes"].append(lane)
        native = run_dir / "native"
        native.mkdir()
        native_env = {**env, "ALPHA_NATIVE_WEB_EVIDENCE": str(native / "evidence")}
        report = native / "junit.xml"
        run_child(
            [sys.executable, "-m", "pytest", "-q", NATIVE_NODE, f"--junitxml={report}"],
            root,
            native_env,
            native / "run.log",
            root,
        )
        validate_native_report(report)
        summary["completed_lanes"].append("native")
        summary["status"] = "passed"
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        summary["error"] = str(exc)
        raise
    finally:
        with (run_dir / "summary.json").open("x") as stream:
            json.dump(summary, stream, indent=2)
            stream.write("\n")
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-parent", type=Path, default=Path(tempfile.gettempdir()))
    args = parser.parse_args()
    try:
        run(ROOT, dict(os.environ), args.output_parent)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f"Browser lanes failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
