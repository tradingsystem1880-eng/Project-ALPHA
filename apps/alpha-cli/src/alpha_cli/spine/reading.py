"""A rule test's reading: facts, numbers and evidence in context, never a grade.

Pure arrangement of numbers the gauntlet already stored. It computes no new statistic.
Shape ``AlphaReadingV1``: ``checks`` (fact items), ``measures``, ``evidence`` (one of four fixed
words), ``aim`` (what the reading is compared with), ``counts`` and one short ``sentence``.
Design: owner decision 2026-11-19, readings not verdicts.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

SCHEMA = "AlphaReadingV1"
# The four evidence words and their fixed definitions. Each number below has one source.
MIN_TRADES = 30  # spine/audit.py ENOUGH_TRADES: fewer closed trades are too few to judge
MIN_OOS_OBSERVATIONS = 100  # packages/alpha-validation verdict.py: smallest sample band (D)
NULL_THRESHOLD = 0.95  # _gauntlet.py: null percentile every stored null test must reach
CONFIDENCE = 0.95  # _gauntlet.py: bootstrap Sharpe interval; its lower end must be above 0
DSR_THRESHOLD = 0.95  # _gauntlet.py dsr_threshold: deflated Sharpe, after counting every trial
# CPCV: its mean out-of-sample Sharpe must be above 0 (_gauntlet.py).
# Only the deflated Sharpe counts trials; the bootstrap interval and the null tests do not. So the
# corrected figure decides between "not clear of chance" and the two positive words, and only a
# deflated Sharpe counted against a ledger family can give the top word. A missing number never
# helps: it makes the word weaker.
CLEAR, SOME, NOT_CLEAR, TOO_LITTLE = (
    "clear of chance",
    "some evidence",
    "not clear of chance",
    "too little to read",
)
WORDS = {
    CLEAR: (
        f"Every check holds after counting all trials: each null test at {NULL_THRESHOLD}, the "
        f"{CONFIDENCE:.0%} Sharpe interval above 0, deflated Sharpe at least {DSR_THRESHOLD} with "
        "the trials counted from the ledger family, cross-validated mean Sharpe above 0, and the "
        "plausibility check ran and raised nothing."
    ),
    SOME: (
        f"The Sharpe interval is above 0, every null test holds and deflated Sharpe is at least "
        f"{DSR_THRESHOLD}, but cross-validation, a plausibility caution or a plausibility check "
        "that did not run, or trials not counted from a ledger family hold back the top word."
    ),
    NOT_CLEAR: (
        "The Sharpe is not above 0, its interval includes 0, random data did as well as the rule "
        f"in more than {1 - NULL_THRESHOLD:.0%} of draws, or the deflated Sharpe after counting "
        f"trials is under {DSR_THRESHOLD}. A missing interval, null test or deflated Sharpe "
        "reads the same way."
    ),
    TOO_LITTLE: (
        f"Under {MIN_TRADES} closed trades or under {MIN_OOS_OBSERVATIONS} out-of-sample "
        "observations, or either count was not stored. This word wins over every other."
    ),
}
# Setup Lab: the three outcome words stored before readings, read as the evidence word they were
# derived from (the same conditions). The old words stay in stored files for machines.
OLD_SETUP_OUTCOMES = {
    "inconclusive": TOO_LITTLE,
    "not supported": NOT_CLEAR,
    "supported (exploratory, not confirmed)": SOME,
}
LEGACY_SETUP_OUTCOMES = {word: old for old, word in OLD_SETUP_OUTCOMES.items()}
# A setup study or trade reads with these three only: its p-value is not corrected for the
# variants tried, so the top word is never one of them.
SETUP_WORDS = (TOO_LITTLE, NOT_CLEAR, SOME)
RELATIONS = ("above the aim", "below the aim", "within the uncertainty of the aim")
AIM_BASIS = (
    "buy-and-hold Sharpe over the same scored days ({price}, no costs) against the strategy's "
    f"{CONFIDENCE:.0%} bootstrap Sharpe interval: within the interval reads within the "
    "uncertainty of the aim; the benchmark's own uncertainty is not included"
)


def _num(value: Any) -> float | None:
    """A finite float, or None for a missing or non-finite statistic."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _get(node: Any, *path: str) -> Any:
    for key in path:
        node = node.get(key) if isinstance(node, Mapping) else None
    return node


def _f(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _sharpe_ci(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    cis = manifest.get("cis") or []
    found: Mapping[str, Any] = next((c for c in cis if c.get("metric") == "sharpe"), {})
    return found


def _checks(manifest: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> list[dict[str, str]]:
    metrics = manifest.get("oos_metrics")
    missing = [
        label
        for key, label in (
            ("sharpe", "out-of-sample Sharpe"),
            ("max_drawdown", "maximum drawdown"),
            ("risk_of_ruin", "risk of ruin"),
        )
        if _num(_get(metrics, key)) is None
    ]
    computed = (
        {"state": "fault", "detail": f"the {missing[0]} could not be computed"}
        if missing
        else {"state": "sound", "detail": "every statistic was computed"}
    )
    audit = {item.get("check"): item for item in diagnostics.get("audit", [])}
    fills = audit.get("fills-after-decisions", {}).get("status")
    ahead = {
        "FLAG": {"state": "fault", "detail": "a fill came at or before its decision (look-ahead)"},
        "PASS": {"state": "sound", "detail": "every fill came after its decision"},
    }.get(fills, {"state": "not-checked", "detail": "no decision trace was checked"})
    health = _get(manifest, "data_health", "verdict")
    data = {
        "fail": {"state": "fault", "detail": "the data failed its health check"},
        "pass": {"state": "sound", "detail": "the data health check is clean"},
        "warn": {"state": "sound", "detail": "the data health check has warnings"},
    }.get(health, {"state": "not-checked", "detail": "the data health was not checked"})
    return [
        {"name": name, **item}
        for name, item in (("numbers", computed), ("no-look-ahead", ahead), ("data-health", data))
    ]


def _trades(manifest: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> int | None:
    for value in (
        diagnostics.get("closed_oos_trades"),
        _get(manifest, "spine", "periods", "scored", "strategy", "trades"),
    ):
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _too_little(manifest: Mapping[str, Any], trades: int | None, n_oos: float | None) -> str | None:
    """Why the sample is too small to read, or None when both counts are stored and large enough."""
    if trades is None:
        return "the closed-trade count was not stored"
    if trades < MIN_TRADES or "too-few-trades" in (_get(manifest, "spine", "labels") or []):
        return f"{trades} closed trades (fewer than {MIN_TRADES} make too few to judge)"
    if n_oos is None:
        return "the out-of-sample observation count was not stored"
    if n_oos < MIN_OOS_OBSERVATIONS:
        return f"{n_oos:.0f} out-of-sample observations (fewer than {MIN_OOS_OBSERVATIONS})"
    return None


def _word(
    manifest: Mapping[str, Any], diagnostics: Mapping[str, Any], little: str | None
) -> tuple[str, list[str]]:
    """The evidence word, by the fixed precedence in ``WORDS``, and what held back the top word."""
    sharpe = _num(_get(manifest, "oos_metrics", "sharpe"))
    lower = _num(_sharpe_ci(manifest).get("lower"))
    nulls = manifest.get("nulls") or []
    dsr = _num(_get(manifest, "dsr", "dsr"))
    if little:
        return TOO_LITTLE, []
    if (
        sharpe is None
        or sharpe <= 0
        or lower is None
        or lower <= 0
        or not nulls
        or not all(n.get("passed") is True for n in nulls)
        or dsr is None
        or dsr < DSR_THRESHOLD
    ):
        return NOT_CLEAR, []
    held = []
    if _get(manifest, "cpcv", "passed") is not True:
        held.append("Cross-validated mean Sharpe is not above 0.")
    if not _get(manifest, "dsr", "family_id"):
        held.append("Trials were not counted from a ledger family.")
    plausible = diagnostics.get("plausibility")
    if not isinstance(plausible, list):
        held.append("The plausibility check did not run.")
    elif plausible:
        held.append("The result looks too good: check for a data error first.")
    return (SOME if held else CLEAR), held


def _evidence(
    manifest: Mapping[str, Any], diagnostics: Mapping[str, Any], trades: int | None
) -> dict[str, Any]:
    ci = _sharpe_ci(manifest)
    lower, upper = _num(ci.get("lower")), _num(ci.get("upper"))
    nulls = manifest.get("nulls") or []
    little = _too_little(
        manifest, trades, _num(_get(manifest, "verdict", "detail", "sample_n_oos"))
    )
    word, held = _word(manifest, diagnostics, little)
    because = [little.capitalize() + "."] if little else []
    ok_nulls = sum(n.get("passed") is True for n in nulls)
    because.append(f"Random-data tests held: {ok_nulls} of {len(nulls)}.")
    because.append(f"Sharpe interval {_f(lower)} to {_f(upper)} ({CONFIDENCE:.0%}).")
    dsr, psr = _num(_get(manifest, "dsr", "dsr")), _num(_get(manifest, "dsr", "psr"))
    because.append(
        f"Deflated Sharpe {_f(dsr)} over {_get(manifest, 'dsr', 'n_trials')} trials "
        f"(needs {DSR_THRESHOLD}); {_f(psr)} before counting trials."
    )
    return {"word": word, "because": because + held}


def _aim(manifest: Mapping[str, Any]) -> dict[str, Any]:
    observed = _num(_get(manifest, "oos_metrics", "sharpe"))
    scored = _get(manifest, "spine", "periods", "scored")
    aim = _num(_get(scored, "benchmark", "sharpe"))
    ci = _sharpe_ci(manifest)
    lower, upper = _num(ci.get("lower")), _num(ci.get("upper"))
    # Only buy-and-hold over the same scored days is an aim; no interval, no relation.
    if observed is None or aim is None or lower is None or upper is None:
        return {"source": "none", "basis": None, "rows": []}
    relation = RELATIONS[0] if aim < lower else RELATIONS[1] if aim > upper else RELATIONS[2]
    price = _get(scored, "price_basis") or "price basis not stored"
    row = {
        "measure": "out-of-sample Sharpe",
        "aim": aim,
        "observed": observed,
        "interval_95": [lower, upper],
        "relation": relation,
    }
    return {"source": "default", "basis": AIM_BASIS.format(price=price), "rows": [row]}


def _counts(manifest: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    family = _get(diagnostics, "trials", "family") or {}
    variants = diagnostics.get("variants_evaluated")
    variants = variants if isinstance(variants, int) and variants > 0 else None
    return {
        "trial_n": _get(diagnostics, "trials", "total_trials"),
        "family_id": family.get("family_id") or _get(manifest, "dsr", "family_id"),
        "family_trials": family.get("n_trials_used") or _get(manifest, "verdict", "n_trials"),
        "variants_tried": variants,
        "best_of": variants + 1 if variants else None,
    }


def _measures(manifest: Mapping[str, Any], trades: int | None, hold: bool) -> list[dict[str, Any]]:
    ci = _sharpe_ci(manifest)
    interval = [_num(ci.get("lower")), _num(ci.get("upper"))]
    rows = [
        ("out-of-sample Sharpe", _get(manifest, "oos_metrics", "sharpe"), interval),
        ("deflated Sharpe", _get(manifest, "dsr", "dsr"), None),
        ("Sharpe before counting trials", _get(manifest, "dsr", "psr"), None),
        ("cross-validated mean Sharpe", _get(manifest, "cpcv", "mean_sharpe"), None),
        ("maximum drawdown", _get(manifest, "oos_metrics", "max_drawdown"), None),
        ("closed trades", trades, None),
    ]
    return [
        {
            "name": name,
            "value": _num(value),
            "interval_95": interval_95 if interval_95 and None not in interval_95 else None,
            "basis": "walk-forward out-of-sample, after costs",
            **({"not_to_be_read": True} if hold else {}),
        }
        for name, value, interval_95 in rows
    ]


def _sentence(
    faults: list[str],
    evidence: Mapping[str, Any],
    aim: Mapping[str, Any],
    counts: Mapping[str, Any],
) -> str:
    if faults:
        return f"Fault: {faults[0]}. Fix this first. No reading."
    parts = []
    if aim["rows"]:
        row = aim["rows"][0]
        parts.append(
            f"Out-of-sample Sharpe {_f(row['observed'])}; buy-and-hold over the same days "
            f"{_f(row['aim'])}."
        )
        parts.append(f"Default aim: beat buy-and-hold; this reading is {row['relation']}.")
    parts.append(f"Evidence strength: {evidence['word']}.")
    tail = [
        part
        for part in (
            f"ledger entry {counts['trial_n']}" if counts["trial_n"] else "",
            f"family counted as {counts['family_trials']} tries" if counts["family_trials"] else "",
            f"best of {counts['best_of']} variants" if counts["best_of"] else "",
        )
        if part
    ]
    if tail:
        parts.append("; ".join(tail).capitalize() + ".")
    return " ".join(parts)


def _costs(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """The costs and annualisation the run used, as stored; an older run did not store them."""
    spine = manifest.get("spine")
    costs = spine.get("costs") if isinstance(spine, Mapping) else None
    if not isinstance(costs, Mapping) or not isinstance(costs.get("line"), str):
        return {"line": None, "periods": None, "reason": "This run did not store its costs line."}
    periods = costs.get("periods")
    return {"line": costs["line"], "periods": periods if isinstance(periods, str) else None}


def build_reading(
    manifest: Mapping[str, Any], diagnostics: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Arrange a stored run's numbers as a reading; works for old manifests too."""
    diag: Mapping[str, Any] = diagnostics or {}
    checks = _checks(manifest, diag)
    faults = [c["detail"] for c in checks if c["state"] == "fault"]
    trades = _trades(manifest, diag)
    evidence = _evidence(manifest, diag, trades)
    aim = _aim(manifest)
    counts = _counts(manifest, diag)
    if faults:
        evidence = {"word": None, "because": []}
        aim = {"source": aim["source"], "basis": aim["basis"], "rows": []}
    return {
        "schema": SCHEMA,
        "costs": _costs(manifest),
        "checks": checks,
        "measures": _measures(manifest, trades, bool(faults)),
        "evidence": evidence,
        "aim": aim,
        "counts": counts,
        "sentence": _sentence(faults, evidence, aim, counts),
    }


def reading_text(reading: Mapping[str, Any]) -> str:
    """The reading sentence, then the costs line and the annualisation line when stored."""
    costs = reading.get("costs")
    extra = [
        costs[key] for key in ("line", "periods") if isinstance(costs, Mapping) and costs.get(key)
    ]
    return "\n".join([reading["sentence"], *extra])


def stored_reading(
    manifest: Mapping[str, Any], diagnostics: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """The reading written with the run, or one derived from an old manifest's numbers."""
    stored = manifest.get("reading")
    return dict(stored) if isinstance(stored, Mapping) else build_reading(manifest, diagnostics)


def old_grade_text(letter: str | None) -> str:
    """Owner words for a row where only a letter grade was kept."""
    return f"graded {letter} under the old rules" if letter else "recorded without a reading"


def reading_word(reading: Mapping[str, Any]) -> str:
    """The short owner word: the evidence word, or ``fault``."""
    return str(_get(reading, "evidence", "word") or "fault")


def ledger_fields(found: Mapping[str, Any] | None) -> dict[str, str | None]:
    """The two additive ledger fields of a new rule-test row; an error row has none."""
    if not isinstance(found, Mapping):
        return {"evidence": None, "aim_relation": None}
    rows = _get(found, "aim", "rows") or []
    relation = rows[0].get("relation") if rows else None
    return {"evidence": reading_word(found), "aim_relation": relation}


def setup_evidence_of(summary: Mapping[str, Any]) -> tuple[str, bool]:
    """A stored setup study or trade as an evidence word, and True when only the old word exists."""
    word = summary.get("evidence")
    if isinstance(word, str) and word in SETUP_WORDS:
        return word, False
    return OLD_SETUP_OUTCOMES[str(summary["outcome"])], True
