"""Versioned content identity including the Python sources that execute a research run."""

from __future__ import annotations

import hashlib
import importlib.util
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from typing import TypedDict

from alpha_core import DataError

RUN_IDENTITY_VERSION = 3
_EXECUTION_PACKAGES = (
    "alpha_core",
    "alpha_data",
    "alpha_backtest",
    "alpha_strategies",
    "alpha_validation",
    "alpha_forecast",
    "alpha_cli",
)
_STRATEGY_MODULES = {
    "ts_momentum": "ts_momentum.py",
    "ma_crossover": "ma_crossover.py",
    "mean_reversion": "mean_reversion.py",
    "breakout": "breakout.py",
    "kronos": "signal_replay.py",
}


class RunIdentityFields(TypedDict):
    run_identity_version: int
    execution_fingerprint: str
    strategy_fingerprint: str | None
    source_fingerprint: str
    snapshot_hash: str | None


@dataclass(frozen=True, slots=True)
class RunIdentity:
    run_id: str
    execution_fingerprint: str
    strategy_fingerprint: str | None
    source_fingerprint: str
    snapshot_hash: str | None
    run_identity_version: int = RUN_IDENTITY_VERSION

    def manifest_fields(self) -> RunIdentityFields:
        return {
            "run_identity_version": self.run_identity_version,
            "execution_fingerprint": self.execution_fingerprint,
            "strategy_fingerprint": self.strategy_fingerprint,
            "source_fingerprint": self.source_fingerprint,
            "snapshot_hash": self.snapshot_hash,
        }


def _package_root(package: str) -> Path:
    spec = importlib.util.find_spec(package)
    if spec is None or not spec.submodule_search_locations:
        raise DataError(f"cannot fingerprint missing execution package {package!r}")
    return Path(next(iter(spec.submodule_search_locations)))


def _source_files(package: str) -> list[tuple[str, Path]]:
    root = _package_root(package)
    return [(f"{package}/{path.relative_to(root).as_posix()}", path) for path in root.rglob("*.py")]


def _digest_sources(files: Iterable[tuple[str, Path]], *, domain: str) -> str:
    digest = hashlib.sha256()
    digest.update(domain.encode("ascii") + b"\0")
    for label, path in sorted(files, key=lambda item: item[0]):
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise DataError(f"cannot read execution source {path}") from exc
        digest.update(label.encode("utf-8") + b"\0")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def execution_fingerprint() -> str:
    """Hash every ALPHA Python execution package, independent of installation path."""
    files = [item for package in _EXECUTION_PACKAGES for item in _source_files(package)]
    return _digest_sources(files, domain="project-alpha-execution-source-v1")


@cache
def strategy_fingerprint(strategy_name: str | None) -> str | None:
    """Hash the selected strategy plus its shared lifecycle/signal/sizing implementation."""
    if strategy_name is None:
        return None
    root = _package_root("alpha_strategies")
    selected = _STRATEGY_MODULES.get(strategy_name)
    filenames = ["base.py", "signals.py", "sizing.py"]
    if selected is not None:
        filenames.append(selected)
    files = [(f"alpha_strategies/{name}", root / name) for name in filenames]
    digest = hashlib.sha256()
    digest.update(b"project-alpha-strategy-source-v1\0")
    digest.update(strategy_name.encode("utf-8") + b"\0")
    digest.update(bytes.fromhex(_digest_sources(files, domain="strategy-files-v1")))
    return digest.hexdigest()


def strategy_name_from_payload(payload: Mapping[str, object]) -> str | None:
    value = payload.get("strategy_name", payload.get("strategy"))
    return value if isinstance(value, str) and value else None
