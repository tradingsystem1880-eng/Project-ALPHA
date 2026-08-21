"""S3a lineage and feature-value contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Literal, cast

import pytest

from alpha_core import DataError
from alpha_research import ResearchArtifactRef
from alpha_study import FeatureInputRefV1, FeatureValueV1

Scalar = bool | int | float | str
Role = Literal["geometry", "state", "factor"]
ValueType = Literal["bool", "int", "float", "str"]

HASH = "a" * 64
BASE = datetime(2026, 1, 1, 12, tzinfo=UTC)


def artifact() -> ResearchArtifactRef:
    return ResearchArtifactRef("bars", "table", "application/json", HASH, 10, 1)


def source(*, available_at: datetime = BASE) -> FeatureInputRefV1:
    return FeatureInputRefV1(
        artifact=artifact(),
        input_available_at=available_at,
        snapshot_id="snapshot-1",
        snapshot_manifest_sha256=HASH,
        provider="tiingo",
        data_family="daily_bars",
        frequency="1d",
        venue="XNAS",
    )


def value(
    *,
    observed_at: datetime = BASE,
    available_at: datetime = BASE + timedelta(hours=1),
    vintage_at: datetime = BASE,
    scalar: object = 1.5,
    value_type: str = "float",
) -> FeatureValueV1:
    return FeatureValueV1(
        feature_id="feature.atr_20",
        role="state",
        value=cast(Scalar, scalar),
        value_type=cast(ValueType, value_type),
        observed_at=observed_at,
        available_at=available_at,
        vintage_at=vintage_at,
        vintage_id="v1",
        sources=(source(),),
        computation_sha256=HASH,
        unit="ratio",
        venue="XNAS",
    )


def test_exact_round_trip_preserves_nested_research_artifact() -> None:
    original = value()
    assert FeatureValueV1.from_dict(original.to_dict()) == original
    assert FeatureInputRefV1.from_dict(original.sources[0].to_dict()) == original.sources[0]
    assert original.sources[0].artifact == artifact()


def test_timezone_equivalent_inputs_have_equal_identity() -> None:
    shifted = value(
        observed_at=BASE.astimezone(timezone(timedelta(hours=-4))),
        available_at=(BASE + timedelta(hours=1)).astimezone(timezone(timedelta(hours=-4))),
        vintage_at=BASE.astimezone(timezone(timedelta(hours=-4))),
    )
    assert shifted.content_sha256 == value().content_sha256
    assert shifted.sources[0].content_sha256 == value().sources[0].content_sha256
    assert str(shifted.to_dict()["available_at"]).endswith("Z")


def test_tamper_unknown_missing_and_hash_errors_fail_closed() -> None:
    original = value()
    tampered = original.to_dict()
    tampered["value"] = 9.0
    with pytest.raises(DataError):
        FeatureValueV1.from_dict(tampered)

    unknown = original.to_dict()
    unknown["operational_timestamp"] = BASE.isoformat()
    with pytest.raises(DataError):
        FeatureValueV1.from_dict(unknown)

    missing = original.to_dict()
    del missing["sources"]
    with pytest.raises(DataError):
        FeatureValueV1.from_dict(missing)

    bad_hash = original.to_dict()
    bad_hash["computation_sha256"] = "f" * 64
    with pytest.raises(DataError):
        FeatureValueV1.from_dict(bad_hash)

    bad_source_hash = original.sources[0].to_dict()
    bad_source_hash["content_sha256"] = "f" * 64
    with pytest.raises(DataError):
        FeatureInputRefV1.from_dict(bad_source_hash)


@pytest.mark.parametrize("scalar", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_scalars_fail(scalar: float) -> None:
    with pytest.raises(DataError):
        value(scalar=scalar)


def test_naive_and_causal_clock_errors_fail() -> None:
    with pytest.raises(DataError):
        value(observed_at=datetime(2026, 1, 1, 12))
    with pytest.raises(DataError):
        value(available_at=BASE - timedelta(seconds=1))
    with pytest.raises(DataError):
        value(vintage_at=BASE + timedelta(days=1))
    with pytest.raises(DataError):
        FeatureValueV1(
            feature_id="feature.bad",
            role="state",
            value=1.0,
            value_type="float",
            observed_at=BASE,
            available_at=BASE + timedelta(hours=1),
            vintage_at=BASE,
            vintage_id="v1",
            sources=(source(available_at=BASE + timedelta(hours=2)),),
            computation_sha256=HASH,
            unit="ratio",
            venue="XNAS",
        )


def test_scalar_types_are_stable_and_contract_is_frozen() -> None:
    boolean = value(scalar=True, value_type="bool")
    integer = value(scalar=1, value_type="int")
    assert boolean.content_sha256 != integer.content_sha256
    assert boolean.computation_sha256 == integer.computation_sha256 == HASH
    with pytest.raises(DataError):
        value(scalar=True, value_type="int")
    with pytest.raises(FrozenInstanceError):
        boolean.role = "geometry"  # type: ignore[misc]


def test_roles_unit_venue_and_nonempty_strings_are_closed() -> None:
    for role in ("geometry", "state", "factor"):
        assert replace(value(), role=role).role == role
    with pytest.raises(DataError):
        replace(value(), role=cast(Role, "unknown"))
    with pytest.raises(DataError):
        replace(value(), role=cast(Role, {}))
    with pytest.raises(DataError):
        replace(value(), feature_id="")
    with pytest.raises(DataError):
        replace(value(), unit="")
    with pytest.raises(DataError):
        value(scalar="", value_type="str")


def test_semantic_lineage_changes_content_not_computation_identity() -> None:
    original = value()
    changed = replace(original, vintage_id="v2")

    assert changed.content_sha256 != original.content_sha256
    assert changed.computation_sha256 == original.computation_sha256
    assert changed.content_sha256 != changed.sources[0].content_sha256


def test_sources_are_nonempty_canonical_and_explicitly_unverified() -> None:
    original = value()
    assert original.to_dict()["lineage_verification"] == "unverified_reference"
    with pytest.raises(DataError):
        replace(original, sources=())
    with pytest.raises(DataError):
        replace(original, sources=(original.sources[0], original.sources[0]))
    claimed = original.to_dict()
    claimed["lineage_verification"] = "verified"
    with pytest.raises(DataError):
        FeatureValueV1.from_dict(claimed)
