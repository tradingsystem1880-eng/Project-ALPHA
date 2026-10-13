"""Weekly mutation jobs must publish measurements for exactly their assigned module."""

from __future__ import annotations

from copy import deepcopy

import pytest
from check_mutation_report import validate_report

MODULE = "packages/alpha-validation/src/alpha_validation/bootstrap.py"


def report(status: str = "pass") -> dict[str, object]:
    return {
        "min_kill": 0.9,
        "modules": {
            MODULE: {
                "status": status,
                "seconds": 1.0,
                "total": 10,
                "killed": 9,
                "survived": 1,
                "no_tests": 0,
                "timeout": 0,
                "kill_rate": 0.9,
                "required": 0.9,
            }
        },
    }


@pytest.mark.parametrize("status", ["pass", "fail"])
def test_valid_measurements_allow_report_only_floor_failure(status: str) -> None:
    validate_report(report(status), MODULE)


@pytest.mark.parametrize("modules", [{}, {"wrong.py": {}}, {MODULE: {}, "extra.py": {}}])
def test_rejects_missing_wrong_and_extra_modules(modules: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="exactly"):
        validate_report({"min_kill": 0.9, "modules": modules}, MODULE)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "unavailable:timeout"),
        ("status", "unknown"),
        ("seconds", -1),
        ("kill_rate", float("nan")),
        ("required", 1.1),
        ("killed", True),
        ("total", -1),
        ("survived", None),
        ("killed", 11),
    ],
)
def test_rejects_unavailable_and_invalid_measurements(field: str, value: object) -> None:
    payload = deepcopy(report())
    modules = payload["modules"]
    assert isinstance(modules, dict)
    entry = modules[MODULE]
    assert isinstance(entry, dict)
    entry[field] = value
    with pytest.raises(ValueError):
        validate_report(payload, MODULE)


@pytest.mark.parametrize("payload", [None, [], {"modules": None}, {"modules": {MODULE: None}}])
def test_rejects_malformed_report(payload: object) -> None:
    with pytest.raises(ValueError):
        validate_report(payload, MODULE)
