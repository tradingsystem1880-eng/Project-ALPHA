"""Static figure-catalog contract tests."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_research.figures.catalog import FigureDefinition


def _definition(**overrides: object) -> FigureDefinition:
    values: dict[str, object] = {
        "figure_id": "monte_carlo_equity_fans",
        "title": "Equity fans",
        "summary": "Synthetic equity paths and the observed out-of-sample path.",
        "question": "How sensitive is equity to path order?",
        "uncertainty": "The fan is conditional on the selected generator.",
        "caveat": "Scenario evidence does not prove edge.",
        "section": "Monte Carlo",
        "run_commands": ("monte_carlo_classical",),
        "required_artifacts": ("account_return_paths.parquet",),
        "panel_count": 4,
    }
    values.update(overrides)
    return FigureDefinition(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"figure_id": "Monte Carlo"}, "lower_snake_case"),
        ({"title": " "}, "title must be a non-empty string"),
        ({"run_commands": ()}, "at least one command"),
        ({"required_artifacts": ()}, "declare what it reads"),
        ({"panel_count": 0}, "at least one panel"),
    ),
)
def test_figure_definition_rejects_invalid_catalog_metadata(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(DataError, match=message):
        _definition(**overrides)


def test_figure_definition_derives_size_from_panel_count() -> None:
    size = _definition(panel_count=4).default_size
    assert size.width_in > size.height_in
