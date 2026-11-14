"""The local RD-Agent setup script refuses a wrong supplied checkout before installing anything."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/setup_rdagent.sh"


def test_script_parses() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_unpinned_supplied_checkout_is_refused_before_any_install(tmp_path: Path) -> None:
    root = tmp_path / "checkout with spaces"
    (root / "scripts").mkdir(parents=True)
    shutil.copyfile(SCRIPT, root / "scripts/setup_rdagent.sh")
    pristine = tmp_path / "pristine"
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "init", "--quiet", str(pristine)], check=True)
    (pristine / "README.md").write_text("not the pinned commit\n")
    subprocess.run([*git, "-C", str(pristine), "add", "README.md"], check=True)
    subprocess.run([*git, "-C", str(pristine), "commit", "--quiet", "-m", "x"], check=True)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    log = tmp_path / "uv.log"
    uv = binaries / "uv"
    record = f"import sys\nopen({str(log)!r}, 'a').write(' '.join(sys.argv))\n"
    uv.write_text(f"#!{sys.executable}\n{record}")
    uv.chmod(0o755)
    env = {key: value for key, value in os.environ.items() if not key.startswith("ALPHA_")} | {
        "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}",
        "ALPHA_RDAGENT_PRISTINE": str(pristine),
        "ALPHA_RDAGENT_SOURCE": str(tmp_path / "derived"),
    }
    completed = subprocess.run(
        ["bash", str(root / "scripts/setup_rdagent.sh")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "is not the unmodified pinned commit" in completed.stderr
    assert not log.exists()  # no uv sync, venv or package install ran
    assert not (tmp_path / "derived").exists()
    assert not (root / ".alpha").exists()


def test_unknown_option_is_refused_before_any_install(tmp_path: Path) -> None:
    completed = subprocess.run(
        ["bash", str(SCRIPT), "--with-everything"],
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if not key.startswith("ALPHA_")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "unknown option --with-everything" in completed.stderr


def test_stock_lock_is_exact_hashed_and_follows_upstream_constraints() -> None:
    import importlib.util

    worker = SCRIPT.parents[1] / "workers/rdagent"
    spec = importlib.util.spec_from_file_location(
        "install_stock_profile", worker / "install_stock_profile.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lock = (worker / "stock-requirements.lock").read_text()
    pins = module.locked_pins(lock)
    assert len(pins) == 60
    for name, version in {"litellm": "1.97.0", "dill": "0.3.9", "psutil": "6.1.0"}.items():
        assert pins[name] == version
    upstream_imports = {"docker", "rich", "numpy", "openai", "tiktoken", "pydantic-settings"}
    assert upstream_imports <= set(pins)
    assert not {"pandas", "scikit-learn", "torch"} & set(pins)


def test_factor_setup_is_opt_in_and_uses_closed_profile() -> None:
    text = SCRIPT.read_text()
    assert "--with-factor-runtime) with_factor=1" in text
    assert "with_factor=0" in text
    assert "rdagent-factor-py311.incomplete" in text
    assert "rdagent-factor-py311.built-$stamp" in text
    assert "-r workers/rdagent/factor-requirements.lock" in text
    assert 'install_stock_profile.py --profile factor "$bundle"' in text
    assert 'install_stock_profile.py --profile factor --verify "$bundle"' in text
    assert "export ALPHA_FACTOR_PYTHON=%q" in text
