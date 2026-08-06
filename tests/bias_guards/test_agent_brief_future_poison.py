"""Later project, stage, and holdout-lineage state must not change an earlier AgentBrief."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_cli.control_store import ControlStore
from alpha_cli.project_cmds import _agent_brief
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy

pytestmark = pytest.mark.bias_guard

PROJECT_ID = "7fb31b48-9527-4aec-ae6b-68d55da2c0e0"
START = datetime(2026, 7, 19, 0, 0, tzinfo=UTC)
CUTOFF = "2026-07-19T00:02:30Z"


def _version(store: ControlStore, *, source: str, window: int, at: datetime) -> str:
    row = store.create_strategy_version(
        PROJECT_ID,
        strategy_name="mean_reversion",
        source_fingerprint=source,
        definition={"window": window},
        parameter_space={"window": [window]},
        at=at,
    )
    return str(row["version_id"])


def _experiment(store: ControlStore, version_id: str, *, at: datetime) -> str:
    row = store.create_experiment_spec(
        PROJECT_ID,
        strategy_version_id=version_id,
        snapshot_id=f"snapshot-{version_id[-8:]}",
        universe=["AAPL", "MSFT"],
        split_policy={"train": 504, "test": 63, "embargo": 5},
        costs={"fee_bps": 1.0, "slippage_bps": 2.0},
        seeds={"master": 7},
        at=at,
    )
    return str(row["experiment_id"])


def test_future_project_scope_cannot_poison_agent_brief(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    store.create_project(
        name="PIT AgentBrief",
        hypothesis="A causal signal survives costs.",
        falsification_criterion="Reject on failed OOS evidence.",
        project_id=PROJECT_ID,
        at=START,
    )
    mark_project_as_migrated_legacy(store, PROJECT_ID)
    first_version = _version(
        store,
        source="git:first",
        window=20,
        at=START + timedelta(minutes=1),
    )
    _experiment(store, first_version, at=START + timedelta(minutes=2))
    baseline = _agent_brief(store, PROJECT_ID, evidence_limit=10, as_of=CUTOFF)

    later_version = _version(
        store,
        source="git:future",
        window=60,
        at=START + timedelta(minutes=3),
    )
    later_experiment = _experiment(
        store,
        later_version,
        at=START + timedelta(minutes=4),
    )
    store.append_experiment_stage_state(
        PROJECT_ID,
        later_experiment,
        "baseline",
        "queued",
        reason="future work",
        at=START + timedelta(minutes=5),
    )

    after_future_mutations = _agent_brief(
        store,
        PROJECT_ID,
        evidence_limit=10,
        as_of=CUTOFF,
    )
    assert after_future_mutations == baseline
