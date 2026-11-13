"""Record and re-check the closed stock RDLoop runtime bundle built from stock-requirements.lock.

The bundle is the layout ``StockFixtureLaunch`` measures: ``<bundle>/venv/bin/python``,
``<bundle>/venv/pyvenv.cfg`` and ``<bundle>/dependencies.lock.txt``. This helper never installs or
downloads anything; ``scripts/setup_rdagent.sh --with-stock-runtime`` installs the lock with
``uv pip install --require-hashes --no-deps`` first. It then proves the installed distributions
are exactly the locked ones (no extra, missing or different versions), copies the lock bytes into
the bundle and writes ``stock-profile.json`` with an inventory digest of every installed file.
``--verify`` repeats the checks against that profile and prints the identity digest.

This measures a runtime; it grants no launch, inference, admission or qualification authority.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import sys
from pathlib import Path

WORKER = Path(__file__).resolve().parent
LOCK = WORKER / "stock-requirements.lock"
SCHEMA = "AlphaStockRuntimeProfileV1"
PYTHON = "3.11"
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)\s")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def locked_pins(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        match = _PIN.match(line)
        if match is None or "--hash=sha256:" not in line:
            raise ValueError(f"stock lock line is not an exact hashed pin: {line[:60]}")
        name = _normalize(match[1])
        if name in pins:
            raise ValueError(f"duplicate stock lock pin: {name}")
        pins[name] = match[2]
    return pins


def _inventory(site: Path) -> dict[str, str]:
    result = {}
    for path in sorted(site.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"stock runtime symlink: {path}")
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue  # the fixture selects a fresh bytecode cache; bytecode is not identity
        if path.is_file():
            result[str(path.relative_to(site))] = _sha(path.read_bytes())
    return result


def measure(bundle: Path) -> dict[str, object]:
    if bundle.is_symlink() or bundle != bundle.resolve() or not bundle.is_dir():
        raise ValueError("stock runtime bundle must be a canonical directory")
    venv = bundle / "venv"
    config = (venv / "pyvenv.cfg").read_text()
    version = re.search(r"^version_info\s*=\s*(\S+)$", config, re.M) or re.search(
        r"^version\s*=\s*(\S+)$", config, re.M
    )
    if version is None or not version[1].startswith(PYTHON + "."):
        raise ValueError(f"stock runtime must be CPython {PYTHON}")
    site = venv / "lib" / f"python{PYTHON}" / "site-packages"
    lock = LOCK.read_bytes()
    pins = locked_pins(lock.decode())
    installed: dict[str, str] = {}
    for dist in importlib.metadata.distributions(path=[str(site)]):
        name = _normalize(dist.metadata["Name"])
        if name in installed:
            raise ValueError(f"duplicate installed distribution: {name}")
        installed[name] = dist.version
    if installed != pins:
        extra = sorted(set(installed) - set(pins))
        missing = sorted(set(pins) - set(installed))
        changed = sorted(n for n in set(pins) & set(installed) if pins[n] != installed[n])
        raise ValueError(f"stock runtime differs from lock: {extra=} {missing=} {changed=}")
    files = _inventory(site)
    return {
        "schema": SCHEMA,
        "python": version[1],
        "lock_sha256": _sha(lock),
        "distributions": len(installed),
        "site_sha256": _sha(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()),
    }


def identity(profile: dict[str, object]) -> str:
    return _sha(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode())


def _write_exclusive(path: Path, data: bytes) -> None:
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError(f"{path.name} already exists with different bytes; refusing overwrite")
        return
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "wb") as stream:
        stream.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    bundle = args.bundle.absolute()
    try:
        profile = measure(bundle)
        rendered = (json.dumps(profile, sort_keys=True, indent=2) + "\n").encode()
        if args.verify:
            if (bundle / "dependencies.lock.txt").read_bytes() != LOCK.read_bytes():
                raise ValueError("bundle dependencies.lock.txt differs from the committed lock")
            if (bundle / "stock-profile.json").read_bytes() != rendered:
                raise ValueError("stock runtime changed since its profile was recorded")
        else:
            _write_exclusive(bundle / "dependencies.lock.txt", LOCK.read_bytes())
            _write_exclusive(bundle / "stock-profile.json", rendered)
    except (OSError, ValueError) as error:
        print(f"install-stock-profile: {error}", file=sys.stderr)
        return 1
    print(identity(profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
