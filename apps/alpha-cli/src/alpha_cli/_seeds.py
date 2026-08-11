"""Stable semantic seed derivation for independent stochastic components."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from alpha_core import DataError

_SEED_DOMAIN = b"project-alpha-semantic-seed-v1\0"


def semantic_seed(master: int, namespace: str) -> int:
    """Derive one unsigned 64-bit seed from ``master`` and a stable semantic namespace."""
    if not isinstance(master, int) or isinstance(master, bool):
        raise DataError(f"master seed must be an integer, got {master!r}")
    if not isinstance(namespace, str) or not namespace.strip():
        raise DataError("semantic seed namespace must be a non-empty string")
    payload = _SEED_DOMAIN + str(master).encode("ascii") + b"\0" + namespace.encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def semantic_seeds(master: int, namespaces: Sequence[str]) -> dict[str, int]:
    """Derive seeds keyed by name; ordering or inserting other names cannot shift a seed."""
    if len(set(namespaces)) != len(namespaces):
        raise DataError(f"duplicate semantic seed namespaces: {list(namespaces)!r}")
    return {namespace: semantic_seed(master, namespace) for namespace in namespaces}
