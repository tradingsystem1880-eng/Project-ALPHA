"""The lines ``alpha report`` prints for a stored gauntlet run: readings and numbers, never a grade.

Only arranges numbers the manifest stored. Each gate is shown by its class: a fact check keeps a
state word (sound, fault, not checked); a statistical gate shows its numbers and the plain
comparison, with the level the old grade used, muted, after it. The classes have one home:
docs/reference/invariants/cli-rule-readings.md.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from alpha_cli.run_store import read_manifest
from alpha_cli.spine.facts import read_json
from alpha_cli.spine.reading import reading_word, stored_reading

OLD_LEVEL = "the level used by the old grade"


def _num(value: Any) -> float | None:
    ok = isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
    return float(value) if ok else None


def _f(value: Any) -> str:
    number = _num(value)
    return "n/a" if number is None else f"{number:.4f}"


def _pct(value: Any, digits: int = 1) -> str:
    number = _num(value)
    return "n/a" if number is None else f"{number * 100:.{digits}f}%"


def _caveat(verdict: Mapping[str, Any]) -> str:
    labels = verdict.get("labels")
    return f" [{', '.join(labels)}: {verdict.get('sentence')}]" if labels else ""


def costs_line(manifest: Mapping[str, Any]) -> str | None:
    """The costs a rule-test run used, in one plain line; None for any other run.

    A rule-test run from before this line was stored says so instead of guessing.
    """
    spine = manifest.get("spine")
    if not isinstance(spine, Mapping) or "test_id" not in spine:
        return None
    costs = spine.get("costs") if isinstance(spine, Mapping) else None
    line = costs.get("line") if isinstance(costs, Mapping) else None
    return line if isinstance(line, str) else "Costs: not recorded for this older run."


def reading_line(manifest: Mapping[str, Any]) -> str | None:
    """``reading: <word> (old grade: X)`` for a run that stored a gauntlet grade; else None."""
    verdict = manifest.get("verdict")
    if not isinstance(verdict, Mapping):
        return None
    letter = verdict.get("overall")
    old = f" (old grade: {letter})" if letter else ""
    if isinstance(manifest.get("oos_metrics"), Mapping):
        folder = manifest.get("__dir")
        diagnostics = read_json(Path(str(folder)) / "diagnostics.json") if folder else {}
        word = reading_word(stored_reading(manifest, diagnostics))
    else:
        word = "not recorded"
    return f"reading: {word}{old}{_caveat(verdict)}"


def run_reading_text(run_dir: Path) -> str:
    """``<word> (old grade: X)`` for a stored run: the reading a command prints after writing it."""
    manifest = read_manifest(run_dir)
    manifest["__dir"] = str(run_dir)
    line = reading_line(manifest)
    return line.removeprefix("reading: ") if line else "not recorded"


def null_line(tier: Mapping[str, Any]) -> str:
    """One null tier: its numbers, what share of random runs did as well, the old level."""
    level = _f(tier.get("threshold"))
    return (
        f"null[{tier.get('tier')}]: percentile={_f(tier.get('percentile'))} "
        f"p={_f(tier.get('p_value'))} (random data did as well in {_pct(tier.get('p_value'))} "
        f"of draws; {OLD_LEVEL}: {level})"
    )


def monte_carlo_lines(manifest: Mapping[str, Any]) -> list[str]:
    """The family count, then one line per family: stored percentiles and the share below zero."""
    families = manifest.get("families")
    if not isinstance(families, list):
        family = manifest.get("family")
        families = [family] if isinstance(family, Mapping) else []
    lines = [f"Monte Carlo families: {len(manifest.get('families') or [])}"]
    for family in (f for f in families if isinstance(f, Mapping)):
        loss = family.get("loss_probability")
        loss = loss if isinstance(loss, Mapping) else {}
        lines.append(
            f"family[{family.get('family')}]: paths={family.get('n_paths')} "
            f"median_terminal={_f(family.get('terminal_return_q50'))} "
            f"terminal_5th={_f(family.get('terminal_return_q05'))} "
            f"terminal_95th={_f(family.get('terminal_return_q95'))} "
            f"drawdown_median={_f(family.get('maximum_drawdown_q50'))} "
            f"drawdown_q95={_f(family.get('maximum_drawdown_q95'))} "
            f"paths_below_zero={_f(loss.get('point'))} "
            f"[{_f(loss.get('lower'))}, {_f(loss.get('upper'))}]"
        )
    return lines


def _walk_forward(manifest: Mapping[str, Any]) -> str:
    metrics = manifest.get("oos_metrics")
    if not isinstance(metrics, Mapping):
        return "not checked"
    sharpe = _num(metrics.get("sharpe"))
    if sharpe is None:
        return "fault, the out-of-sample Sharpe could not be computed"
    return f"sound, out-of-sample Sharpe {sharpe:.4f}"


def _luck(manifest: Mapping[str, Any]) -> str:
    shares = [_num(t.get("p_value")) for t in manifest.get("nulls") or []]
    known = [s for s in shares if s is not None]
    if not known:
        return "no random-data result was stored"
    return (
        f"random data did as well in up to {_pct(max(known))} of draws in the weakest tier "
        f"({OLD_LEVEL}: at most 5.0%)"
    )


def _interval(manifest: Mapping[str, Any]) -> str:
    found = next((c for c in manifest.get("cis") or [] if c.get("metric") == "sharpe"), None)
    low, high = (_num(found.get(k)) for k in ("lower", "upper")) if found else (None, None)
    if low is None or high is None:
        return "no Sharpe interval was stored"
    verb = "is above zero" if low > 0 else "is below zero" if high < 0 else "includes zero"
    return (
        f"Sharpe interval {low:.4f} to {high:.4f}; the interval {verb} "
        f"({OLD_LEVEL}: lower end above 0)"
    )


def _deflated(manifest: Mapping[str, Any]) -> str:
    block = manifest.get("dsr")
    if not isinstance(block, Mapping) or _num(block.get("dsr")) is None:
        return "no deflated Sharpe was stored"
    tries = block.get("n_trials")
    counted = "n/a tries" if tries is None else f"{tries} {'try' if tries == 1 else 'tries'}"
    return (
        f"deflated Sharpe {_f(block.get('dsr'))} after {counted} "
        f"({OLD_LEVEL}: {_f(block.get('threshold'))})"
    )


def _cross_validated(manifest: Mapping[str, Any]) -> str:
    block = manifest.get("cpcv")
    if not isinstance(block, Mapping) or _num(block.get("mean_sharpe")) is None:
        return "no cross-validation result was stored"
    return (
        f"mean Sharpe across folds {_f(block.get('mean_sharpe'))}, "
        f"{_pct(block.get('frac_positive'), 0)} of folds above zero ({OLD_LEVEL}: mean above 0)"
    )


_GATES = {
    "walk_forward_oos": _walk_forward,
    "randomized_price_null": _luck,
    "bootstrap_ci": _interval,
    "deflated_sharpe": _deflated,
    "cpcv_oos": _cross_validated,
}


def gate_lines(manifest: Mapping[str, Any]) -> list[str]:
    """One line per stored gate; a gate this module does not know prints no verdict word."""
    lines = []
    for outcome in manifest.get("outcomes") or []:
        name = str(outcome.get("name"))
        text = _GATES.get(name)
        lines.append(f"gate[{name}]: {text(manifest) if text else 'recorded, see the manifest'}")
    return lines
