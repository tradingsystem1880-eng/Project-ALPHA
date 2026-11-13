"""Real offline setup fixtures for the dependency-free backend CI entrypoint."""

import json
import os
import re
import shlex
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def backend_command() -> list[str]:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    backend = workflow.split("  check:\n", 1)[1].split("  harness:\n", 1)[0]
    commands = [line.split("run: ", 1)[1] for line in backend.splitlines() if "run: " in line]
    assert commands == [
        "uv run --no-project --python 3.12 python scripts/gate.py component backend"
    ]
    return shlex.split(commands[0])


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "UV_OFFLINE": "1", "UV_PYTHON_DOWNLOADS": "never"}
    env.pop("VIRTUAL_ENV", None)
    bootstrap = root / ".alpha/bootstrap/bin"
    if bootstrap.exists():
        env["PATH"] = str(bootstrap) + os.pathsep + env["PATH"]
    return subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=60)


def wheel(root: Path, version: str) -> None:
    info = f"setup_probe-{version}.dist-info"
    files = {
        "setup_probe/__init__.py": f"VERSION = {version!r}\n",
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: setup-probe\nVersion: {version}\n",
        f"{info}/WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    files[f"{info}/RECORD"] = "".join(f"{name},,\n" for name in files)
    with zipfile.ZipFile(root / f"setup_probe-{version}-py3-none-any.whl", "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def project(root: Path, version: str) -> None:
    wheel(root, version)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "setup-fixture"\nversion = "0.0.0"\n'
        'requires-python = ">=3.12"\ndependencies = ["setup-probe"]\n'
        "[tool.uv.sources]\n"
        f'setup-probe = {{ path = "setup_probe-{version}-py3-none-any.whl" }}\n'
    )


@pytest.fixture
def setup_repo(tmp_path: Path) -> Path:
    from tests.unit._harness_support import git

    git(tmp_path, "init", "--quiet")
    (tmp_path / ".gitignore").write_text(".venv/\n.alpha/\n")
    result = run(tmp_path, "uv", "venv", "--python", "3.12", ".alpha/bootstrap")
    assert result.returncode == 0, result.stderr
    project(tmp_path, "1.0")
    result = run(tmp_path, "uv", "lock", "--python", "3.12")
    assert result.returncode == 0, result.stderr
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    # Exercise the actual workflow launcher and runner with real setup commands;
    # replace only the expensive post-setup checks with a dependency import probe.
    (scripts / "gate.py").write_text(
        "import importlib.util, json, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
        "import gate, gate_components\n"
        "root = Path.cwd()\n"
        "state = root / '.alpha/state'\nstate.mkdir(parents=True, exist_ok=True)\n"
        "(state / 'bootstrap.json').write_text(json.dumps({'venv_exists': "
        "(root / '.venv').exists(), 'python': sys.executable, "
        "'pydantic_available': importlib.util.find_spec('pydantic') is not None}))\n"
        "steps = gate_components.component_steps(root, 'backend', context={'paths': []})[:2]\n"
        "original_runner = gate._env_runner\n"
        "def runner(command, **kwargs):\n"
        "    result = original_runner(command, **kwargs)\n"
        "    if command == ['uv', 'lock', '--check'] and (state / 'lose-wheel').exists():\n"
        "        next(root.glob('*.whl')).unlink()\n"
        "    return result\n"
        "gate._env_runner = runner\n"
        "steps.append(('dependency probe', root, ['uv', 'run', '--locked', 'python', '-c', "
        '"import setup_probe; print(setup_probe.VERSION)"]))\n'
        "gate_components.component_steps = lambda *args, **kwargs: steps\n"
        "sys.exit(gate.main())\n"
    )
    return tmp_path


def launch(root: Path, *, success: bool) -> list[tuple[str, bool]]:
    """Run the CI backend entrypoint; return the (step, passed) lines it printed."""
    result = run(root, *backend_command())
    assert (result.returncode == 0) is success, result.stdout + result.stderr
    return [
        (match.group(1), match.group(2) == "PASS")
        for match in re.finditer(r"^\[gate:backend\] (.+): (PASS|FAIL) \(", result.stdout, re.M)
    ]


def test_backend_workflow_has_one_locked_setup_owner() -> None:
    backend_command()


def test_cold_warm_and_missing_dependency(setup_repo: Path) -> None:
    steps = launch(setup_repo, success=True)
    state = setup_repo / ".alpha/state/bootstrap.json"
    assert json.loads(state.read_text())["venv_exists"] is False
    assert json.loads(state.read_text())["pydantic_available"] is False
    assert [name for name, _ in steps] == ["uv lock", "uv sync", "dependency probe"]
    launch(setup_repo, success=True)
    assert json.loads(state.read_text())["venv_exists"] is True
    site = next((setup_repo / ".venv/lib").glob("python*/site-packages"))
    for path in site.glob("setup_probe*"):
        shutil.rmtree(path)
    launch(setup_repo, success=True)
    result = run(setup_repo, str(setup_repo / ".venv/bin/python"), "-c", "import setup_probe")
    assert result.returncode == 0, result.stderr


def test_changed_config_requires_updated_lock(setup_repo: Path) -> None:
    launch(setup_repo, success=True)
    project(setup_repo, "2.0")
    steps = launch(setup_repo, success=False)
    assert steps == [("uv lock", False)]
    result = run(setup_repo, "uv", "lock", "--python", "3.12")
    assert result.returncode == 0, result.stderr
    launch(setup_repo, success=True)
    result = run(
        setup_repo,
        str(setup_repo / ".venv/bin/python"),
        "-c",
        "import setup_probe; assert setup_probe.VERSION == '2.0'",
    )
    assert result.returncode == 0, result.stderr


def test_invalid_lock_stops_before_install(setup_repo: Path) -> None:
    (setup_repo / "uv.lock").write_text("invalid = [\n")
    steps = launch(setup_repo, success=False)
    assert steps == [("uv lock", False)]
    assert not (setup_repo / ".venv").exists()


def test_failed_sync_stops_before_checks(setup_repo: Path) -> None:
    state = setup_repo / ".alpha/state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lose-wheel").touch()
    steps = launch(setup_repo, success=False)
    assert steps == [("uv lock", True), ("uv sync", False)]
