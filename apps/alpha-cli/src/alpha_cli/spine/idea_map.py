"""The idea file's map: the creators' pipeline as facts, each done or not yet. Never a gate."""

from __future__ import annotations

from typing import Any

DONE, NOT_YET, UNKNOWN, NOT_BUILT = "done", "not yet", "not recorded", "not built yet"
COSTS_TOOL = "costs.break_even"


def build_map(
    card_id: str,
    runs: list[dict[str, Any]],
    finds: list[dict[str, Any]],
    follows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    read = [r for r in runs if r["reading"] is not None and r["word"] != "fault"]
    unread = bool(runs or finds) and not read and not finds
    studies = [s["id"] for f in finds for s in f["studies"] if not s["problem"]]
    nulls = [r["id"] for r in read if r["_manifest"].get("nulls")]
    aims = [r["id"] for r in read if r["aim"] is not None]
    variants = [r["id"] for r in read if (r["reading"]["counts"].get("variants_tried") or 0) > 0]
    settings: dict[str, set[str]] = {}
    for r in read:
        rule = r["tested"].get("rule") or ""
        settings.setdefault(rule.split(" (")[0], set()).add(rule)
    if any(len(found) > 1 for found in settings.values()):
        variants = [r["id"] for r in read]
    costs = [c["file"] for r in read for c in r["checks"] if c["tool"] == COSTS_TOOL]
    oos = [
        r["id"]
        for r in read
        if any(
            m["name"] == "out-of-sample Sharpe" and m["value"] is not None
            for m in r["reading"]["measures"]
        )
    ]

    def line(step: str, evidence: list[str], note: str = "") -> dict[str, Any]:
        state = DONE if evidence else UNKNOWN if unread else NOT_YET
        return {"step": step, "state": state, "evidence": evidence, "note": note}

    return [
        {"step": "card written", "state": DONE, "evidence": [card_id], "note": ""},
        line("examples looked at", [f["id"] for f in finds], "a setup find linked to the card"),
        line("compared with controls", studies + nulls, "a setup study, or a random-data test"),
        line("compared with a simple baseline", aims, "an aim row in a reading"),
        line("settings checked", variants, "other settings of the rule were tried and recorded"),
        line("costs checked", costs, "a stored break-even cost check"),
        line("out-of-sample numbers recorded", oos, "no out-of-sample Sharpe is stored"),
        {"step": "held-back confirmation", "state": NOT_BUILT, "evidence": [], "note": ""},
        line(
            "followed forward on paper",
            [f["follow_id"] for f in follows or []],
            "no paper follow names this card",
        ),
    ]


def next_steps(
    card_id: str, steps: list[dict[str, Any]], finds: list[dict[str, Any]]
) -> list[dict[str, str]]:
    find = finds[0]["id"] if finds else "<find id>"
    test = f"alpha test <spec.toml> --idea-card {card_id}"
    commands = {
        "examples looked at": "alpha setup find <spec.toml>",
        "compared with controls": f"alpha setup study {find}",
        "compared with a simple baseline": test,
        "settings checked": 'alpha tool find "how sensitive are the settings"',
        "costs checked": 'alpha tool find "how much cost would remove the edge"',
        "out-of-sample numbers recorded": test,
    }
    return [
        {"step": s["step"], "command": commands[s["step"]]}
        for s in steps
        if s["state"] == NOT_YET and s["step"] in commands
    ]
