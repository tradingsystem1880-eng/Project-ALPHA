"""Closed development probe, invoked only in a fresh sanitized fixture subprocess."""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

WORKER = Path(__file__).resolve().parent
WORKER_MODULES = {
    "source_pin",
    "conformance",
    "native_fixture",
    "fixture_owner",
    "admitted_probe",
    "rule_probe",
    "costed_probe",
}

ALLOWED_MODULES = {
    "rdagent",
    "rdagent.core",
    "rdagent.core.conf",
    "rdagent.core.serialization",
    "rdagent.oai",
    "rdagent.oai.llm_conf",
    "rdagent.core.utils",
    "rdagent.log.base",
    "rdagent.log.conf",
    "rdagent.log.utils",
    "rdagent.log.storage",
    "rdagent.log.logger",
    "rdagent.log",
    "rdagent.core.exception",
    "rdagent.utils.agent.workflow",
    "rdagent.utils.agent",
    "rdagent.utils.agent.tpl",
    "rdagent.utils",
    "rdagent.log.timer",
    "rdagent.utils.workflow.tracking",
    "rdagent.utils.workflow.loop",
    "rdagent.utils.workflow.misc",
    "rdagent.utils.workflow",
    "rdagent.core.evaluation",
    "rdagent.core.experiment",
    "rdagent.core.scenario",
    "rdagent.core.proposal",
    "rdagent.core.knowledge_base",
}


class _ImportBoundary(importlib.abc.MetaPathFinder):
    def __init__(self, source: Path) -> None:
        self.source = source

    def find_spec(
        self, fullname: str, path: Sequence[str] | None = None, target: ModuleType | None = None
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname in WORKER_MODULES:
            file = WORKER / f"{fullname}.py"
            if file.is_symlink():
                raise ImportError(f"worker helper must be a reviewed source file: {fullname}")
            return importlib.util.spec_from_file_location(fullname, file)
        if fullname == "rdagent":
            # The pinned upstream root is a namespace package. Bind only its verified directory;
            # never expose the surrounding external source root as a general import search path.
            spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = [str(self.source / "rdagent")]
            return spec
        if fullname.startswith("rdagent."):
            if fullname not in ALLOWED_MODULES:
                raise ImportError(f"outside fixed native import closure: {fullname}")
            parent = self.source.joinpath(*fullname.split(".")[:-1])
            upstream_spec = importlib.machinery.PathFinder.find_spec(fullname, [str(parent)])
            if upstream_spec is None:
                raise ImportError(f"missing pinned upstream module: {fullname}")
            return upstream_spec
        return None


def _reject_source_root_shadows(source: Path) -> None:
    for entry in source.iterdir():
        if entry == source / "rdagent":
            continue
        if entry.is_dir():
            name = entry.name
        elif entry.suffix in {".py", ".pyc", ".so", ".pyd"}:
            name = entry.name.split(".", 1)[0]
        else:
            continue
        if (
            name in WORKER_MODULES | {"rdagent"} | sys.stdlib_module_names
            or importlib.machinery.PathFinder.find_spec(name) is not None
        ):
            raise ValueError(f"unpinned source-root import shadow: {entry.name}")


def _no_external_effects(event: str, args: tuple[Any, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
        raise RuntimeError(f"external effect disabled in fixture: {event}")


def main() -> None:
    admitted = len(sys.argv) == 4 and sys.argv[2] == "admitted"
    if not admitted and (
        len(sys.argv) != 3
        or sys.argv[2]
        not in {
            "SUPPORTED",
            "CONTRADICTED",
            "INCONCLUSIVE",
            "INVALID",
            "resume",
            "cancel",
            "tamper",
            "zero_allowance",
            "partial_allowance",
            "unguarded",
            "post_effect_step_n",
        }
    ):
        raise ValueError("unknown closed fixture probe")
    root = Path.cwd()
    if admitted:
        if (
            root.parent.parent != Path(tempfile.gettempdir())
            or not root.parent.name.startswith("alpha-native-fixture-")
            or not root.name.startswith("payload-")
            or (root.parent / "synthetic-only").read_text()
            != "ALPHA synthetic native lifecycle v1\n"
        ):
            raise ValueError("admitted probe requires its synthetic owner workspace")
    elif root.parent != Path(tempfile.gettempdir()) or not root.name.startswith(
        "alpha-rdagent-conformance-"
    ):
        raise ValueError("probe requires a new disposable fixture directory")
    if list(root.iterdir()):
        raise ValueError("probe fixture directory must start empty")
    source = Path(sys.argv[1]).resolve()
    # No inherited settings, credentials, user home, dotenv, caches or signing key.
    os.environ.clear()
    os.environ.update(
        {
            "HOME": str(root),
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "ARTIFACT_SIGNING_KEY_PATH": str(root / "synthetic.key"),
            "LOG_TRACE_PATH": str(root / "logs"),
        }
    )
    # This must precede source_pin and every other local helper import too.
    sys.pycache_prefix = str(root / "bytecode")
    sys.meta_path.insert(0, _ImportBoundary(source))
    sys.addaudithook(_no_external_effects)
    from source_pin import ARCHIVE_SHA256, COMMIT, SOURCE_SHA256, verify_source

    source_sha = verify_source(source)
    _reject_source_root_shadows(source)
    from conformance import probe

    if admitted:
        from admitted_probe import probe as admitted_probe

        result = admitted_probe(json.loads(sys.argv[3]))
    else:
        result = probe(sys.argv[2])
    imported = {}
    imported_worker = {}
    for name in WORKER_MODULES:
        if name not in sys.modules:
            continue
        file = Path(sys.modules[name].__file__ or "")
        if file != WORKER / f"{name}.py":
            raise RuntimeError(f"worker helper origin mismatch: {name}")
        imported_worker[name] = hashlib.sha256(file.read_bytes()).hexdigest()
    for name, module in tuple(sys.modules.items()):
        if name == "rdagent" or name.startswith("rdagent."):
            if name not in ALLOWED_MODULES:
                raise RuntimeError(f"unexpected upstream module: {name}")
            path = getattr(module, "__file__", None)
            if path:
                file = Path(path)
                imported[str(file.relative_to(source))] = hashlib.sha256(
                    file.read_bytes()
                ).hexdigest()
    result.update(
        {
            # Commit and archive are pinned expectations; only the source tree is measured here.
            "source_pin": {
                "expected": {
                    "commit": COMMIT,
                    "archive_sha256": ARCHIVE_SHA256,
                    "source_tree_sha256": SOURCE_SHA256,
                },
                "verified": {"source_tree_sha256": source_sha},
                "not_verified": ["commit", "archive_sha256"],
            },
            "source_tree_sha256": source_sha,
            "imported_source_sha256": imported,
            "imported_worker_sha256": imported_worker,
            "dependencies": {
                dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()
            },
            "authority": "none",
            "synthetic": True,
        }
    )
    if verify_source(source) != source_sha:
        raise RuntimeError("source tree changed during execution")
    (root / "receipt.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
