"""Semantic seed namespaces do not shift when validation gates are inserted or reordered."""

from __future__ import annotations

import pytest

from alpha_cli._seeds import semantic_seed, semantic_seeds
from alpha_core import DataError


def test_semantic_seed_is_stable_and_namespace_sensitive() -> None:
    assert semantic_seed(7, "validation.tier1_null") == semantic_seed(7, "validation.tier1_null")
    assert semantic_seed(7, "validation.tier1_null") != semantic_seed(7, "validation.tier2_null")
    assert semantic_seed(7, "validation.tier1_null") != semantic_seed(8, "validation.tier1_null")


def test_inserting_or_reordering_a_namespace_does_not_shift_existing_seeds() -> None:
    original = semantic_seeds(7, ["tier1", "tier2", "sharpe_ci"])
    expanded = semantic_seeds(7, ["new_gate", "sharpe_ci", "tier2", "tier1"])
    assert {name: expanded[name] for name in original} == original


def test_semantic_seed_rejects_invalid_or_duplicate_namespaces() -> None:
    with pytest.raises(DataError, match="namespace"):
        semantic_seed(7, "")
    with pytest.raises(DataError, match="duplicate"):
        semantic_seeds(7, ["tier1", "tier1"])
