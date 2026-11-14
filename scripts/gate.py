"""Local engineering checks for Project ALPHA.

CI on the pull request is the merge gate; nothing here proves or records that a tree passed.
This module holds the fast local check, the CI component runner entry point, the harness
weakening scanner, the harness doctor and the quant-rigor sweeps CI and nightly jobs call.

Top level is stdlib-only so hook shims can import it before ``uv sync`` has ever run;
pydantic models (scripts/harness_models.py) are imported lazily where they are needed.

CLI:
    python3 scripts/gate.py check [--all] [--base REF]  # fast local check (~3 min)
    python3 scripts/gate.py component NAME [--shard I/N]  # one CI job's steps, as CI runs them
    python3 scripts/gate.py changes [--all]    # which conditional CI jobs a change needs
    python3 scripts/gate.py coverage --shards N [--base REF]  # combine shards, gate changed lines
    python3 scripts/gate.py durations JUNIT... [--output F]  # per-file seconds for shard balance
    python3 scripts/gate.py preflight [--json] # read-only environment readiness report
    python3 scripts/gate.py orient [--json]    # source orientation (same as scripts/fs.py orient)
    python3 scripts/gate.py lint-harness       # weakening scanner vs .claude/harness-baseline.json
    python3 scripts/gate.py baseline           # rewrite that baseline (reviewed in the PR)
    python3 scripts/gate.py plan-check PLAN.md # validate a plan's ```json FeaturePlan front block
    python3 scripts/gate.py doctor [--json]    # verify the harness wiring itself
    python3 scripts/gate.py mutate [MODULES|--all] [--json --write-baseline --require-measured]
    python3 scripts/gate.py semgrep [--changed] # .semgrep/alpha.yml banned constructs
    python3 scripts/gate.py determinism        # byte-stability tests twice under perturbed env
    python3 scripts/gate.py raise-cov [--fail] # `raise` lines in quant modules no test reached
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_DIR = Path(".alpha") / "state"
BASELINE_FILE = Path(".claude") / "harness-baseline.json"

FULL_GATE_MYPY_COMMAND = ("uv", "run", "mypy", "packages", "apps", "tests")

# claude_hooks.py subcommands; doctor verifies every one is wired in settings.json.
HOOK_NAMES = (
    "pre-file-guard",
    "pre-mcp-guard",
    "pre-owner-action-guard",
    "session-start",
)

_QUANT_NAME_RE = re.compile(
    r"(dsr|psr|pbo|deflated|bootstrap|reality_check|spa|montecarlo|"
    r"walkforward|cpcv|multiple_testing|overfitting)"
)
_QUANT_SRC_PREFIXES = ("packages/alpha-validation/src/", "packages/alpha-research/src/")

EnvRunner = Callable[..., tuple[bool, float, str]]


# ---------------------------------------------------------------------------
# git plumbing


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def repo_root(start: Path | None = None, *, timeout: float | None = None) -> Path:
    """Resolve the enclosing repository root (worktree-correct) from cwd."""
    where = start or Path.cwd()
    out = subprocess.run(
        ["git", "-C", str(where), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )
    return Path(out.stdout.strip())


def _status_entries(root: Path) -> list[tuple[str, bool]]:
    """``(path, untracked)`` for every changed or untracked working-tree entry."""
    status = _git(root, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    entries: list[tuple[str, bool]] = []
    records = iter(status.split("\0"))
    for entry in records:
        if not entry:
            continue
        kind = entry[0]
        if kind == "?":
            entries.append((entry[2:], True))
        elif kind in {"1", "2", "u"}:
            fields = {"1": 8, "2": 9, "u": 10}[kind]
            entries.append((entry.split(" ", fields)[fields], False))
            if kind == "2":
                entries.append((next(records), False))
    return entries


def scoped_changed_paths(root: Path, matcher: Callable[[str], bool]) -> list[str]:
    """Working-tree paths (tracked-changed or untracked) accepted by ``matcher``."""
    return sorted({path for path, _ in _status_entries(root) if matcher(path)})


# ---------------------------------------------------------------------------
# path tiers


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def matches_quant(path: str) -> bool:
    """Statistical source code requiring academic verification before Stop."""
    posix = _posix(path)
    if posix.startswith(_QUANT_SRC_PREFIXES):
        return posix.endswith(".py")
    if posix.startswith("packages/") and "/src/" in posix and posix.endswith(".py"):
        return bool(_QUANT_NAME_RE.search(posix.rsplit("/", 1)[-1]))
    return False


# ---------------------------------------------------------------------------
# state files


def _state_dir(root: Path) -> Path:
    directory = root / STATE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def first_json_object(text: str) -> str | None:
    """The outermost ``{...}`` slice of ``text`` (fenced or not), or ``None``."""
    body = text.strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    return body[start : end + 1]


def write_json_atomic(path: Path, obj: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# weakening scanner


def harness_metrics(root: Path) -> dict[str, Any]:
    """Explicit safety configuration; file/contract counts are not behavioral evidence."""
    settings = read_json(root / ".claude" / "settings.json") or {}
    permissions = settings.get("permissions") or {}
    deny = sorted(str(rule) for rule in permissions.get("deny") or [])
    hook_events = sorted(str(k) for k in (settings.get("hooks") or {}))
    pyproject = (root / "pyproject.toml").read_text() if (root / "pyproject.toml").is_file() else ""
    # The one coverage floor in pyproject: since the global floor was retired it is the
    # changed-line floor under [tool.diff_cover].
    fail_under = 0
    match = re.search(r"^fail_under\s*=\s*(\d+)", pyproject, re.MULTILINE)
    if match:
        fail_under = int(match.group(1))
    strict_markers = "--strict-markers" in pyproject
    suppressions = 0
    for base in ("packages/alpha-validation/src", "packages/alpha-research/src"):
        directory = root / base
        if not directory.is_dir():
            continue
        for file in directory.rglob("*.py"):
            text = file.read_text(errors="replace")
            suppressions += text.count("# noqa") + text.count("# type: ignore")
    return {
        "schema_version": 2,
        "deny_rules": deny,
        "hook_events": hook_events,
        "coverage_fail_under": fail_under,
        "strict_markers": strict_markers,
        "quant_suppressions": suppressions,
    }


def lint_harness(root: Path) -> list[str]:
    """Return regressions of the current tree against the committed baseline."""
    baseline = read_json(root / BASELINE_FILE)
    if baseline is None:
        return [f"{BASELINE_FILE} missing — run `gate.py baseline`"]
    current = harness_metrics(root)
    problems: list[str] = []
    for rule in set(baseline.get("deny_rules", [])) - set(current["deny_rules"]):
        problems.append(f"deny rule removed: {rule}")
    for event in set(baseline.get("hook_events", [])) - set(current["hook_events"]):
        problems.append(f"hook event unwired: {event}")
    if current["coverage_fail_under"] < int(baseline.get("coverage_fail_under", 0)):
        problems.append(
            f"coverage fail_under lowered: {baseline.get('coverage_fail_under')} -> "
            f"{current['coverage_fail_under']}"
        )
    if baseline.get("strict_markers") and not current["strict_markers"]:
        problems.append("--strict-markers disabled")
    if current["quant_suppressions"] > int(baseline.get("quant_suppressions", 0)):
        problems.append(
            f"quant-module suppressions grew: {baseline.get('quant_suppressions')} -> "
            f"{current['quant_suppressions']} (# noqa / # type: ignore)"
        )
    ci = root / ".github" / "workflows" / "ci.yml"
    if ci.is_file():
        text = ci.read_text()
        if re.search(r"pytest[^\n]*(--maxfail|\s-x\b)", text):
            problems.append("CI pytest uses -x/--maxfail (hides later failures)")
    return problems


def write_baseline(root: Path) -> None:
    """Rewrite the committed baseline; the change is reviewed in the pull request like any other."""
    from harness_models import HarnessBaseline

    baseline = HarnessBaseline.model_validate(harness_metrics(root))
    write_json_atomic(root / BASELINE_FILE, baseline.model_dump())


# ---------------------------------------------------------------------------
# gate execution


def _env_runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
    """The one subprocess wrapper: (ok, seconds, combined output); never raises."""
    started = time.monotonic()
    # A separate owner can reap Linux orphans without stealing pytest/app wait statuses.
    command = cmd
    if sys.platform == "linux" and cmd[:3] == ["uv", "run", "pytest"]:
        owner = Path(__file__).resolve().with_name("run_owned_test.py")
        limit = kwargs.pop("timeout", None)
        timeout_args = [] if limit is None else ["--timeout", str(limit)]
        command = [sys.executable, str(owner), *timeout_args, "--", *cmd]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (False, time.monotonic() - started, f"{type(exc).__name__}: {exc}")
    output = (result.stdout + result.stderr).strip()
    return (result.returncode == 0, time.monotonic() - started, output)


HARNESS_SCRIPTS = (
    "scripts/run_owned_test.py",
    "scripts/gate.py",
    "scripts/gate_components.py",
    "scripts/gate_preflight.py",
    "scripts/gate_select.py",
    "scripts/git_guard.py",
    "scripts/wheel_smoke.py",
    "scripts/check_semgrep_contracts.py",
    "scripts/fs.py",
    "scripts/fs_orient.py",
    "scripts/fs_search.py",
    "scripts/fs_stale.py",
    "scripts/commands_reference.py",
    "scripts/status.py",
    "scripts/capabilities.py",
    "scripts/claude_hooks.py",
    "scripts/harness_awareness.py",
    "scripts/harness_models.py",
    "scripts/harness_quant.py",
    "scripts/mutation_sweep.py",
    "scripts/mutation_legacy.py",
    "scripts/mutation_fragment.py",
    "scripts/check_mutation_report.py",
    "scripts/codex_bridge.py",
    "scripts/handoff.py",
    ".claude/statusline.py",
)


CHECK_PYTEST_MARKERS = "not network and not slow_oracle"
FAST_TIER_MARKERS = "not platform and not network and not slow_oracle"


def check_steps(root: Path, test_paths: list[str] | None) -> list[tuple[str, list[str]]]:
    """The fast local check; ``test_paths`` None runs the whole fast tier instead of a selection."""
    harness_files = [rel for rel in HARNESS_SCRIPTS if (root / rel).is_file()]
    workers = str(max(1, min(3, (os.cpu_count() or 2) // 2)))
    pytest = ["uv", "run", "pytest", "-q", "-n", workers]
    if test_paths is None:
        pytest += ["-m", FAST_TIER_MARKERS]
    else:
        pytest += ["-m", CHECK_PYTEST_MARKERS, *test_paths]
    return [
        ("ruff check", ["uv", "run", "ruff", "check", "."]),
        ("ruff format", ["uv", "run", "ruff", "format", "--check", "."]),
        ("import contracts", ["uv", "run", "lint-imports"]),
        # One mypy run: pyproject's strict config covers the harness scripts too.
        ("mypy", [*FULL_GATE_MYPY_COMMAND, *harness_files]),
        ("pytest", pytest),
    ]


def run_check(
    root: Path, *, run_all: bool = False, base: str | None = None, runner: EnvRunner | None = None
) -> int:
    """Run every check step, print one line each, then a plain-English summary. Writes nothing."""
    import gate_components  # deferred: gate_components imports gate
    import gate_select

    run = runner or _env_runner
    selection = None
    if not run_all:
        changed = gate_components.comparison_context(root, base)["paths"]
        selection = gate_select.select(root, changed)
    failed: list[str] = []
    started = time.monotonic()
    for name, command in check_steps(root, None if selection is None else selection.pytest_paths()):
        ok, seconds, output = run(command, cwd=root)
        print(f"[check] {name}: {'PASS' if ok else 'FAIL'} ({seconds:.1f}s)", flush=True)
        if not ok:
            failed.append(name)
            print(output[-4000:], file=sys.stderr)
    elapsed = time.monotonic() - started
    if selection is None:
        scope = "the whole fast test tier"
    else:
        changed_count = "unknown" if selection.changed is None else len(selection.changed)
        scope = (
            f"the research guards plus {len(selection.mapped)} test file(s) mapped from "
            f"{changed_count} changed path(s) and {len(selection.last_failed)} last failure(s)"
        )
    for note in () if selection is None else selection.notes:
        print(f"[check] note: {note}")
    if failed:
        print(f"[check] FAILED in {elapsed:.0f}s: {', '.join(failed)}. Tests run: {scope}.")
        return 1
    print(
        f"[check] All checks passed in {elapsed:.0f}s. Tests run: {scope}. "
        "CI runs everything on the pull request."
    )
    return 0


# ---------------------------------------------------------------------------
# doctor


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fields: dict[str, str] = {}
    key = ""
    for line in parts[1].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            key = key.strip()
            fields[key] = value.strip()
        elif key and line.lstrip().startswith("- "):  # YAML block list → inline "[a, b]"
            item = line.lstrip()[2:].strip()
            inner = fields[key].strip("[]")
            fields[key] = f"[{inner}, {item}]" if inner else f"[{item}]"
    return fields


def _bracket_list(value: str) -> list[str]:
    """A frontmatter inline list (``[a, b]``) as items, brackets and quotes stripped."""
    return [item.strip().strip("\"'") for item in value.strip("[]").split(",") if item.strip()]


def codex_probe() -> tuple[bool, str]:
    """Is the Codex CLI installed and logged in? Never calls the model."""
    binary = shutil.which("codex")
    if binary is None:
        return (False, "codex CLI not on PATH (second-model review unavailable; gates unaffected)")
    try:
        status = subprocess.run(
            ["codex", "login", "status"], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (False, f"codex login status failed: {exc!r}")
    text = (status.stdout + status.stderr).strip()
    if "logged in" in text.lower() and "not logged" not in text.lower():
        return (True, f"{binary}: {text.splitlines()[0][:80]}")
    return (False, f"codex present but not logged in: {text[:80]}")


# ADR-0032 default reserve and ADR-0043 owner-set override; mirrors alpha_cli.crypto_bulk_store
# with the standard library only, because doctor must run before `uv sync`.
_DEFAULT_RESERVE_FRACTION = 0.15
_DEFAULT_MINIMUM_FREE_BYTES = 100_000_000_000
_GB = 1_000_000_000


def storage_advisory(
    root: Path,
    environ: dict[str, str] | None = None,
    usage: Callable[[Path], Any] = shutil.disk_usage,
) -> tuple[bool, str]:
    """Machine-state disk report for the data root. Advisory only: never fails the doctor.

    Reads only ``ALPHA_DATA_DIR`` from the environment (never ``.env``) and the retained
    ``<data>/crypto/storage-config.json``. Refusals stay in the storage code itself.
    """
    env = os.environ if environ is None else environ
    data = Path(env.get("ALPHA_DATA_DIR") or (root / "data"))
    if not data.is_absolute():
        data = root / data
    config_path = data / "crypto" / "storage-config.json"
    config: dict[str, Any] = {}
    if config_path.is_file() and not config_path.is_symlink():
        try:
            loaded = json.loads(config_path.read_bytes()[:8192])
            config = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            return (True, f"storage settings unreadable at {config_path}; storage commands refuse")
    probe = Path(str(config.get("bulk_root") or data))
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    disk = usage(probe)
    free, total = int(disk.free), int(disk.total)
    owner = config.get("free_space_reserve")
    if isinstance(owner, dict) and isinstance(owner.get("minimum_free_bytes"), int):
        reserve = int(owner["minimum_free_bytes"])
        advisory = owner.get("advisory_free_bytes")
        threshold = int(advisory) if isinstance(advisory, int) else reserve
        source = f"owner-set ({owner.get('decided_by')}, {owner.get('decided_on')})"
    else:
        reserve = max(int(total * _DEFAULT_RESERVE_FRACTION), _DEFAULT_MINIMUM_FREE_BYTES)
        threshold = reserve
        source = "default 15%/100 GB" + ("" if config else "; no storage settings yet")
    detail = (
        f"{free / _GB:.1f} GB free at {probe}; reserve {reserve / _GB:.1f} GB ({source}); "
        f"advisory below {threshold / _GB:.1f} GB"
    )
    if free < reserve:
        detail = "LOW DISK SPACE: below the reserve; data-storage writes refuse. " + detail
    elif free < threshold:
        detail = "LOW DISK SPACE: below the owner's advisory threshold. " + detail
    return (True, detail)


# ---------------------------------------------------------------------------
# machine readiness: "can this machine do synthetic-data development?" (plain English, stdlib only)

MACHINE_QUESTION = "Can this machine do synthetic-data development?"
SETUP_COMMAND = "bash scripts/setup.sh"
RDAGENT_SETUP_SCRIPT = Path("scripts") / "setup_rdagent.sh"
_FRONTEND = Path("apps") / "alpha-web" / "frontend"
_WEB_BUNDLE = Path("apps") / "alpha-web" / "src" / "alpha_web" / "static" / "app" / "index.html"

ProbeRunner = Callable[[list[str], Path], tuple[int, str]]


def _run_probe(argv: list[str], cwd: Path) -> tuple[int, str]:
    """Run one short read-only command; (exit code, output). Never raises."""
    try:
        done = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (127, repr(exc))
    return (done.returncode, (done.stdout + done.stderr).strip())


def _item(name: str, required: bool, present: bool, detail: str, fix: str) -> dict[str, Any]:
    return {
        "name": name,
        "required": required,
        "status": "present" if present else "missing",
        "detail": detail,
        "fix": "" if present else fix,
    }


def _playwright_cache(root: Path, env: dict[str, str]) -> Path:
    explicit = env.get("PLAYWRIGHT_BROWSERS_PATH")
    if explicit == "0":  # Playwright's own spelling for "inside node_modules"
        return root / _FRONTEND / "node_modules" / "playwright-core" / ".local-browsers"
    if explicit:
        return Path(explicit)
    cache_home = env.get("XDG_CACHE_HOME") or str(Path(env.get("HOME") or Path.home()) / ".cache")
    return Path(cache_home) / "ms-playwright"


def _browser_item(root: Path, env: dict[str, str]) -> dict[str, Any]:
    name = "Browser for the web app's tests (Playwright Chromium)"
    fix = f"cd {_FRONTEND} && npm ci && npx --no-install playwright install chromium"
    cache = _playwright_cache(root, env)
    listing = read_json(root / _FRONTEND / "node_modules" / "playwright-core" / "browsers.json")
    revisions = {
        str(entry.get("name")): str(entry.get("revision"))
        for entry in (listing or {}).get("browsers", [])
        if isinstance(entry, dict)
    }
    if "chromium" not in revisions:
        return _item(
            name,
            True,
            False,
            "the web app's packages are not installed, so the browser version it needs is unknown",
            fix,
        )
    wanted = [f"chromium-{revisions['chromium']}"]
    if "chromium-headless-shell" in revisions:
        wanted.append(f"chromium_headless_shell-{revisions['chromium-headless-shell']}")
    absent = [folder for folder in wanted if not (cache / folder).is_dir()]
    if absent:
        return _item(name, True, False, f"not found in {cache}: {', '.join(absent)}", fix)
    return _item(name, True, True, f"{', '.join(wanted)} in {cache}", fix)


def _python_in(venv: Path) -> Path:
    return venv / "bin" / "python"


def _daily_image_pin(root: Path) -> tuple[str, str] | None:
    """The pinned daily-study image (repository digest, image id), read from its one home."""
    try:
        text = (root / RDAGENT_SETUP_SCRIPT).read_text()
    except OSError:
        return None
    digest = re.search(r"^daily_digest=(sha256:[0-9a-f]{64})$", text, re.MULTILINE)
    image = re.search(r"^daily_image=(sha256:[0-9a-f]{64})$", text, re.MULTILINE)
    return (digest.group(1), image.group(1)) if digest and image else None


def _rdagent_runtime_items(runtime: Path, env: dict[str, str]) -> list[dict[str, Any]]:
    """Doctor items for the Python 3.11 RD-Agent runtimes (stock loop; factor loop, ADR-0049)."""
    stock = Path(
        env.get("ALPHA_STOCK_PYTHON") or runtime / "rdagent-stock-py311" / "venv" / "bin" / "python"
    )
    factor_bundle = runtime / "rdagent-factor-py311"
    factor = Path(env.get("ALPHA_FACTOR_PYTHON") or factor_bundle / "venv" / "bin" / "python")
    factor_profile = factor_bundle / "factor-profile.json"
    factor_ok = factor.is_file() and factor_profile.is_file()
    if factor_ok:
        factor_detail = f"found at {factor}, profile recorded"
    elif factor.is_file():
        factor_detail = f"profile not recorded at {factor_profile}"
    else:
        factor_detail = f"not found at {factor}"
    return [
        _item(
            "RD-Agent stock runtime (Python 3.11)",
            False,
            stock.is_file(),
            f"found at {stock}" if stock.is_file() else f"not found at {stock}",
            f"{SETUP_COMMAND} --with-stock-runtime",
        ),
        _item(
            "RD-Agent factor-loop runtime (Python 3.11, ADR-0049)",
            False,
            factor_ok,
            factor_detail,
            f"{SETUP_COMMAND} --with-factor-runtime",
        ),
    ]


def machine_readiness(
    root: Path,
    environ: dict[str, str] | None = None,
    run: ProbeRunner = _run_probe,
    which: Callable[[str], str | None] = shutil.which,
    usage: Callable[[Path], Any] = shutil.disk_usage,
    codex: Callable[[], tuple[bool, str]] | None = None,
) -> list[dict[str, Any]]:
    """Every item synthetic-data development needs, present or missing, with the fixing command.

    Reads only the repository tree, a few non-secret environment variables, ``codex login
    status`` and Docker's own status; never ``.env``, never ``~/.codex``. Standard library only.
    """
    env = dict(os.environ if environ is None else environ)
    items: list[dict[str, Any]] = []

    venv_python = _python_in(root / ".venv")
    importable = False
    if venv_python.is_file():
        code, _ = run(
            [
                str(venv_python),
                "-I",
                "-c",
                "import importlib.util, sys; "
                "sys.exit(0 if importlib.util.find_spec('alpha_cli') else 1)",
            ],
            root,
        )
        importable = code == 0
    items.append(
        _item(
            "Root Python environment",
            True,
            importable,
            ".venv has the ALPHA packages installed" if importable else "no usable .venv here",
            "uv sync --locked",
        )
    )

    bundle = root / _WEB_BUNDLE
    built = bundle.is_file() and bundle.stat().st_size > 0
    items.append(
        _item(
            "Built web app",
            True,
            built,
            f"{_WEB_BUNDLE} exists"
            if built
            else f"{_WEB_BUNDLE} is missing (the web app is not built)",
            f"cd {_FRONTEND} && npm ci && npm run build",
        )
    )

    items.append(_browser_item(root, env))

    for worker, label in (("qlib", "Qlib"), ("literature", "Literature")):
        python = _python_in(root / "workers" / worker / ".venv")
        items.append(
            _item(
                f"{label} worker environment",
                True,
                python.is_file(),
                f"workers/{worker}/.venv exists"
                if python.is_file()
                else f"workers/{worker}/.venv is missing",
                f"cd workers/{worker} && uv sync --locked",
            )
        )

    runtime = root / STATE_DIR / "runtime"
    source = Path(env.get("ALPHA_RDAGENT_SOURCE") or runtime / "rdagent-source")
    has_source = (source / "rdagent").is_dir()
    items.append(
        _item(
            "RD-Agent source (pinned)",
            False,
            has_source,
            f"found at {source}" if has_source else f"not found at {source}",
            f"{SETUP_COMMAND} --with-rdagent",
        )
    )
    profiles = [
        root / "workers" / "rdagent" / ".venv-rule-qualified",
        root / "workers" / "rdagent" / ".venv-economics-qualified",
    ]
    absent_profiles = [p.name for p in profiles if not _python_in(p).is_file()]
    items.append(
        _item(
            "RD-Agent rule and economics environments",
            False,
            not absent_profiles,
            "both built" if not absent_profiles else "not built: " + ", ".join(absent_profiles),
            f"{SETUP_COMMAND} --with-rdagent",
        )
    )
    items += _rdagent_runtime_items(runtime, env)

    docker_fix = "install Docker (https://docs.docker.com/engine/install/) and start it"
    if which("docker") is None:
        docker_ok, docker_detail = False, "the docker command is not installed"
    else:
        code, out = run(["docker", "version", "--format", "{{.Server.Version}}"], root)
        docker_ok = code == 0 and bool(out)
        docker_detail = (
            f"Docker engine {out.splitlines()[0]}"
            if docker_ok
            else "Docker is installed but not answering (not running, or no permission): "
            + out[:80]
        )
    items.append(_item("Docker", False, docker_ok, docker_detail, docker_fix))

    pin = _daily_image_pin(root)
    image_fix = f"{SETUP_COMMAND} --with-daily-container"
    if pin is None:
        image_ok, image_detail = (
            False,
            f"the pinned image is not readable from {RDAGENT_SETUP_SCRIPT}",
        )
    elif not docker_ok:
        image_ok, image_detail = False, "needs Docker first"
    else:
        code, out = run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", f"python@{pin[0]}"], root
        )
        image_ok = code == 0 and out.strip() == pin[1]
        image_detail = (
            f"python@{pin[0][:19]}... present, image {pin[1][:19]}..."
            if image_ok
            else f"python@{pin[0][:19]}... is not pulled (or is a different image)"
        )
    items.append(
        _item("Daily-study Docker image (pinned)", False, image_ok, image_detail, image_fix)
    )

    codex_ok, codex_detail = (codex or codex_probe)()
    items.append(
        _item(
            "Codex CLI, signed in",
            False,
            codex_ok,
            codex_detail,
            "install the Codex CLI (docs/operations/codex-second-model-runbook.md), "
            "then run: codex login"
            if "not on PATH" in codex_detail
            else "codex login",
        )
    )

    try:
        _, disk_detail = storage_advisory(root, env, usage)
        disk_ok = not disk_detail.startswith("LOW DISK SPACE")
    except OSError as exc:
        disk_ok, disk_detail = False, f"could not read free disk space: {exc}"
    items.append(
        _item(
            "Free disk space above the storage reserve",
            False,
            disk_ok,
            disk_detail,
            "free some disk space, or record your own reserve: "
            f"{SETUP_COMMAND} --data-dir /ABSOLUTE/DATA/FOLDER --storage-reserve-gb 10 "
            "(docs/operations/storage-settings.md)",
        )
    )
    return items


def machine_summary(
    items: list[dict[str, Any]], environ: dict[str, str] | None = None
) -> dict[str, Any]:
    """The machine section of the report; hosted CI (``CI`` set) lists items but enforces none."""
    env = os.environ if environ is None else environ
    enforced = not env.get("CI")
    missing_required = [i["name"] for i in items if i["required"] and i["status"] == "missing"]
    missing_optional = [i["name"] for i in items if not i["required"] and i["status"] == "missing"]
    return {
        "question": MACHINE_QUESTION,
        "ready": not missing_required,
        "enforced": enforced,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "fix_everything_required": SETUP_COMMAND,
        "items": items,
    }


def format_machine_section(machine: dict[str, Any]) -> list[str]:
    lines = ["", f"{machine['question']}"]
    for item in machine["items"]:
        mark = "present" if item["status"] == "present" else "MISSING"
        need = "required" if item["required"] else "optional"
        lines.append(f"  [{mark}] {item['name']} ({need}): {item['detail']}")
        if item["fix"]:
            lines.append(f"            fix: {item['fix']}")
    if machine["ready"]:
        verdict = "Yes: everything required is in place."
    else:
        verdict = (
            "No: required items are missing ("
            + ", ".join(machine["missing_required"])
            + f"). One command fixes them all: {machine['fix_everything_required']}."
        )
    if machine["missing_optional"]:
        verdict += " Optional items missing: " + ", ".join(machine["missing_optional"]) + "."
    if not machine["enforced"]:
        verdict += " (Hosted CI runner: listed for information, not enforced.)"
    lines.append(verdict)
    return lines


def doctor(
    root: Path,
    readiness: Callable[[Path], list[dict[str, Any]]] | None = None,
) -> tuple[int, dict[str, Any]]:
    checks: list[tuple[str, bool, str]] = []

    settings_path = root / ".claude" / "settings.json"
    settings = read_json(settings_path)
    checks.append(("settings.json parses", settings is not None, str(settings_path)))

    wired = json.dumps(settings.get("hooks", {})) if settings else ""
    for name in HOOK_NAMES:
        checks.append((f"hook wired: {name}", name in wired, "settings.json hooks block"))

    for rel in HARNESS_SCRIPTS:
        checks.append((f"file present: {rel}", (root / rel).is_file(), rel))

    try:
        probe = _state_dir(root) / ".doctor-probe"
        probe.write_text("ok")
        probe.unlink()
        checks.append(("state dir writable", True, str(_state_dir(root))))
    except OSError as exc:
        checks.append(("state dir writable", False, str(exc)))

    skills_dir = root / ".claude" / "skills"
    if skills_dir.is_dir():
        for stub in sorted(skills_dir.iterdir()):
            if not stub.is_dir():
                continue
            canonical = root / ".agents" / "skills" / stub.name / "SKILL.md"
            checks.append(
                (
                    f"skill stub has canonical: {stub.name}",
                    canonical.is_file(),
                    str(canonical),
                )
            )

    agents_dir = root / ".claude" / "agents"
    if agents_dir.is_dir():
        for agent in sorted(agents_dir.glob("*.md")):
            fields = _frontmatter(agent.read_text())
            ok = bool(fields.get("name")) and bool(fields.get("description"))
            skills = _bracket_list(fields.get("skills", ""))
            missing = [s for s in skills if not (skills_dir / s).is_dir()]
            checks.append(
                (
                    f"agent frontmatter valid: {agent.stem}",
                    ok and not missing,
                    "missing skills: " + ", ".join(missing) if missing else "name+description",
                )
            )

    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        for rule in sorted(rules_dir.glob("*.md")):
            fields = _frontmatter(rule.read_text())
            paths_field = fields.get("paths", "")
            unmatched = [g for g in _bracket_list(paths_field) if not any(root.glob(g))]
            checks.append(
                (
                    f"rule paths resolve: {rule.stem}",
                    not unmatched,
                    "unmatched: " + ", ".join(unmatched)
                    if unmatched
                    else (paths_field or "unscoped"),
                )
            )

    baseline_ok = (root / BASELINE_FILE).is_file()
    checks.append(("harness baseline present", baseline_ok, str(BASELINE_FILE)))
    if baseline_ok:
        problems = lint_harness(root)
        checks.append(
            ("harness not weakened", not problems, "; ".join(problems) or "no regressions")
        )

    checks.append(("storage free-space advisory", *storage_advisory(root)))

    codex_ok, codex_detail = codex_probe()
    checks.append(("codex second model", True, ("available: " if codex_ok else "") + codex_detail))

    report: dict[str, Any] = {
        "created_at": _now(),
        "checks": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in checks],
        "ok": all(ok for _, ok, _ in checks),
    }
    try:
        from harness_models import DoctorReport

        DoctorReport.model_validate(report)
    except ImportError:
        pass  # doctor must still run pre-`uv sync`; validation is best-effort here
    machine = machine_summary((readiness or machine_readiness)(root))
    report["machine"] = machine
    if machine["enforced"] and not machine["ready"]:
        report["ok"] = False
    return (0 if report["ok"] else 1, report)


# ---------------------------------------------------------------------------
# quant-tier module selection (W5); the sweeps themselves live in scripts/harness_quant.py

SEMGREP_RULES = Path(".semgrep") / "alpha.yml"


def quant_source_modules(root: Path, paths: list[str] | None = None) -> list[str]:
    """Quant-tier SOURCE modules (default: those changed in the working tree). Tests excluded."""
    candidates = paths if paths is not None else scoped_changed_paths(root, matches_quant)
    return sorted(
        p
        for p in candidates
        if matches_quant(p)
        and "/src/" in p
        and not p.rsplit("/", 1)[-1].startswith("__")
        and (root / p).is_file()
    )


def all_quant_source_modules(root: Path) -> list[str]:
    files = [
        str(p.relative_to(root)).replace(os.sep, "/")
        for prefix in _QUANT_SRC_PREFIXES
        for p in sorted((root / prefix).rglob("*.py"))
        if (root / prefix).is_dir()
    ]
    return quant_source_modules(root, files)


# ---------------------------------------------------------------------------
# CLI


def _reexec_with_pydantic(root: Path) -> None:
    """Re-exec under the project venv when pydantic is unavailable.

    ``baseline`` and ``plan-check`` validate with pydantic, but the stdlib-only commands
    must keep working when invoked as plain ``python3``.
    """
    try:
        import pydantic  # noqa: F401

        return
    except ImportError:
        pass
    venv_python = root / ".venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), *sys.argv])
    raise SystemExit(
        "pydantic unavailable and no project venv found — run via: "
        "uv run python scripts/gate.py ..."
    )


def _shard_spec(value: str) -> tuple[int, int]:
    """``I/N`` with 1 <= I <= N, as a CI matrix names its shard."""
    index, _, total = value.partition("/")
    try:
        shard = (int(index), int(total))
    except ValueError:
        raise argparse.ArgumentTypeError(f"shard must look like 2/4, got {value!r}") from None
    if not 1 <= shard[0] <= shard[1]:
        raise argparse.ArgumentTypeError(f"shard index must be within 1..N, got {value!r}")
    return shard


def build_parser() -> argparse.ArgumentParser:
    """The full CLI parser (built apart from ``main`` so every subcommand is testable)."""
    parser = argparse.ArgumentParser(prog="gate", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check_p = sub.add_parser("check", help="fast local check: lint, types, mapped tests")
    check_p.add_argument("--all", action="store_true", help="run the whole fast test tier")
    check_p.add_argument("--base", default=None, help="comparison base (default origin/main)")
    preflight_p = sub.add_parser("preflight", help="read-only environment readiness report")
    preflight_p.add_argument("--json", action="store_true")
    component_p = sub.add_parser("component", help="one CI job's steps, as CI runs them")
    component_p.add_argument(
        "name",
        choices=(
            "backend",
            "backend-static",
            "backend-tests",
            "backend-quant",
            "frontend",
            "frontend-full",
            "literature",
            "qlib",
        ),
    )
    component_p.add_argument(
        "--shard", type=_shard_spec, default=None, help="backend-tests only: I/N, 1-based"
    )
    changes_p = sub.add_parser("changes", help="which conditional CI jobs the change needs")
    changes_p.add_argument("--all", action="store_true", help="select every job (push to main)")
    coverage_p = sub.add_parser("coverage", help="combine shard coverage; gate changed lines")
    coverage_p.add_argument("--shards", type=int, required=True)
    coverage_p.add_argument("--base", default=None, help="gate changed lines against this ref")
    coverage_p.add_argument("--summary", type=Path, default=None, help="append a Markdown report")
    durations_p = sub.add_parser("durations", help="per-file test seconds from JUnit reports")
    durations_p.add_argument("reports", nargs="+", type=Path)
    durations_p.add_argument("--output", type=Path, default=None, help="write this JSON file")
    orient_p = sub.add_parser("orient")
    orient_p.add_argument("--component")
    orient_p.add_argument("--json", action="store_true")
    sub.add_parser("lint-harness")
    sub.add_parser("baseline", help="rewrite .claude/harness-baseline.json from the tree")
    plan_p = sub.add_parser("plan-check")
    plan_p.add_argument("plan", help="docs/work/<task>/02-plan.md with a ```json front block")
    doctor_p = sub.add_parser("doctor")
    doctor_p.add_argument("--json", action="store_true")
    mutate_p = sub.add_parser("mutate")
    mutate_p.add_argument("modules", nargs="*", help="quant modules (default: changed in tree)")
    mutate_p.add_argument("--all", action="store_true", help="every quant-tier source module")
    mutate_p.add_argument("--json", action="store_true")
    mutate_p.add_argument("--write-baseline", action="store_true", help="record measured rates")
    mutate_p.add_argument("--timeout", type=float, default=1800.0, help="seconds per module")
    mutate_p.add_argument(
        "--require-measured",
        action="store_true",
        help="fail when a module cannot be measured (the pull-request gate)",
    )
    semgrep_p = sub.add_parser("semgrep")
    semgrep_p.add_argument("--changed", action="store_true", help="only changed .py files")
    sub.add_parser("determinism")
    raise_p = sub.add_parser("raise-cov")
    raise_p.add_argument("--fail", action="store_true", help="exit 1 on any uncovered raise")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "preflight":
        sys.dont_write_bytecode = True
        from gate_preflight import render_report, root_resolution_failure_report, run_preflight

        try:
            root = repo_root(timeout=10)
        except (OSError, subprocess.SubprocessError) as exc:
            code, report = root_resolution_failure_report(Path.cwd(), exc)
        else:
            code, report = run_preflight(root)
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_report(report))
        return code
    root = repo_root()
    if args.command in ("baseline", "plan-check"):
        _reexec_with_pydantic(root)
    if args.command == "check":
        return run_check(root, run_all=args.all, base=args.base)
    if args.command == "component":
        from gate_components import run_component

        if args.shard is not None and args.name != "backend-tests":
            print("--shard applies only to backend-tests", file=sys.stderr)
            return 2
        return run_component(root, args.name, shard=args.shard)
    if args.command == "coverage":
        from gate_components import run_coverage

        return run_coverage(root, shards=args.shards, base=args.base, summary=args.summary)
    if args.command == "durations":
        from gate_components import file_durations

        text = json.dumps({"seconds": file_durations(args.reports)}, indent=1, sort_keys=True)
        if args.output is None:
            print(text)
        else:
            args.output.write_text(text + "\n")
        return 0
    if args.command == "changes":
        from gate_components import ci_changes, comparison_context

        selected = ci_changes(root, comparison_context(root), run_all=args.all)
        # One `name=true|false` line each: the format GitHub reads from $GITHUB_OUTPUT.
        for name, needed in sorted(selected.items()):
            print(f"{name}={'true' if needed else 'false'}")
        return 0
    if args.command == "orient":
        from fs_orient import orientation, render_orientation

        payload = orientation(root, component=args.component)
        print(json.dumps(payload, sort_keys=True) if args.json else render_orientation(payload))
        return 0
    if args.command == "lint-harness":
        problems = lint_harness(root)
        for problem in problems:
            print(f"[harness-lint] FAIL {problem}", file=sys.stderr)
        if not problems:
            print("[harness-lint] ok — no guardrail regressions vs baseline")
        return 1 if problems else 0
    if args.command == "baseline":
        write_baseline(root)
        print(f"harness baseline rewritten at {BASELINE_FILE}; commit it for review.")
        return 0
    if args.command == "plan-check":
        from harness_awareness import plan_check

        ok, message = plan_check(Path(args.plan))
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    if args.command == "doctor":
        code, report = doctor(root)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
            return code
        for check_row in report["checks"]:
            marker = "ok " if check_row["ok"] else "FAIL"
            print(f"[doctor] {marker} {check_row['name']} — {check_row['detail']}")
        for line in format_machine_section(report["machine"]):
            print(line)
        return code
    if args.command == "mutate":
        from harness_quant import MUTATION_BASELINE_FILE, mutate, write_mutation_baseline

        modules = all_quant_source_modules(root) if args.all else (args.modules or None)
        code, report = mutate(
            root, modules, timeout=args.timeout, require_measured=args.require_measured
        )
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            for rel, entry in report["modules"].items():
                print(f"[mutate] {entry['status']:<8} {rel} {entry}")
            if not report["modules"]:
                print("[mutate] no quant-tier source modules to mutate")
        for rel, entry in report["modules"].items():
            status = str(entry.get("status", ""))
            if args.require_measured and status.startswith("unavailable:"):
                cause = status.removeprefix("unavailable:").strip() or "no output"
                print(
                    f"[mutate] FAIL {rel}: the mutation gate could not measure this module, so "
                    f"it cannot pass. Cause: {cause}",
                    file=sys.stderr,
                )
        if args.write_baseline:
            write_mutation_baseline(root, report)
            print(f"mutation baseline written at {MUTATION_BASELINE_FILE}; commit it for review.")
        return code
    if args.command == "semgrep":
        from harness_quant import semgrep

        return semgrep(root, changed_only=args.changed)
    if args.command == "determinism":
        from harness_quant import determinism

        ok, detail = determinism(root)
        print(f"[determinism] {'ok' if ok else 'FAIL'} {detail}")
        return 0 if ok else 1
    if args.command == "raise-cov":
        from harness_quant import raise_cov

        uncovered, total = raise_cov(root)
        for site in uncovered:
            print(f"[raise-cov] uncovered {site}")
        print(f"[raise-cov] {len(uncovered)} of {total} raise sites in quant modules unreached")
        return 1 if (args.fail and uncovered) else 0
    return 2  # pragma: no cover - argparse enforces choices


if __name__ == "__main__":
    raise SystemExit(main())
