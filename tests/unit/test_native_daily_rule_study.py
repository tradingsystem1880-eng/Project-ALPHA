"""Artificial identity fixtures; no market study, approval, or launch acceptance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from alpha_cli._native_daily_rule_study import (
    DailyRuleEconomicsV1,
    DailyRuleResourcesV1,
    DailyRuleStudyV1,
    bind_daily_study,
    daily_rule_terms_proposal,
    momentum20_rule,
)
from alpha_cli._native_loop_admission import NativeLaunch
from alpha_cli._native_rule_protocol import validate_rule_plan
from alpha_cli._native_rule_study import SyntheticRuleStudy
from alpha_core import DataError
from alpha_strategies.rules import rule_signal, rule_spec_from_json
from tests.unit.test_crypto_price_snapshot_query import _full_discovery_query


def _study(tmp_path: Path) -> DailyRuleStudyV1:
    query = _full_discovery_query(tmp_path)
    economics, resources = daily_rule_terms_proposal()
    return bind_daily_study(
        query,
        snapshot_sha256=query.snapshot_id,
        runtime_profile_sha256="a" * 64,
        container_image_id="sha256:" + "c" * 64,
        storage_config_sha256="b" * 64,
        data_origin="artificial_fixture",
        economics=economics,
        resources=resources,
    )


def test_exact_twenty_day_rule_has_hand_specified_chronology() -> None:
    spec = rule_spec_from_json(momentum20_rule())
    # Compare 21st/22nd/23rd close with first/second/third: positive, equal, negative.
    closes = [10.0] * 20 + [11.0, 10.0, 9.0]
    assert [
        rule_signal(
            spec, [x + 1 for x in closes[:stop]], [x - 1 for x in closes[:stop]], closes[:stop]
        )
        for stop in (21, 22, 23)
    ] == [1, 0, 0]


def test_full_query_binds_immutable_identity_without_creating_authority(tmp_path: Path) -> None:
    study = _study(tmp_path)
    document = study.to_dict()
    assert document["schema"] == "FrozenDailyRuleStudyV1"
    assert document["authority"] == "none"
    assert document["scientific_acceptance"] == "not_admitted"
    assert DailyRuleStudyV1.model_validate(document) == study
    assert study.economics.half_spread_and_slippage_bps == pytest.approx(6.0)
    assert len(json.loads(study.query_document)["rows"]) == 1096
    assert (
        study.content_sha256
        == hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    )
    document["authority"] = "approved"
    assert study.to_dict()["authority"] == "none"
    with pytest.raises(ValidationError, match="frozen"):
        study.economics.__setattr__("fixed_quantity_btc", 0.5)
    # Even a typed draft is still refused by the synthetic-only launch/plan seam.
    with pytest.raises(DataError, match="no registered"):
        NativeLaunch(tmp_path, "INCONCLUSIVE", study=cast(SyntheticRuleStudy, study))
    with pytest.raises(DataError, match="fixed rule analysis plan changed"):
        validate_rule_plan(
            {"schema": "FrozenDailyRulePlanV1", "study": study.to_dict()}, max_grid_cells=5
        )


@pytest.mark.parametrize(
    "change", ["snapshot", "profile", "window", "query_bytes", "provider", "sources"]
)
def test_invalid_binding_cannot_be_frozen(tmp_path: Path, change: str) -> None:
    query = _full_discovery_query(tmp_path)
    economics, resources = daily_rule_terms_proposal()
    snapshot, profile = query.snapshot_id, "a" * 64
    if change == "snapshot":
        snapshot = "b" * 64
    elif change == "profile":
        profile = "unknown"
    elif change == "window":
        query = replace(query, start=query.start + timedelta(days=1))
    elif change == "query_bytes":
        query = replace(query, rows=query.rows[:-1])
    elif change == "provider":
        query = replace(query, dataset=replace(query.dataset, provider="bybit", venue="bybit"))
    else:
        query = replace(query, source_receipts=())
    with pytest.raises(DataError, match="daily study"):
        bind_daily_study(
            query,
            snapshot_sha256=snapshot,
            runtime_profile_sha256=profile,
            container_image_id="sha256:" + "c" * 64,
            storage_config_sha256="b" * 64,
            data_origin="artificial_fixture",
            economics=economics,
            resources=resources,
        )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("trials", True),
        ("max_cpus", True),
        ("max_rows", 1096.0),
        ("repairs", False),
        ("max_wall_seconds", 61),
        ("max_http_attempts", 9),
        ("tool_calls", 1),
    ],
)
def test_proposal_resources_are_finite_strict_and_have_no_extra_trials(
    name: str, value: object
) -> None:
    _, resources = daily_rule_terms_proposal()
    payload = resources.model_dump()
    payload[name] = value
    with pytest.raises(ValidationError):
        DailyRuleResourcesV1.model_validate(payload)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("fee_bps_per_side", float("nan")),
        ("slippage_bps_per_side", -1.0),
        ("starting_cash", float("inf")),
        ("fixed_quantity_btc", True),
        ("leverage", True),
        ("allow_short", 0),
        ("terminal_liquidation", True),
    ],
)
def test_proposal_economics_rejects_invalid_or_broadened_terms(name: str, value: object) -> None:
    economics, _ = daily_rule_terms_proposal()
    payload = economics.model_dump()
    payload[name] = value
    with pytest.raises(ValidationError):
        DailyRuleEconomicsV1.model_validate(payload)
