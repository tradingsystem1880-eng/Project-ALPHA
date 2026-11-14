"""Characterise research JSON; regenerate explicitly with this module's --write CLI.

The program stories' research sequences and helpers run unchanged. Research commands
are recorded, including helper invocations and failures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

# Direct script execution must find the same test helpers that pytest imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha_cli.main import app
from tests.integration import test_research_cli as cli
from tests.integration import test_research_program_acceptance as program

_GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "research_cmds_golden.json"
Flow = Callable[[Path, pytest.MonkeyPatch], None]


def _golden_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The program golden path's research commands, before strategy development."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    ref_id = cli._register_daily_dataset(tmp_path, "SPY", cli._varied_daily_lows())
    captured = cli._invoke("capture", program._RAW_IDEA)
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])
    cli._invoke("status", project_id)
    cli._invoke("evidence-hub", project_id)
    source = cli._invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Technical trading revisited",
        "--locator",
        "doi:10.0000/example",
        "--provider",
        "crossref",
        "--access-mode",
        "metadata_only",
    )
    pack = cli._invoke("sources", "freeze", project_id, "--source-id", str(source["source_id"]))
    drafted = cli._invoke(
        *cli._daily_draft_args(project_id, str(pack["pack_id"])), "--dataset", ref_id
    )
    contract = drafted["contract"]
    assert isinstance(contract, dict)
    cli._invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "The registered daily dataset and bounded plan suit empirical D1 exploration.",
    )
    cli._invoke("run", "pilot", project_id)
    cli._invoke("run", "deep", project_id)
    confirmation = cli._invoke("draft-confirmation", project_id)
    confirmation_contract = confirmation["contract"]
    assert isinstance(confirmation_contract, dict)
    cli._approve_confirmation(project_id, str(confirmation_contract["contract_id"]))
    cli._invoke("run", "confirm", project_id)
    cli._invoke("decision-view", project_id)
    cli._invoke(
        "decide",
        project_id,
        "--outcome",
        "SUPPORTED",
        "--disposition",
        "advance_to_strategy",
        "--actor",
        "owner",
        "--reason",
        "The mechanically confirmed effect advances to strategy work.",
    )
    cli._invoke("report", project_id)
    cli._invoke("decision-view", project_id)
    promotions = program._promotion_packets(project_id)
    assert len(promotions) == 1
    for _ in range(2):
        cli._invoke("context", "show", str(promotions[0]["packet_id"]))


def _unknown_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = cli._invoke("capture", "A generic synthetic research idea")
    project = captured["project"]
    assert isinstance(project, dict)
    result = cli.runner.invoke(
        app, ["research", "run", "unknown", str(project["project_id"]), "--json"]
    )
    assert result.exit_code != 0, result.output


_FLOWS: dict[str, Flow] = {
    "golden": _golden_path,
    "non_advancing": program.test_supported_outcome_with_a_non_advancing_disposition_never_promotes,
    "parked": program.test_parked_pre_d2_case_closes_honestly_and_cannot_claim_support,
    "run_gates": cli.test_deep_and_confirmation_runs_remain_gated,
    "unknown_phase": _unknown_phase,
    "confirmation_authority": (
        cli.test_confirmation_drafting_fails_closed_without_authority_or_evidence
    ),
    "confirmation_before_deep": cli.test_confirmation_drafting_requires_a_completed_clearing_d1,
    "confirmation_degenerate": (
        cli.test_confirmation_drafting_fails_loud_on_degenerate_discovery_intervals
    ),
    "draft_datasets": cli.test_empirical_daily_draft_fails_closed_on_missing_or_mismatched_datasets,
    "draft_cross_project": (
        cli.test_draft_rejects_cross_project_source_pack_before_persisting_contract
    ),
}

# Match embedded ids too (e.g. cp_<hex16> and rd_<sha>), without matching a
# shorter hex substring inside a longer one. Preserve all surrounding literal text.
_VARIABLE = re.compile(
    r"(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"|(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))"
    r"|(?<![0-9a-f])(?P<sha>[0-9a-f]{64})(?![0-9a-f])"
    r"|(?<![0-9a-f])(?P<hex16>[0-9a-f]{16})(?![0-9a-f])"
)


# Wall-clock measurements of a run: the only literal values that differ between two runs of
# the same code.
_WALL_CLOCK_KEYS = frozenset({"elapsed_time_seconds"})


class _Normalizer:
    def __init__(self, tmp_path: Path) -> None:
        self.path = str(tmp_path)
        self.repo = str(Path(__file__).resolve().parents[2])
        self.tokens: dict[str, dict[str, str]] = {}

    def _replace(self, match: re.Match[str]) -> str:
        kind = match.lastgroup
        assert kind is not None
        values = self.tokens.setdefault(kind, {})
        value = match.group()
        if value not in values:
            values[value] = f"<{kind}-{len(values) + 1}>"
        return values[value]

    def _field(self, key: str, value: object) -> object:
        if key in _WALL_CLOCK_KEYS:
            return "<elapsed>"
        if key.endswith(".png") and isinstance(value, dict) and "size_bytes" in value:
            # PNG bytes depend on in-process Matplotlib state left by earlier tests in the same
            # worker; the image digest is already a token, so only the size is masked.
            return self.normalize({**value, "size_bytes": "<png-size>"})
        return self.normalize(value)

    def normalize(self, value: object) -> object:
        if isinstance(value, str):
            text = value.replace(self.path, "<path>").replace(self.repo, "<repo>")
            return _VARIABLE.sub(self._replace, text)
        if isinstance(value, dict):
            return {
                str(self.normalize(key)): self._field(str(key), value[key]) for key in sorted(value)
            }
        if isinstance(value, list):
            return [self.normalize(item) for item in value]
        return value


def _records(flow: str, tmp_path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    normalizer = _Normalizer(tmp_path)
    invoke = CliRunner.invoke

    def record(
        runner: CliRunner,
        command: Any,
        args: str | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> Result:
        result = invoke(runner, command, args, **kwargs)
        if isinstance(args, (list, tuple)) and args and args[0] == "research":
            payload: object = json.loads(result.stdout) if result.exit_code == 0 else result.stderr
            value = normalizer.normalize(
                {"command": ["alpha", *args], "exit_code": result.exit_code, "output": payload}
            )
            assert isinstance(value, dict)
            records.append(value)
        return result

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(CliRunner, "invoke", record)
        _FLOWS[flow](tmp_path, monkeypatch)
    assert records, flow
    return records


def _summary(record: Mapping[str, object]) -> dict[str, object]:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    command = record["command"]
    assert isinstance(command, list)
    return {
        "command": shlex.join(command),
        "exit_code": record["exit_code"],
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


@pytest.mark.parametrize("flow", _FLOWS)
def test_research_commands_match_golden(flow: str, tmp_path: Path) -> None:
    assert _GOLDEN.is_file(), "Missing golden: run this module with --write explicitly"
    expected = json.loads(_GOLDEN.read_text(encoding="utf-8"))[flow]
    actual = _records(flow, tmp_path)
    for index, record in enumerate(actual):
        summary = _summary(record)
        assert index < len(expected) and summary == expected[index], (
            f"{flow} command {index + 1}: first mismatch\n"
            f"expected: {expected[index] if index < len(expected) else '<missing>'}\n"
            f"actual: {json.dumps(record, sort_keys=True, indent=2)}"
        )
    assert len(actual) == len(expected), f"{flow}: missing commands {expected[len(actual) :]}"


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", required=True)
    parser.add_argument("--full", type=Path)
    args = parser.parse_args()
    full: dict[str, list[dict[str, object]]] = {}
    with tempfile.TemporaryDirectory(prefix="research-golden-") as directory:
        for flow in _FLOWS:
            path = Path(directory) / flow
            path.mkdir()
            full[flow] = _records(flow, path)
    golden = {flow: [_summary(record) for record in records] for flow, records in full.items()}
    _GOLDEN.write_text(json.dumps(golden, indent=2) + "\n", encoding="utf-8")
    if args.full is not None:
        args.full.write_text(json.dumps(full, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    _main()
