"""Public fixed synthetic rule qualification; no native scientific admission."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._native_loop_admission import NativeLaunch
from alpha_cli._native_rule_study import SyntheticRuleStudy
from alpha_core import DataError
from alpha_research import (
    EqualDurationResearchBars,
    ResearchArtifactRef,
    ResearchBar,
    ResearchDatasetRef,
)
from alpha_strategies.rules import rule_signal, rule_spec_from_json

# Independently authored input and expected signals. No implementation-generated oracle.
RULE = (
    '{"history":2,"long_when":[{"left":{"source":"close"},"op":">",'
    '"right":{"value":10}}],"name":"synthetic-close-above-ten","short_when":[],"version":1}'
)
CONTROL = (
    '{"history":2,"long_when":[{"left":{"source":"close"},"op":"<",'
    '"right":{"value":0}}],"name":"synthetic-always-flat","short_when":[],"version":1}'
)
START = datetime(2000, 1, 1, tzinfo=UTC)


def _bars() -> EqualDurationResearchBars:
    # Fifth row is future to the fixed cutoff. Four visible closes: 8, 12, 10, 16.
    rows = tuple(
        ResearchBar(
            dataset_id="synthetic-rules-v1",
            start=START + timedelta(days=i),
            end=START + timedelta(days=i + 1),
            available_at=START + timedelta(days=i + 1),
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=1.0,
        )
        for i, close in enumerate((8.0, 12.0, 10.0, 16.0, 4.0))
    )
    # Hand-authored wire shape; source must independently bind these exact values and clocks.
    raw = json.dumps(
        [
            [
                r.start.isoformat(),
                r.end.isoformat(),
                r.available_at.isoformat(),
                r.open,
                r.high,
                r.low,
                r.close,
                r.volume,
            ]
            for r in rows
        ],
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    dataset = ResearchDatasetRef(
        dataset_id="synthetic-rules-v1",
        provider="synthetic",
        provider_symbol="RULES",
        symbol="RULES",
        venue="SYNTHETIC",
        timeframe="1d",
        timezone="UTC",
        session="UTC_DAY",
        content_sha256=hashlib.sha256(raw).hexdigest(),
    )
    return EqualDurationResearchBars(dataset, rows)


def _request(**changes: Any) -> SyntheticRuleStudy:
    bars = _bars()
    values: dict[str, Any] = {
        "rules_spec": RULE,
        "control_spec": CONTROL,
        "data": bars,
        "data_artifact": ResearchArtifactRef(
            artifact_id="synthetic-bars.json",
            kind="table",
            media_type="application/json",
            content_sha256=bars.dataset.content_sha256,
            size_bytes=542,
            row_count=5,
        ),
        "cutoff": datetime(2000, 1, 5, tzinfo=UTC),
        "horizon_bars": 1,
        "price_unit": "synthetic_price",
        "signal_unit": "position",
        "capability": "frozen_rule_positions_v1",
    }
    values.update(changes)
    return SyntheticRuleStudy(**values)


def test_fixed_data_hash_and_immutable_request() -> None:
    request = _request()
    assert request.content_sha256 == _request().content_sha256
    assert request.to_dict()["authority"] == "none"
    assert request.to_dict()["scientific_acceptance"] == "not_admitted"
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.horizon_bars = 2  # type: ignore[misc]


def test_real_rule_operator_and_flat_position_control() -> None:
    request = _request()
    bars = [b for b in request.data.bars if b.available_at <= request.cutoff]
    rule = rule_spec_from_json(request.rules_spec)
    control = rule_spec_from_json(request.control_spec)
    observed = []
    null = []
    for stop in (2, 3, 4):
        window = bars[:stop]
        values = ([b.high for b in window], [b.low for b in window], [b.close for b in window])
        observed.append(rule_signal(rule, *values))
        null.append(rule_signal(control, *values))
    assert observed == [1, 0, 1]  # 12 > 10; equality is flat; 16 > 10.
    assert null == [0, 0, 0]  # Positive prices never meet close < 0.
    # No event-study mean, strategy return, or scientific verdict is inferred from these states.


@pytest.mark.parametrize(
    "changes",
    [
        {"rules_spec": RULE.replace('"value":10', '"value":11')},
        {"rules_spec": RULE.replace("synthetic-close-above-ten", "renamed")},
        {"control_spec": RULE},
        {"control_spec": "unsupported"},
        {"cutoff": datetime(2000, 1, 6, tzinfo=UTC)},
        {"cutoff": datetime(2000, 1, 5, 1, tzinfo=timezone(timedelta(hours=1)))},
        {"cutoff": datetime(2000, 1, 5)},
        {"horizon_bars": 2},
        {"horizon_bars": True},
        {"price_unit": "USD"},
        {"signal_unit": "fraction"},
        {"capability": "event_study"},
        {"capability": "unknown"},
    ],
)
def test_changed_request_is_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(DataError):
        _request(**changes)


def test_changed_data_and_missing_or_wrong_artifact_provenance_are_rejected() -> None:
    bars = _bars()
    changed = dataclasses.replace(bars.bars[0], close=9.0)
    with pytest.raises(DataError, match="data"):
        _request(data=EqualDurationResearchBars(bars.dataset, (changed, *bars.bars[1:])))
    with pytest.raises(DataError, match="artifact"):
        _request(data_artifact=None)
    artifact = _request().data_artifact
    for replacement in (
        dataclasses.replace(artifact, content_sha256="a" * 64),
        dataclasses.replace(artifact, size_bytes=0),
        dataclasses.replace(artifact, row_count=4),
        dataclasses.replace(artifact, artifact_id="other.json"),
    ):
        with pytest.raises(DataError, match="artifact"):
            _request(data_artifact=replacement)


def test_requested_native_study_blocks_before_source_read_or_process_effects(
    tmp_path: Path,
) -> None:
    # A missing source path would fail launch measurement if this scientific guard were too late.
    with pytest.raises(DataError, match="registered RuleSpec/control protocol"):
        NativeLaunch(tmp_path / "source-must-not-be-opened", "INCONCLUSIVE", study=_request())
    assert list(tmp_path.iterdir()) == []


def test_existing_d0_registry_does_not_admit_frozen_rules() -> None:
    from alpha_cli.research_runtime import registered_d0_operator
    from alpha_study._operator_registry import OPERATOR_REGISTRY_V1

    assert tuple(OPERATOR_REGISTRY_V1) == ("double_bottom.v1",)
    with pytest.raises(DataError, match="only supports the canonical double_bottom"):
        registered_d0_operator({"event_definition": {"name": "frozen_rules"}})


def test_existing_approved_reservation_cannot_launder_rule_study(tmp_path: Path) -> None:
    from alpha_cli.control_store import ControlStore
    from tests.unit.test_research_control_store import (
        PROJECT_ID,
        _approved_native_d1,
        _native_d1_job,
        _project,
    )

    job = "4c657d82-fc1a-44d8-b49b-bfdcfe93c52c"
    root = tmp_path
    store = ControlStore(root)
    _project(store)
    contract, _ = _approved_native_d1(store)
    _native_d1_job(store, contract, job_id=job)
    before = store.research_case_summary(PROJECT_ID)
    for _ in range(2):  # A repeated request gets no owner claim, effect, or refund.
        with pytest.raises(DataError, match="registered RuleSpec/control protocol"):
            NativeLaunch(root / "unused-source", "INCONCLUSIVE", study=_request())
    assert store.get_job(job)["job_id"] == job
    with store._transaction(write=False) as connection:
        assert not connection.execute(
            "SELECT 1 FROM job_events WHERE job_id=? AND event_type LIKE 'native_%'",
            (job,),
        ).fetchall()
    assert store.research_case_summary(PROJECT_ID) == before
    assert not (root / f"payload-{job}").exists()


@pytest.mark.bias_guard
def test_fixed_visible_position_signal_excludes_future_with_leaky_twin() -> None:
    request = _request()
    spec = rule_spec_from_json(request.rules_spec)
    visible = [bar for bar in request.data.bars if bar.available_at <= request.cutoff]
    future = dataclasses.replace(request.data.bars[-1], open=40.0, high=41.0, low=39.0, close=40.0)

    def signal(rows: list[ResearchBar]) -> int:
        return rule_signal(
            spec, [b.high for b in rows], [b.low for b in rows], [b.close for b in rows]
        )

    assert signal(visible) == 1
    assert signal([b for b in [*visible, future] if b.available_at <= request.cutoff]) == 1
    # Must-fail leaky twin: using the unfiltered last bar changes the observation.
    assert signal(list(request.data.bars)) == 0
    assert signal([*visible, future]) == 1
    with pytest.raises(DataError, match="data bytes"):
        _request(data=EqualDurationResearchBars(request.data.dataset, (*visible, future)))


def test_frozen_dataset_reference_cannot_be_relabelled_or_rehashed() -> None:
    bars = _bars()
    for dataset in (
        dataclasses.replace(bars.dataset, provider="market"),
        dataclasses.replace(bars.dataset, content_sha256="a" * 64),
        dataclasses.replace(bars.dataset, timeframe="1h"),
    ):
        with pytest.raises(DataError, match="data identity"):
            _request(data=EqualDurationResearchBars(dataset, bars.bars))


def test_request_does_not_accept_metrics_repair_or_continuation() -> None:
    for field in ("metrics", "outcome", "repair", "continue_from", "study_id", "trial_id"):
        with pytest.raises(TypeError, match="unexpected keyword"):
            _request(**{field: "caller supplied"})
