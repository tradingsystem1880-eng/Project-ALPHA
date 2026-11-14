"""Full planner characterisation; regenerate explicitly with this file's --write helper.

The golden keeps, per scenario and action, the SHA-256 of the complete normalised output (plan,
every step's argv, preview, redactions, label and role, or the exact error), plus the stage
states. A mismatch prints the full actual output; `--write --full <file>` dumps it all for a diff.
The normal pytest path only reads the golden. Fixed fixture inputs (including run IDs,
snapshot IDs, research contracts, dates and fingerprints) are deliberately literal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

if __name__ == "__main__":
    # Direct file execution puts tests/unit, rather than the repository, on sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha_cli._suite import SUITE_ACTIONS, SuiteAction, _managed_qlib_id, build_suite_plan
from alpha_cli.control_store import ControlStore
from tests.unit.test_suite_planner import (
    _complete_action,
    _complete_candidate_stage,
    _experiment,
    _governed_overridden_experiment,
    _hedged_basis_experiment,
)

_GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "suite_plan_golden.json"
_STANDARD_ACTIONS = (
    "baseline",
    "inner_oos",
    "three_null_families",
    "monte_carlo",
    "optimize_grid",
    "portfolio_cross_asset",
    "kronos",
)
_CANDIDATE_STAGES = (
    ("baseline", "baseline", ("candidate_baseline",)),
    ("inner_oos", "oos", ("candidate_oos",)),
    (
        "three_null_families",
        "robustness",
        ("candidate_null_bootstrap", "candidate_null_student_t", "candidate_null_garch"),
    ),
    (
        "monte_carlo",
        "monte_carlo",
        ("candidate_monte_carlo_classical", "candidate_monte_carlo_kronos"),
    ),
    ("optimize_grid", "optimization", ("candidate_optim",)),
    ("portfolio_cross_asset", "portfolio", ("candidate_portfolio", "candidate_cross_asset")),
    ("qlib", "ml", ("candidate_qlib",)),
    ("kronos", "kronos", ("candidate_kronos_forecast", "candidate_kronos_eval")),
)


def _generated_values(store: ControlStore, project_id: str, experiment_id: str) -> set[str]:
    """Identify volatile values by provenance, never by a broad hash/date regex."""
    project = store.get_project(project_id)
    values = {project_id, experiment_id, _managed_qlib_id(experiment_id)}
    for collection, fields in (
        ("versions", ("version_id", "created_at")),
        ("experiments", ("experiment_id", "created_at")),
        ("holdouts", ("holdout_spec_hash",)),
    ):
        for row in cast(list[dict[str, object]], project[collection]):
            for field in fields:
                value = row[field]
                if value is not None:
                    assert isinstance(value, str)
                    values.add(value)
    return values


def _capture_state(
    store: ControlStore, path: Path, project_id: str, experiment_id: str
) -> dict[str, object]:
    actions: dict[str, object] = {}
    for action in sorted(SUITE_ACTIONS):
        try:
            plan = build_suite_plan(
                store, project_id, experiment_id, cast(SuiteAction, action), data_dir=path
            )
        except Exception as exc:
            # Exceptions are part of the characterised output, with no discarded detail.
            actions[action] = {"error": {"class": type(exc).__name__, "message": str(exc)}}
        else:
            actions[action] = {
                "plan": plan.as_dict(),
                "steps": [
                    {
                        "argv": list(step.argv),
                        "preview": list(step.preview),
                        "redactions": [list(pair) for pair in step.redactions],
                        "label": step.label,
                        "evidence_role": step.evidence_role,
                    }
                    for step in plan.steps
                ],
            }
    states = {
        str(row["stage"]): row["state"]
        for row in cast(list[dict[str, object]], store.get_project(project_id)["stage_states"])
        if row["experiment_id"] == experiment_id
    }
    return {"stage_states": states, "actions": actions}


def _normalise(record: dict[str, object], generated: set[str], tmp_path: Path) -> dict[str, object]:
    """Replace exact generated values, including occurrences embedded in previews/paths.

    Token assignment follows first appearance in the complete record. One shared mapping
    preserves identity both within plans and across actions and successive stage states.
    """
    path = str(tmp_path)
    pattern = re.compile("|".join(re.escape(value) for value in sorted(generated | {path})))
    tokens: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        value = match.group()
        if value == path:
            return "<path>"
        if value not in tokens:
            tokens[value] = f"<id-{len(tokens) + 1}>"
        return tokens[value]

    def visit(value: object) -> object:
        if isinstance(value, str):
            return pattern.sub(replace, value)
        if isinstance(value, list):
            return [visit(item) for item in cast(list[object], value)]
        if isinstance(value, dict):
            return {key: visit(item) for key, item in cast(dict[str, object], value).items()}
        return value

    return cast(dict[str, object], visit(record))


def _capture(tmp_path: Path) -> dict[str, object]:
    record: dict[str, object] = {}
    generated: set[str] = set()
    for scenario in ("sealed", "unsealed", "hedged_basis", "governed_overridden"):
        path = tmp_path / scenario
        if scenario == "hedged_basis":
            store, project_id, experiment_id, contract_id, snapshot_id = _hedged_basis_experiment(
                path
            )
        elif scenario == "governed_overridden":
            store, project_id, experiment_id = _governed_overridden_experiment(path)
        else:
            store, project_id, experiment_id = _experiment(path, seal=scenario == "sealed")
        generated.update(_generated_values(store, project_id, experiment_id))
        record[f"{scenario}/fresh"] = _capture_state(store, path, project_id, experiment_id)
        if scenario == "unsealed":
            # _complete_action cannot admit baseline evidence without a dated seal.
            continue
        if scenario == "hedged_basis":
            for action, stage, commands in _CANDIDATE_STAGES:
                _complete_candidate_stage(
                    store,
                    path,
                    project_id,
                    experiment_id,
                    contract_id,
                    snapshot_id,
                    action=action,
                    stage=stage,
                    commands=commands,
                )
                record[f"{scenario}/after_{action}"] = _capture_state(
                    store, path, project_id, experiment_id
                )
        else:
            for action in _STANDARD_ACTIONS:
                _complete_action(store, path, project_id, experiment_id, action)
                record[f"{scenario}/after_{action}"] = _capture_state(
                    store, path, project_id, experiment_id
                )
    return _normalise(record, generated, tmp_path)


def _digest(output: object) -> str:
    encoded = json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _golden(record: dict[str, object]) -> dict[str, object]:
    golden: dict[str, object] = {}
    for scenario, raw in record.items():
        state = cast(dict[str, object], raw)
        actions = cast(dict[str, object], state["actions"])
        golden[scenario] = {
            "stage_states": state["stage_states"],
            "actions": {action: _digest(output) for action, output in actions.items()},
        }
    return golden


def test_suite_plan_golden(tmp_path: Path) -> None:
    expected = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    record = _capture(tmp_path)
    actual = _golden(record)
    assert actual.keys() == expected.keys(), "scenario/state coverage differs"
    for scenario, raw in actual.items():
        state = cast(dict[str, object], raw)
        assert state["stage_states"] == expected[scenario]["stage_states"], scenario
        actions = cast(dict[str, str], state["actions"])
        assert actions.keys() == expected[scenario]["actions"].keys(), scenario
        for action, digest in actions.items():
            output = cast(dict[str, object], record[scenario])["actions"]
            assert digest == expected[scenario]["actions"][action], (
                f"{scenario}: {action} changed; actual output:\n"
                + json.dumps(cast(dict[str, object], output)[action], indent=2, sort_keys=True)
            )


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", required=True)
    parser.add_argument("--full", type=Path, help="also dump the full normalised output here")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="suite-plan-golden-") as directory:
        record = _capture(Path(directory))
    _GOLDEN.write_text(json.dumps(_golden(record), indent=2) + "\n", encoding="utf-8")
    if args.full is not None:
        args.full.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    _main()
