"""Closed, Git-owned operator declarations for alpha-study."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

DOUBLE_BOTTOM_V1: Final = MappingProxyType(
    {
        "availability_rule_sha256": (
            "17269facf1ad0f432467809e9939d961628c84ffbeba49c858ad361cee80a407"
        ),
        "compatible_analysis_families": ("event_study",),
        "dedup_rule_sha256": "c9bb095d66c41256817233294855ef287bcd4cd5111be54f8b484ec97841f12e",
        "dependency_lock_sha256": (
            "b5251e188f0e90db3eb4dfd0858759c1b48fafd683be8b36571bc85e52afe17b"
        ),
        "description": "Existing causal, greedy, non-overlapping double-bottom detector.",
        "environment_sha256": "1b560c0f7dcf21491e7f107c227cbd6a64500df3dce3f581a7ae81ed85b3826d",
        "implementation_code_sha256": (
            "8e61b14451737654aebad51bc29e57cc256d33e03543c4b34b1ce521b367949f"
        ),
        "implementation_git_commit": "678ce412e6dfc8d2f348633565979fd5e106bebe",
        "implementation_module": "alpha_research.patterns",
        "implementation_symbol": "detect_double_bottom_events",
        "kind": "python",
        "operator_id": "double_bottom.v1",
        "operator_version": "1.0.0",
        "output_schema": "EventTableV1",
        "overlap_rule_sha256": "78eeff0894226b2504f86cd03769936cadff2c111fe9abc999aaebb60d278783",
        "parameter_schema_sha256": (
            "e44f03fed605bb61cae7006569bb235614e972b5c9ae091bde1f6202b26a2043"
        ),
        "registry_path": "packages/alpha-study/src/alpha_study/_operator_registry.py",
        "required_fields": ("available_at", "end", "high", "low"),
        "supported_asset_classes": ("asset_agnostic",),
    }
)

OPERATOR_REGISTRY_V1: Final = MappingProxyType({"double_bottom.v1": DOUBLE_BOTTOM_V1})

__all__ = ["OPERATOR_REGISTRY_V1"]
