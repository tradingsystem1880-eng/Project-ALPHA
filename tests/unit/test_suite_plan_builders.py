"""Characterize argv, redaction and error order before splitting action builders."""

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from alpha_cli._suite import SuiteAction, build_suite_plan
from alpha_core import DataError
from tests.unit.test_suite_planner import _experiment


@pytest.mark.parametrize(
    "action", ["baseline", "inner_oos", "three_null_families", "portfolio_cross_asset", "kronos"]
)
@pytest.mark.parametrize("sealed", [False, True])
def test_research_steps_keep_exact_cutoff_redactions(
    tmp_path: Path, action: SuiteAction, sealed: bool
) -> None:
    store, project, experiment = _experiment(tmp_path, seal=sealed)
    plan = build_suite_plan(store, project, experiment, action, data_dir=tmp_path)
    for index, step in enumerate(plan.steps, start=1):
        cutoff, marker = step.redactions[0]
        assert cutoff == ("2026-03-31" if sealed else "<sealed-research-cutoff-required>")
        assert step.preview == tuple(marker if arg == cutoff else arg for arg in step.argv)
        assert step.public(index) == {
            "index": index,
            "label": step.label,
            "command": list(step.preview),
            "evidence_role": step.evidence_role,
        }
        assert step.argv[step.argv.index("--as-of") + 1] == cutoff


def test_null_family_options_order_and_public_roles(tmp_path: Path) -> None:
    store, project, experiment = _experiment(tmp_path)
    baseline = build_suite_plan(store, project, experiment, "baseline", data_dir=tmp_path)
    plan = build_suite_plan(store, project, experiment, "three_null_families", data_dir=tmp_path)
    prefix = (
        "validate",
        *baseline.steps[0].argv[2:],
        "--train-size",
        "504",
        "--test-size",
        "63",
        "--embargo",
        "5",
        "--seed",
        "7",
        "--tier1-paths",
        "100",
        "--tier2-paths",
        "8",
        "--n-resamples",
        "200",
        "--mean-block",
        "5",
        "--threshold",
        "0.95",
        "--tier1-divergence-tol",
        "0.25",
    )
    assert [step.argv for step in plan.steps] == [
        (*prefix, "--null-model", family) for family in ("bootstrap", "student_t", "garch")
    ]
    assert [step.label for step in plan.steps] == [
        "Stationary bootstrap headline",
        "Student-t sensitivity",
        "GARCH sensitivity",
    ]
    assert [step.evidence_role for step in plan.steps] == [
        "headline_tier1_plus_tier2",
        *["tier1_sensitivity_tier2_repeated_non_governing"] * 2,
    ]


@pytest.mark.parametrize(
    ("first_field", "second_field", "message"),
    [
        ("split_policy", "seeds", "train"),
        ("seeds", "stage_config", "master seed"),
        ("stage_config", "stage_config", "tier1_paths"),
    ],
)
def test_null_validation_error_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_field: str,
    second_field: str,
    message: str,
) -> None:
    store, project, experiment = _experiment(tmp_path)
    record = deepcopy(store.get_project(project))
    spec = cast(list[dict[str, object]], record["experiments"])[0]
    invalid = {
        "split_policy": {"train": -1},
        "seeds": {"master": -1},
        "stage_config": {"tier1_paths": -1, "tier2_paths": -1, "max_workers": -1},
    }
    spec[first_field] = invalid[first_field]
    spec[second_field] = invalid[second_field]
    monkeypatch.setattr(store, "get_project", lambda _: record)
    with pytest.raises(DataError, match=message):
        build_suite_plan(store, project, experiment, "three_null_families", data_dir=tmp_path)
