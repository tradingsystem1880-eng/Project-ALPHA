"""Truthful preference semantics for the legacy strategy comparison."""

from alpha_cli.research_cmds import _comparison_preference


def _row(
    strategy: str, value: float | None, trades: int | None, error: str | None = None
) -> dict[str, object]:
    return {
        "strategy": strategy,
        "total_return": value,
        "n_trades": trades,
        "error": error,
    }


def test_comparison_prefers_only_one_distinct_comparable_traded_result() -> None:
    rows = [_row("a", 0.1, 2), _row("b", 0.2, 3)]
    assert _comparison_preference(rows) == ("preferred", "b", None)


def test_comparison_has_no_preference_for_tie_zero_trade_or_incomplete_rows() -> None:
    assert _comparison_preference([_row("a", 0.2, 2), _row("b", 0.2, 3)]) == (
        "tie",
        None,
        "top comparable strategies have equal total return",
    )
    assert _comparison_preference([_row("a", 0.2, 0), _row("b", 0.1, 3)]) == (
        "no_trades",
        None,
        "at least one strategy produced no completed trades",
    )
    assert _comparison_preference([_row("a", 0.2, 2), _row("b", None, None, "failed")]) == (
        "not_comparable",
        None,
        "every requested strategy must produce a comparable result",
    )
