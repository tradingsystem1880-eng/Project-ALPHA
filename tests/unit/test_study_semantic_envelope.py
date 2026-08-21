"""Verified server-side envelope tests for the S5a2 semantic read."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alpha_cli.study_semantic import VerifiedBlindSemanticReadV1
from alpha_core import DataError
from alpha_study import BlindSemanticProjectionV1


def _projection() -> BlindSemanticProjectionV1:
    return BlindSemanticProjectionV1(
        run_id="0123456789abcdef",
        acceptance_artifact_sha256="a" * 64,
        events_artifact_sha256="b" * 64,
        chart_data_artifact_sha256="c" * 64,
        cutoff_confirmed_at=datetime(2024, 1, 1, tzinfo=UTC),
        visible_points=(),
        masked_count=0,
    )


def test_verified_read_has_exact_keys_and_self_excluding_hash() -> None:
    value = VerifiedBlindSemanticReadV1(run_id="0123456789abcdef", projection=_projection())
    payload = value.to_dict()

    assert set(payload) == {
        "schema",
        "schema_version",
        "source_verification",
        "authority",
        "run_id",
        "projection",
        "content_sha256",
    }
    assert payload["source_verification"] == "verified_completed_d0_recomputation"
    assert payload["authority"] == "none"
    assert VerifiedBlindSemanticReadV1.from_dict(payload) == value


def test_verified_read_rejects_hash_or_outer_key_tampering() -> None:
    value = VerifiedBlindSemanticReadV1(run_id="0123456789abcdef", projection=_projection())
    payload = value.to_dict()
    payload["content_sha256"] = "f" * 64
    with pytest.raises(DataError, match="content_sha256"):
        VerifiedBlindSemanticReadV1.from_dict(payload)

    payload = value.to_dict()
    payload["extra"] = True
    with pytest.raises(DataError, match="keys are not exact"):
        VerifiedBlindSemanticReadV1.from_dict(payload)


def test_verified_read_rejects_mismatched_run_id() -> None:
    value = VerifiedBlindSemanticReadV1(run_id="0123456789abcdef", projection=_projection())
    payload = value.to_dict()
    payload["run_id"] = "fedcba9876543210"
    with pytest.raises(DataError, match="run_id"):
        VerifiedBlindSemanticReadV1.from_dict(payload)
