"""Fresh-only complete source installation for two closed synthetic import profiles.

No wheel, editable install, root path hook, or build backend is represented. Original
METADATA and Requires-Dist declarations are preserved; unresolved dependencies are explicit.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import json
import shutil
import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement

WORKER = Path(__file__).resolve().parent
ROOT = WORKER.parents[1]
PACKAGES = ("alpha-core", "alpha-patterns", "alpha-strategies")


def inventory(root: Path, *, ignore_cache: bool = False) -> dict[str, str]:
    if root.is_symlink():
        raise ValueError("source/profile root symlink")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"source/profile symlink: {path}")
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            if ignore_cache:
                continue
            raise ValueError(f"profile bytecode: {path}")
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> None:
    if sys.argv[1:] not in ([], ["--economics"]):
        raise ValueError("only the two closed profiles are installable")
    costed = bool(sys.argv[1:])
    env = WORKER / (".venv-economics-qualified" if costed else ".venv-rule-qualified")
    site = env / "lib/python3.12/site-packages"
    packages = PACKAGES + (("alpha-backtest", "alpha-data") if costed else ())
    if env.is_symlink() or not site.is_dir() or (env / "rule-profile.json").exists():
        raise ValueError("profile installation requires a fresh isolated environment")
    sources = {}
    for name in packages:
        module = name.replace("-", "_")
        source = ROOT / "packages" / name
        project = tomllib.loads((source / "pyproject.toml").read_text())["project"]
        dist = importlib.metadata.distribution(name)
        metadata = dist.read_text("METADATA")
        declared = sorted(str(Requirement(value)) for value in project["dependencies"])
        installed = sorted(str(Requirement(value)) for value in dist.requires or [])
        if (
            metadata is None
            or dist.metadata["Name"] != project["name"]
            or dist.version != project["version"]
            or dist.metadata["Requires-Python"] != project["requires-python"]
            or declared != installed
        ):
            raise ValueError(f"original package METADATA differs from source pyproject: {name}")
        files = {
            "src/" + module + "/" + key: value
            for key, value in inventory(source / "src" / module, ignore_cache=True).items()
        }
        files["pyproject.toml"] = hashlib.sha256(
            (source / "pyproject.toml").read_bytes()
        ).hexdigest()
        if (site / module).exists() or list(site.glob(module + "-*.dist-info")):
            raise ValueError("source installation is fresh-only; duplicate distribution rejected")
        shutil.copytree(
            source / "src" / module,
            site / module,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        info = site / (module + "-" + dist.version + ".dist-info")
        info.mkdir()
        (info / "METADATA").write_text(metadata)
        (info / "INSTALLER").write_text("alpha-closed-source-profile-v1\n")
        sources[name] = {
            "source_files": files,
            "metadata_sha256": hashlib.sha256(metadata.encode()).hexdigest(),
        }
    distributions = list(importlib.metadata.distributions(path=[str(site)]))
    names = [str(d.metadata["Name"]).lower().replace("_", "-") for d in distributions]
    if len(names) != len(set(names)):
        raise ValueError("duplicate installed distribution metadata")
    versions = {str(d.metadata["Name"]).lower().replace("_", "-"): d.version for d in distributions}
    for name in packages:
        info = site / (name.replace("-", "_") + "-1.0.0.dist-info")
        requirements = importlib.metadata.Distribution.at(info).requires or []
        missing = []
        for value in requirements:
            req = Requirement(value)
            if req.marker is not None and not req.marker.evaluate({"extra": ""}):
                continue
            version = versions.get(req.name.lower().replace("_", "-"))
            if version is None or version not in req.specifier:
                missing.append(value)
        provenance = {
            "schema": "AlphaRuleSourceInstallV1",
            "source": str(ROOT / "packages" / name),
            "complete_package_source": True,
            "build_backend_invoked": False,
            "installation_format": "source-with-metadata",
            "qualified_imports": ["alpha_strategies.rules"]
            if not costed
            else [
                "alpha_backtest.engine",
                "alpha_backtest.feed",
                "alpha_backtest.instruments",
                "alpha_strategies.rule_strategy",
            ],
            "full_dependencies_satisfied": not missing,
            "unresolved_declared_dependencies": missing,
            "full_package_api_qualified": False,
            "source_files": sources[name]["source_files"],
        }
        (info / "PROFILE.json").write_text(json.dumps(provenance, sort_keys=True))
        record = info / "RECORD"
        paths = [
            p
            for folder in (site / name.replace("-", "_"), info)
            for p in folder.rglob("*")
            if p.is_file()
        ]
        with record.open("w", newline="") as handle:
            writer = csv.writer(handle)
            for path in sorted(paths):
                raw = path.read_bytes()
                digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
                writer.writerow((str(path.relative_to(site)), "sha256=" + digest, len(raw)))
            writer.writerow((str(record.relative_to(site)), "", ""))
    if sorted(p.name for p in site.glob("*.pth")) != ["_virtualenv.pth"]:
        raise ValueError("unexpected editable/site hook")
    lock = WORKER / ("economics-requirements.lock" if costed else "rule-requirements.lock")
    profile = {
        "schema": "AlphaRuleWorkerProfileV1",
        "profile": "costed" if costed else "positions",
        "sources": sources,
        "site_files": inventory(site),
        "requirements_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "root_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
    }
    (env / "rule-profile.json").write_text(
        json.dumps(profile, sort_keys=True, separators=(",", ":"))
    )


if __name__ == "__main__":
    main()
