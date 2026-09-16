"""Import built wheels outside the checkout without replacing editable installs."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

IMPORT_PROBE = """
import importlib, pathlib, sys
target = pathlib.Path(sys.argv[1]).resolve()
for name in sys.argv[2:]:
    module = importlib.import_module(name)
    origin = pathlib.Path(module.__file__).resolve()
    assert origin.is_relative_to(target), (name, str(origin), str(target))
    assert module.__version__ == '1.0.0', (name, module.__version__)
    print(name, origin)
"""


def workspace_modules(root: Path) -> list[str]:
    config = tomllib.loads((root / "pyproject.toml").read_text())
    members = config["tool"]["uv"]["workspace"]["members"]
    modules = []
    for pattern in members:
        for member in sorted(root.glob(pattern)):
            manifest = member / "pyproject.toml"
            if manifest.is_file():
                project = tomllib.loads(manifest.read_text())["project"]
                modules.append(str(project["name"]).replace("-", "_"))
    return sorted(modules)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    modules = workspace_modules(root)
    wheels = []
    for module in modules:
        matches = list((root / "dist").glob(f"{module}-1.0.0-*.whl"))
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one built wheel for {module}: {matches}")
        wheels.append(str(matches[0]))
    with tempfile.TemporaryDirectory(prefix="alpha-wheel-smoke-") as temporary:
        target = Path(temporary) / "installed"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                "--target",
                str(target),
                "--no-deps",
                *wheels,
            ],
            check=True,
            cwd=temporary,
        )
        env = {**os.environ, "PYTHONPATH": str(target)}
        subprocess.run(
            [sys.executable, "-c", IMPORT_PROBE, str(target), *modules],
            check=True,
            cwd=temporary,
            env=env,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
