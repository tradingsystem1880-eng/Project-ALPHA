"""Verified server-side envelope tests for the S5a2 semantic read."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

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


def test_verified_read_rejects_invalid_envelope_contract_fields() -> None:
    projection = _projection()

    with pytest.raises(DataError, match="string-keyed mapping"):
        VerifiedBlindSemanticReadV1.from_dict(cast(Mapping[str, object], []))
    with pytest.raises(DataError, match="lowercase 16-character hex"):
        VerifiedBlindSemanticReadV1(run_id="not-a-run-id", projection=projection)
    with pytest.raises(DataError, match="projection must be"):
        VerifiedBlindSemanticReadV1(
            run_id="0123456789abcdef",
            projection=cast(BlindSemanticProjectionV1, {}),
        )
    with pytest.raises(DataError, match="source_verification is fixed"):
        VerifiedBlindSemanticReadV1(
            run_id="0123456789abcdef",
            projection=projection,
            source_verification="claimed_without_recomputation",
        )
    with pytest.raises(DataError, match="has no authority"):
        VerifiedBlindSemanticReadV1(
            run_id="0123456789abcdef",
            projection=projection,
            authority="execution",
        )

    payload = VerifiedBlindSemanticReadV1(
        run_id="0123456789abcdef", projection=projection
    ).to_dict()
    payload["run_id"] = " padded "
    with pytest.raises(DataError, match="canonical text"):
        VerifiedBlindSemanticReadV1.from_dict(payload)

    payload = VerifiedBlindSemanticReadV1(
        run_id="0123456789abcdef", projection=projection
    ).to_dict()
    payload["content_sha256"] = "not-a-hash"
    with pytest.raises(DataError, match="64-character SHA-256"):
        VerifiedBlindSemanticReadV1.from_dict(payload)

    payload = VerifiedBlindSemanticReadV1(
        run_id="0123456789abcdef", projection=projection
    ).to_dict()
    payload["schema_version"] = 2
    with pytest.raises(DataError, match="unsupported .* schema"):
        VerifiedBlindSemanticReadV1.from_dict(payload)
