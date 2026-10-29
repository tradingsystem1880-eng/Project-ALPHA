"""Measure the explicitly installed closed rules profile before native admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alpha_cli._native_loop_admission import WORKER, WORKER_FILES
from alpha_core import DataError

RULE_ENV = WORKER / ".venv-rule-qualified"
RULE_FILES = ("rule_probe.py", "install_rule_profile.py", "rule-requirements.lock")
COSTED_FILES = (
    "rule_probe.py",
    "costed_probe.py",
    "install_rule_profile.py",
    "economics-requirements.lock",
)


def _files(root: Path, *, source: bool = False) -> dict[str, str]:
    if root.is_symlink():
        raise DataError("rule runtime root symlink is unsupported")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise DataError("rule runtime package symlink is unsupported")
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            if source:
                continue
            raise DataError("rule runtime contains unqualified bytecode")
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def measure_rule_environment(costed: bool = False) -> str:
    runtime = WORKER / (".venv-economics-qualified" if costed else ".venv-rule-qualified")
    if runtime.is_symlink():
        raise DataError("rule runtime requires a fresh isolated environment")
    profile_path = runtime / "rule-profile.json"
    if profile_path.is_symlink() or (runtime / "pyvenv.cfg").is_symlink():
        raise DataError("rule runtime metadata symlink is unsupported")
    profile = json.loads(profile_path.read_text())
    expected = {"alpha-core", "alpha-patterns", "alpha-strategies"}
    if costed:
        expected |= {"alpha-backtest", "alpha-data"}
    if set(profile.get("sources", {})) != expected or profile.get("profile") != (
        "costed" if costed else "positions"
    ):
        raise DataError("unknown fixed rule import profile")
    site = runtime / "lib/python3.12/site-packages"
    if profile.get("schema") != "AlphaRuleWorkerProfileV1" or _files(site) != profile.get(
        "site_files"
    ):
        raise DataError("installed rule runtime bytes changed")
    for name, expected in profile["sources"].items():
        package = WORKER.parents[1] / "packages" / name
        module = name.replace("-", "_")
        source_files = {
            "src/" + module + "/" + key: value
            for key, value in _files(package / "src" / module, source=True).items()
        }
        source_files["pyproject.toml"] = hashlib.sha256(
            (package / "pyproject.toml").read_bytes()
        ).hexdigest()
        if source_files != expected["source_files"]:
            raise DataError("rule source package bytes changed")
    if (
        hashlib.sha256(
            (
                WORKER / ("economics-requirements.lock" if costed else "rule-requirements.lock")
            ).read_bytes()
        ).hexdigest()
        != profile["requirements_sha256"]
    ):
        raise DataError("rule dependency lock changed")
    if (
        hashlib.sha256((WORKER.parents[1] / "uv.lock").read_bytes()).hexdigest()
        != profile["root_lock_sha256"]
    ):
        raise DataError("approved root dependency lock changed")
    identity = {
        "profile": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "python": hashlib.sha256((runtime / "bin/python").resolve().read_bytes()).hexdigest(),
        "pyvenv": hashlib.sha256((runtime / "pyvenv.cfg").read_bytes()).hexdigest(),
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def rule_implementation_fingerprints(costed: bool = False) -> dict[str, str | None]:
    from alpha_cli._native_rule_protocol import study_data_hash

    files = {
        name: hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
        for name in (*WORKER_FILES, *(COSTED_FILES if costed else RULE_FILES))
        if name.endswith(".py")
    }
    return {
        "code": hashlib.sha256(
            json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "dependency_lock": hashlib.sha256(
            (
                WORKER / ("economics-requirements.lock" if costed else "rule-requirements.lock")
            ).read_bytes()
        ).hexdigest(),
        "environment": measure_rule_environment(costed),
        "evaluator": hashlib.sha256(
            (WORKER / ("costed_probe.py" if costed else "rule_probe.py")).read_bytes()
        ).hexdigest(),
        "data": study_data_hash(costed),
    }
