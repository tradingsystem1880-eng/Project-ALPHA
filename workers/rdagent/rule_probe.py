"""Actual installed ALPHA rule_signal for one committed synthetic native position trial."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any


def evaluate(request: dict[str, Any], profile_sha: str) -> dict[str, object]:
    env = Path(sys.prefix)
    profile_path = env / "rule-profile.json"
    identity = {
        "profile": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "python": hashlib.sha256((env / "bin/python").resolve().read_bytes()).hexdigest(),
        "pyvenv": hashlib.sha256((env / "pyvenv.cfg").read_bytes()).hexdigest(),
    }
    if (
        hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        != profile_sha
    ):
        raise ValueError("rule profile differs from committed admission")
    profile = json.loads(profile_path.read_text())
    site = env / "lib/python3.12/site-packages"
    files = {}
    for path in sorted(site.rglob("*")):
        if path.is_symlink() or "__pycache__" in path.parts or path.suffix == ".pyc":
            raise ValueError("unqualified rule runtime path")
        if path.is_file():
            files[str(path.relative_to(site))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if files != profile["site_files"]:
        raise ValueError("installed rule runtime bytes changed")
    from alpha_strategies.rules import rule_signal, rule_spec_from_json

    if set(request) != {"study", "study_sha256", "bars"}:
        raise ValueError("invalid fixed rule request")
    study = request["study"]
    if (
        hashlib.sha256(
            json.dumps(study, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        != request["study_sha256"]
    ):
        raise ValueError("rule study identity changed")
    # The exact versioned clocks and canonical rows were validated before admission.
    bars = request["bars"]
    raw = json.dumps(bars, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    daily = study.get("schema") == "FrozenDailyRuleStudyV1"
    costed = study.get("schema") == "FrozenRuleCostedReplaySyntheticV1"
    if daily:
        query = json.loads(study["query_document"])
        expected_bars = [
            [row[key] for key in ("open_time", "open", "high", "low", "close", "base_volume")]
            for row in query["rows"]
        ]
        if bars != expected_bars or len(bars) != 1096:
            raise ValueError("daily bars changed after exact query admission")
        if hashlib.sha256(study["query_document"].encode()).hexdigest() != study["query_sha256"]:
            raise ValueError("daily query changed after admission")
    else:
        data_hash = study["data_sha256"] if costed else study["data_artifact"]["content_sha256"]
        if hashlib.sha256(raw).hexdigest() != data_hash:
            raise ValueError("rule bars changed after admission")
    visible = bars if costed or daily else [row for row in bars if row[2] <= study["cutoff"]]
    high, low, close = (2, 3, 4) if costed or daily else (4, 5, 6)
    positions = []
    for key in ("rules_spec",) if daily else ("rules_spec", "control_spec"):
        spec = rule_spec_from_json(study[key])
        positions.append(
            [
                rule_signal(
                    spec,
                    [b[high] for b in visible[:stop]],
                    [b[low] for b in visible[:stop]],
                    [b[close] for b in visible[:stop]],
                )
                for stop in range(21 if daily else 2, len(visible) + 1)
            ]
        )
    if daily:
        positions.append([1] * len(positions[0]))
    result = {
        "schema": "DailyRulePositionsV1"
        if daily
        else "SyntheticRulePositionsV2"
        if costed
        else "SyntheticRulePositionsV1",
        "study_sha256": request["study_sha256"],
        "baseline": positions[0],
        "control": positions[1],
        "unit": "position",
        "evidence_zone": "D0",
        "real_market_evidence": False,
        "scientific_acceptance": "not_admitted",
    }
    if daily:
        result.update(
            data_origin=study["data_origin"],
            evidence_zone="D1",
            real_market_evidence=study["data_origin"] == "captured_provider_history",
        )
    economics = None
    if costed or daily:
        from costed_probe import execute

        economics = execute({**study, "bars": bars} if daily else study)
    origins = {}
    for name, module in tuple(sys.modules.items()):
        if name.startswith(
            ("alpha_core", "alpha_patterns", "alpha_strategies", "alpha_backtest", "alpha_data")
        ):
            filename = module.__file__
            if filename is None:
                raise ValueError("rule import has no source origin")
            path = Path(filename)
            relative = str(path.relative_to(site))
            if hashlib.sha256(path.read_bytes()).hexdigest() != files.get(relative):
                raise ValueError("rule import origin/hash mismatch")
            origins[name] = relative
    for name in profile["sources"]:
        dist = importlib.metadata.distribution(name)
        if Path(str(dist.locate_file(""))).resolve() != site.resolve():
            raise ValueError("rule package metadata origin mismatch")
    (Path.cwd() / "rule-origins.json").write_text(json.dumps(origins, sort_keys=True))
    for key in ("baseline", "control"):
        (Path.cwd() / (key + ".json")).write_text(
            json.dumps(
                {"schema": "RulePositionArtifactV1", "unit": "position", "positions": result[key]},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return result if economics is None else {"positions": result, "economics": economics}
