"""Extract [tool.importlinter] contracts — the authoritative architecture-DAG declarations.

The existing repo index records only contract *names*; Atlas keeps the full
source/forbidden module lists and any sanctioned ignore_imports exemptions.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from alpha_atlas.core.model import AtlasError, Evidence, Fragment, Node, Provenance
from alpha_atlas.generators._repo import record_input

EXTRACTOR = "importlinter"


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def extract(root: Path) -> tuple[Fragment, dict[str, str]]:
    pyproject = root / "pyproject.toml"
    inputs: dict[str, str] = {}
    raw = record_input(root, "pyproject.toml", inputs)
    data = tomllib.loads(raw.decode("utf-8"))
    try:
        contracts = data["tool"]["importlinter"]["contracts"]
    except KeyError as exc:
        raise AtlasError(f"no [tool.importlinter] contracts in {pyproject}") from exc
    nodes: list[Node] = []
    for contract in contracts:
        name = str(contract["name"])
        meta: dict[str, Any] = {
            "contract_type": "import_linter",
            "linter_type": contract.get("type"),
            "source_modules": _as_list(contract.get("source_modules")),
            "forbidden_modules": _as_list(contract.get("forbidden_modules")),
        }
        ignore_imports = _as_list(contract.get("ignore_imports"))
        if ignore_imports:
            meta["ignore_imports"] = ignore_imports
        nodes.append(
            Node(
                id=f"contract:{_slugify(name)}",
                kind="contract",
                label=name,
                path="pyproject.toml",
                evidence=Evidence(
                    level="declared",
                    provenance=[
                        Provenance(
                            extractor=EXTRACTOR,
                            source="pyproject.toml",
                            detail=f"[tool.importlinter] forbidden contract {name!r}",
                        )
                    ],
                ),
                meta=meta,
            )
        )
    return Fragment(nodes=nodes, edges=[]), inputs
