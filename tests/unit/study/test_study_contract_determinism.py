"""Cross-process and golden identity checks for study V1 contracts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alpha_research import ResearchArtifactRef
from alpha_study import (
    EventRowV1,
    EventTableV1,
    FeatureInputRefV1,
    FeatureValueV1,
)

ROOT = Path(__file__).parents[3]
HASH = "a" * 64
GOLDEN_TABLE_SHA256 = "24d162cd90911e01f21fc8842ef404de37aa8c3271fa984094e74cd8dbf841e6"
GOLDEN_BYTES_SHA256 = "e9be07ff3b444cfd6a6e95665f2c6853e2a283dc1416ec013285a3bbc25219cf"
GOLDEN_OPERATOR_SHA256 = "1e50b85c3c9f271661acd37b5acaa09ac38e61dad8cb0903cc02b762d5b6331f"
GOLDEN_OPERATOR_BYTES_SHA256 = "c8bb882774a36c3844059d296811ee5938d0a86119be535718117b24ffd41688"


def _event_table() -> EventTableV1:
    base = datetime(2026, 1, 1, 12, tzinfo=UTC)
    source = FeatureInputRefV1(
        artifact=ResearchArtifactRef("bars", "table", "application/json", HASH, 10, 1),
        input_available_at=base,
        snapshot_id="snapshot-1",
        snapshot_manifest_sha256=HASH,
        provider="tiingo",
        data_family="daily_bars",
        frequency="1d",
        venue="XNAS",
    )
    feature = FeatureValueV1(
        feature_id="geometry.depth",
        role="geometry",
        value=1.5,
        value_type="float",
        observed_at=base + timedelta(hours=1),
        available_at=base + timedelta(hours=3),
        vintage_at=base,
        vintage_id="v1",
        sources=(source,),
        computation_sha256=HASH,
        unit="ratio",
        venue="XNAS",
    )
    row = EventRowV1(
        study_id="study-1",
        entity_id="asset-1",
        asset_class="equity",
        instrument_id="XNAS:ABC",
        venue="XNAS",
        event_start=base,
        event_end=base + timedelta(hours=1),
        printed_at=base + timedelta(hours=2),
        confirmed_at=base + timedelta(hours=3),
        available_at=base + timedelta(hours=3),
        direction=1,
        operator_id="operator.one",
        operator_version="1.0.0",
        operator_code_sha256=HASH,
        parameter_sha256=HASH,
        features=(feature,),
        overlap_cluster_id=None,
        diagnostic_flags=(),
        parent_event_ids=(),
    )
    return EventTableV1("study-1", (row,))


def _subprocess_bytes(*, seed: str, timezone: str) -> bytes:
    code = (
        "import json; "
        "from tests.unit.study.test_study_contract_determinism import _event_table; "
        "print(json.dumps(_event_table().to_dict(), sort_keys=True, "
        "separators=(',', ':'), allow_nan=False))"
    )
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = seed
    environment["TZ"] = timezone
    return subprocess.check_output(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=environment,
    ).strip()


def _operator_subprocess_bytes(*, seed: str, timezone: str) -> bytes:
    code = (
        "import json; "
        "from alpha_study import OperatorRegistrationV1; "
        "value=OperatorRegistrationV1.from_registry('double_bottom.v1'); "
        "print(json.dumps(value.to_dict(), sort_keys=True, "
        "separators=(',', ':'), allow_nan=False))"
    )
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = seed
    environment["TZ"] = timezone
    return subprocess.check_output([sys.executable, "-c", code], cwd=ROOT, env=environment).strip()


def test_study_contract_identity_is_golden_and_environment_independent() -> None:
    utc_bytes = _subprocess_bytes(seed="1", timezone="UTC")
    brisbane_bytes = _subprocess_bytes(seed="999", timezone="Australia/Brisbane")

    assert utc_bytes == brisbane_bytes
    payload = json.loads(utc_bytes)
    assert payload["content_sha256"] == GOLDEN_TABLE_SHA256
    assert hashlib.sha256(utc_bytes).hexdigest() == GOLDEN_BYTES_SHA256


def test_registered_operator_identity_is_golden_and_environment_independent() -> None:
    utc_bytes = _operator_subprocess_bytes(seed="1", timezone="UTC")
    brisbane_bytes = _operator_subprocess_bytes(seed="999", timezone="Australia/Brisbane")

    assert utc_bytes == brisbane_bytes
    payload = json.loads(utc_bytes)
    assert payload["content_sha256"] == GOLDEN_OPERATOR_SHA256
    assert hashlib.sha256(utc_bytes).hexdigest() == GOLDEN_OPERATOR_BYTES_SHA256
