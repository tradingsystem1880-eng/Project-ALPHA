"""Objective-level analysis for realistic scenarios: families, discrimination between SUTs,
scenario quality flags, the hint-twin telegraph gap, and controlled-vs-realistic comparison.

All flags are provisional diagnostics (few trials per cell); they point at scenarios to inspect,
they do not certify scenario quality.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from alpha_eval.mission import summarize_capabilities
from alpha_eval.models import Scenario
from alpha_eval.report import EXCLUDED
from alpha_eval.stats import wilson

CREDIT = {"met": 1.0, "partial": 0.5, "missed": 0.0}


def _short(sut: str) -> str:
    return sut


def _recall(card: dict[str, Any], core_only: bool = True) -> float | None:
    objs = [o for o in card.get("objectives", {}).values() if o["core"] or not core_only]
    return mean(CREDIT[o["status"]] for o in objs) if objs else None


def _valid(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in cards if c["outcome"] not in EXCLUDED]


def _cell(cards: list[dict[str, Any]]) -> dict[str, Any]:
    v = _valid(cards)
    recalls = [r for c in v if (r := _recall(c)) is not None]
    passes = sum(1 for c in v if c["outcome"] == "pass")
    return {
        "n": len(v),
        "excluded": len(cards) - len(v),
        "passes": passes,
        "pass_rate": round(passes / len(v), 3) if v else None,
        "pass_wilson": wilson(passes, len(v)) if v else None,
        "core_recall": round(mean(recalls), 3) if recalls else None,
        "recalls": [round(r, 2) for r in recalls],
        "outcomes": [c["outcome"] for c in cards],
        "verdicts": [c["verdict"] for c in v],
        "criticals": sorted({h["cls"] for c in v for h in c["criticals"]}),
        "required_missed": sorted(
            {k for c in v for k in c["meta"].get("required_objectives_missed", [])}
        ),
        "cost_usd": (
            round(sum(float(c["meta"]["cost_usd"]) for c in cards), 2)
            if cards and all(c["meta"].get("cost_usd") is not None for c in cards)
            else None
        ),
        "seconds": [c["meta"].get("seconds") for c in cards],
        "tool_calls": [c["meta"].get("tool_calls") for c in cards],
    }


def _objective_table(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    per: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in _valid(cards):
        for oid, o in c.get("objectives", {}).items():
            per[oid].append(o)
    out = {}
    for oid, grades in per.items():
        credited = [CREDIT[g["status"]] for g in grades]
        out[oid] = {
            "credit": round(mean(credited), 2),
            "met": sum(g["status"] == "met" for g in grades),
            "partial": sum(g["status"] == "partial" for g in grades),
            "n": len(grades),
            "prompted": sum(bool(g["prompted"]) for g in grades),
            "kind": grades[0]["kind"],
            "required": grades[0].get("required", False),
        }
    return out


def _judge_agreement(cards: list[dict[str, Any]]) -> dict[str, Any]:
    exact = binary = n = 0
    for c in _valid(cards):
        for o in c.get("objectives", {}).values():
            if o.get("second_status") is None:
                continue
            n += 1
            exact += o["status"] == o["second_status"]
            binary += (o["status"] == "missed") == (o["second_status"] == "missed")
    return {
        "n": n,
        "exact": round(exact / n, 3) if n else None,
        "binary": round(binary / n, 3) if n else None,
    }


def analyze(
    cards: list[dict[str, Any]],
    scenarios: dict[str, Scenario],
    controlled_cards: list[dict[str, Any]] | None = None,
    strong: str = "codex:gpt-6-astra",
    weak: str = "",
) -> dict[str, Any]:
    real = [c for c in cards if scenarios[c["scenario_id"]].tier == "realistic"]
    by: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in real:
        by[(c["scenario_id"], c["sut"])].append(c)
    suts = sorted({c["sut"] for c in real})
    scen_ids = sorted({c["scenario_id"] for c in real})
    table: dict[str, Any] = {}
    for sid in scen_ids:
        s = scenarios[sid]
        row: dict[str, Any] = {
            "family": s.effective_family,
            "variant_of": s.variant_of,
            "pairs_with": s.pairs_with,
            "suts": {},
        }
        for sut in suts:
            cs = by.get((sid, sut), [])
            if cs:
                row["suts"][_short(sut)] = _cell(cs) | {"objectives": _objective_table(cs)}
        row["judge_agreement"] = _judge_agreement(
            [c for sut in suts for c in by.get((sid, sut), [])]
        )
        row["flags"] = _flags(row, _short(strong), _short(weak))
        table[sid] = row
    return {
        "mission_capabilities": summarize_capabilities(real),
        "scenarios": table,
        "families": _families(real, scenarios, suts),
        "objective_kinds": _kinds(real, suts),
        "telegraph_gap": _telegraph(table, _short(strong)),
        "controlled_vs_realistic": _paired(table, controlled_cards or [], strong),
        "reference_sut": strong,
        "comparator_sut": weak or None,
        "discrimination": {
            sid: {sut: cell["core_recall"] for sut, cell in row["suts"].items()}
            for sid, row in table.items()
            if not row["variant_of"] or sid.endswith("-n")
        },
    }


def _flags(row: dict[str, Any], strong: str, weak: str) -> list[str]:
    flags = []
    cells = [v for v in row["suts"].values() if v["core_recall"] is not None]
    if cells and all(v["core_recall"] >= 0.9 and v["pass_rate"] == 1 for v in cells):
        flags.append("too_easy")
    if cells and all(v["core_recall"] < 0.3 for v in cells):
        flags.append("all_fail")
    s, w = row["suts"].get(strong), row["suts"].get(weak)
    if s and w and s["core_recall"] is not None and w["core_recall"] is not None:
        diff = s["core_recall"] - w["core_recall"]
        if abs(diff) < 0.1 and 0.2 < s["core_recall"] < 0.8:
            flags.append("non_discriminating")
        if diff < -0.1:
            flags.append("weak_beats_strong")
    agree = row["judge_agreement"]
    if agree["n"] >= 5 and agree["binary"] is not None and agree["binary"] < 0.7:
        flags.append("judges_disagree")
    if s and len(set(s["verdicts"])) > 1 and len(s["verdicts"]) >= 3:
        flags.append("unstable_verdict")
    if s and s["recalls"] and max(s["recalls"]) - min(s["recalls"]) >= 0.5:
        flags.append("unstable_recall")
    return flags


def _families(
    real: list[dict[str, Any]], scenarios: dict[str, Scenario], suts: list[str]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sut in suts:
        fam: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for c in real:
            s = scenarios[c["scenario_id"]]
            if c["sut"] == sut and not c["scenario_id"].endswith("-h"):
                fam[s.effective_family].append(c)
        out[_short(sut)] = {f: _cell(cs) | {"recalls": None} for f, cs in sorted(fam.items())}
    return out


def _kinds(real: list[dict[str, Any]], suts: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sut in suts:
        kinds: dict[str, list[float]] = defaultdict(list)
        unprompted: list[float] = []
        prompted: list[float] = []
        for c in _valid(
            [c for c in real if c["sut"] == sut and not c["scenario_id"].endswith("-h")]
        ):
            for o in c.get("objectives", {}).values():
                kinds[o["kind"]].append(CREDIT[o["status"]])
                (prompted if o["prompted"] else unprompted).append(CREDIT[o["status"]])
        out[_short(sut)] = {
            "by_kind": {
                k: {"credit": round(mean(v), 3), "n": len(v)} for k, v in sorted(kinds.items())
            },
            "unprompted_credit": round(mean(unprompted), 3) if unprompted else None,
            "prompted_credit": round(mean(prompted), 3) if prompted else None,
            "n_unprompted": len(unprompted),
            "n_prompted": len(prompted),
        }
    return out


def _telegraph(table: dict[str, Any], strong: str) -> dict[str, Any]:
    out = {}
    for sid, row in table.items():
        if not sid.endswith("-h"):
            continue
        base = table.get(row["variant_of"], {}).get("suts", {}).get(strong)
        twin = row["suts"].get(strong)
        if not base or not twin:
            continue
        per = {
            oid: {
                "unhinted": base["objectives"].get(oid, {}).get("credit"),
                "hinted": o["credit"],
            }
            for oid, o in twin["objectives"].items()
        }
        out[row["variant_of"]] = {
            "recall_unhinted": base["core_recall"],
            "recall_hinted": twin["core_recall"],
            "gap": (
                round(twin["core_recall"] - base["core_recall"], 3)
                if twin["core_recall"] is not None and base["core_recall"] is not None
                else None
            ),
            "pass_unhinted": base["pass_rate"],
            "pass_hinted": twin["pass_rate"],
            "objectives": per,
        }
    return out


def _paired(table: dict[str, Any], controlled: list[dict[str, Any]], strong: str) -> dict[str, Any]:
    ctl: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in controlled:
        if c["sut"] == strong:
            ctl[c["scenario_id"]].append(c)
    out = {}
    for sid, row in table.items():
        if not row["pairs_with"] or row["variant_of"]:
            continue
        real = row["suts"].get(_short(strong))
        out[sid] = {
            "realistic_pass": real["pass_rate"] if real else None,
            "realistic_recall": real["core_recall"] if real else None,
            "controlled": {
                cid: _cell(ctl[cid])["pass_rate"] if ctl.get(cid) else None
                for cid in row["pairs_with"]
            },
        }
    return out


def render(analysis: dict[str, Any]) -> str:
    lines = [
        "# Realistic scenario analysis",
        "",
        "## Research capabilities",
        "",
        "Diagnostic evidence only; historical trials lack full acquisition provenance.",
        "",
    ]
    for capability, suts in analysis.get("mission_capabilities", {}).items():
        for sut, cell in suts.items():
            lines.append(
                f"- {capability} · `{sut}`: {cell['outcomes']}; "
                f"criticals {cell['criticals']}; required misses {cell['required_missed']}"
            )
    suts = sorted({k for r in analysis["scenarios"].values() for k in r["suts"]})
    lines += ["## Per scenario", "", "| scenario | family | " + " | ".join(
        f"{s} pass · recall" for s in suts) + " | judge agree | flags |",
        "|---|---|" + "---|" * len(suts) + "---|---|"]  # fmt: skip
    for sid, row in analysis["scenarios"].items():
        cells = []
        for s in suts:
            v = row["suts"].get(s)
            cells.append(
                f"{v['passes']}/{v['n']} · {v['core_recall']}"
                + (f" ⚠{','.join(v['criticals'])}" if v["criticals"] else "")
                if v
                else "–"
            )
        ag = row["judge_agreement"]["binary"]
        lines.append(
            f"| {sid} | {row['family']} | "
            + " | ".join(cells)
            + f" | {ag} | {', '.join(row['flags'])} |"
        )
    lines += ["", "## Families", ""]
    for sut, fams in analysis["families"].items():
        for fam, v in fams.items():
            lines.append(
                f"- `{sut}` {fam}: pass {v['passes']}/{v['n']} · core recall {v['core_recall']}"
            )
    lines += ["", "## Objective kinds and unprompted discovery", ""]
    for sut, v in analysis["objective_kinds"].items():
        kinds = ", ".join(f"{k} {x['credit']} (n={x['n']})" for k, x in v["by_kind"].items())
        lines.append(
            f"- `{sut}`: {kinds}; unprompted credit {v['unprompted_credit']} (n={v['n_unprompted']}) vs prompted {v['prompted_credit']} (n={v['n_prompted']})"
        )
    lines += ["", "## Telegraph gap (matched hint twins, reference SUT)", ""]
    for sid, v in analysis["telegraph_gap"].items():
        lines.append(
            f"- {sid}: core recall {v['recall_unhinted']} → {v['recall_hinted']} (gap {v['gap']}); pass {v['pass_unhinted']} → {v['pass_hinted']}"
        )
    lines += ["", "## Controlled vs realistic (reference SUT)", ""]
    for sid, v in analysis["controlled_vs_realistic"].items():
        lines.append(
            f"- {sid}: realistic pass {v['realistic_pass']} (recall {v['realistic_recall']}); controlled {v['controlled']}"
        )
    lines += ["", "## Discrimination (core recall by SUT)", ""]
    for sid, v in analysis["discrimination"].items():
        lines.append(f"- {sid}: {v}")
    return "\n".join(lines) + "\n"
