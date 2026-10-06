"""Load scenario catalogs (YAML lists) and stamp each with a hidden canary."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from alpha_eval.models import Scenario

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"


# One suite-wide canary. It is written as a header comment in every scenario file and into every
# hidden per-trial file; it never appears in anything the SUT is given. If it shows up in a SUT
# event stream, the SUT read evaluator material.
SUITE_CANARY = "AEVAL-CANARY-5c1f0e7a9b3d4e21"


def canary_for(scenario_id: str) -> str:
    del scenario_id
    return SUITE_CANARY


_VAR = re.compile(r"<<(\w+)>>")


def _substitute(value: Any, variables: dict[str, str]) -> Any:
    """Replace <<name>> placeholders (load-time variant vars; {name} stays for setup-time vars)."""
    if isinstance(value, str):
        return _VAR.sub(lambda m: str(variables[m.group(1)]), value)
    if isinstance(value, list):
        return [_substitute(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: _substitute(v, variables) for k, v in value.items()}
    return value


def expand(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """A scenario plus its variants. A variant overrides vars/world/seed/title/turns and merges
    truth fields; it keeps the base checks and criticals unless it overrides them."""
    base = {k: v for k, v in raw.items() if k not in {"variants", "vars"}}
    out = [_substitute(base, dict(raw.get("vars", {})))]
    for variant in raw.get("variants", []):
        variables = {**raw.get("vars", {}), **variant.get("vars", {})}
        merged = {
            **base,
            **{k: v for k, v in variant.items() if k not in {"suffix", "vars", "truth"}},
        }
        merged["truth"] = {**base.get("truth", {}), **variant.get("truth", {})}
        merged["id"] = f"{raw['id']}-{variant['suffix']}"
        merged["variant_of"] = raw["id"]
        out.append(_substitute(merged, variables))
    return out


def load_all(directory: Path = SCENARIO_DIR) -> list[Scenario]:
    out: list[Scenario] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.yaml")):
        items: list[dict[str, Any]] = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        for raw in (x for item in items for x in expand(item)):
            truth = dict(raw.get("truth", {}))
            truth.setdefault("canary", canary_for(raw["id"]))
            scenario = Scenario.model_validate({**raw, "truth": truth})
            if scenario.id in seen:
                raise ValueError(f"duplicate scenario id {scenario.id} in {path}")
            seen.add(scenario.id)
            out.append(scenario)
    return out


def select(scenarios: list[Scenario], ids: str = "", tiers: str = "") -> list[Scenario]:
    wanted = {i.strip() for i in ids.split(",") if i.strip()}
    tier_set = {t.strip() for t in tiers.split(",") if t.strip()}
    return [
        s
        for s in scenarios
        if (not wanted or s.id in wanted) and (not tier_set or s.tier in tier_set)
    ]
