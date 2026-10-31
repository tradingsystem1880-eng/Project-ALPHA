"""Bounded discovery must retain denials, reconcile results and stop without retries."""

import json
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import polars as pl
import pytest

from alpha_cli import _runner
from alpha_cli.artifact_contract import artifact_contract
from alpha_cli.research_execution import BaselineExecutionPlan
from alpha_cli.research_execution_digest import execution_digest
from alpha_core import DataError


def run_fixture(root: Path, *, pretrade_rejection: bool = False) -> Path:
    directory = root / "1234567890abcdef"
    directory.mkdir()
    ts = datetime(2020, 1, 2, tzinfo=UTC)
    pl.DataFrame(
        {
            "sequence_id": [1, 2],
            "ts": [ts, ts],
            "instrument_id": ["TEST.SIM"] * 2,
            "side": ["BUY"] * 2,
            "quantity": [1.0, 2.0],
            "filled_quantity": [1.0, 0.0],
            "status": ["FILLED", "DENIED"],
        }
    ).write_parquet(directory / "orders.parquet")
    pl.DataFrame(
        {
            "sequence_id": [1],
            "order_sequence_id": [1],
            "ts": [ts],
            "instrument_id": ["TEST.SIM"],
            "side": ["BUY"],
            "quantity": [1.0],
            "price": [10.0],
        }
    ).write_parquet(directory / "fills.parquet")
    pl.DataFrame(
        schema={
            "instrument_id": pl.String,
            "entry_ts": pl.Datetime("us", "UTC"),
            "exit_ts": pl.Datetime("us", "UTC"),
        }
    ).write_parquet(directory / "trades.parquet")
    pl.DataFrame(
        {"ts": [datetime(2020, 1, 1, tzinfo=UTC), ts], "equity": [100.0, 100.0]}
    ).write_parquet(directory / "equity_curve.parquet")
    if pretrade_rejection:
        pl.DataFrame(
            {
                "sequence_id": [1],
                "ts": [ts],
                "instrument_id": ["TEST.SIM"],
                "side": ["BUY"],
                "requested_quantity": [1.0],
                "reference_price": [10.0],
                "available_cash": [10.0],
                "estimated_fee": [0.01],
                "required_cash": [10.01],
                "reason": ["cash_plus_commission_exceeds_free_balance"],
            }
        ).write_parquet(directory / "pretrade_rejections.parquet")
    manifest = {
        "schema_version": 3,
        "run_identity_version": 3,
        "artifact_contract_version": 3,
        "run_id": directory.name,
        "command": "backtest_run",
        "symbol": "TEST",
        "snapshot_id": "frozen",
        "snapshot_hash": "a" * 64,
        "execution_fingerprint": "b" * 64,
        "strategy_fingerprint": "c" * 64,
        "source_fingerprint": "d" * 64,
        "research_cutoff": "2020-01-02",
        "orders": 2,
        "fills": 1,
        "rejected": 1 + int(pretrade_rejection),
        "pretrade_rejections": int(pretrade_rejection),
        "n_trades": 0,
        "params": {"fee_bps": 1.0, "slippage_bps": 2.0, "starting_cash": 100.0},
        "artifacts": artifact_contract(directory),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory


def test_digest_retains_denial_and_missing_reason(tmp_path: Path) -> None:
    digest = execution_digest(run_fixture(tmp_path), cutoff="2020-01-02", expected_sessions=2)
    assert digest["orders_by_status"] == {"DENIED": 1, "FILLED": 1}
    assert digest["denied_or_rejected_orders"] == 1
    assert digest["fill_events"] == 1
    assert digest["closed_trades"] == 0
    assert digest["sessions"]["coverage"] == "reconciled"
    assert "rejection_reasons" in digest["unavailable"]
    assert digest["admitted"] is False


def test_digest_reconciles_pretrade_suppression_separately_from_submitted_orders(
    tmp_path: Path,
) -> None:
    digest = execution_digest(
        run_fixture(tmp_path, pretrade_rejection=True),
        cutoff="2020-01-02",
        expected_sessions=2,
    )
    assert digest["orders_by_status"] == {"DENIED": 1, "FILLED": 1}
    assert digest["denied_or_rejected_orders"] == 2
    assert digest["pretrade_rejections"] == {
        "count": 1,
        "by_reason": {"cash_plus_commission_exceeds_free_balance": 1},
    }
    assert "pretrade_rejections" in digest["evidence"]


@pytest.mark.parametrize(
    "change", ["bytes", "count", "cutoff", "sessions", "fill_link", "future", "missing"]
)
def test_digest_rejects_inconsistent_evidence(tmp_path: Path, change: str) -> None:
    directory = run_fixture(tmp_path)
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    if change == "bytes":
        (directory / "orders.parquet").write_bytes(b"tampered")
    elif change == "count":
        manifest["rejected"] = 0
    elif change == "cutoff":
        manifest["research_cutoff"] = "2020-01-01"
    elif change == "fill_link":
        fills = pl.read_parquet(directory / "fills.parquet").with_columns(
            pl.lit(2).alias("order_sequence_id")
        )
        fills.write_parquet(directory / "fills.parquet")
        manifest["artifacts"] = artifact_contract(directory)
    elif change == "future":
        frame = pl.read_parquet(directory / "equity_curve.parquet").with_columns(
            pl.Series("ts", [datetime(2020, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC)])
        )
        frame.write_parquet(directory / "equity_curve.parquet")
        manifest["artifacts"] = artifact_contract(directory)
    elif change == "missing":
        (directory / "fills.parquet").unlink()
        manifest["artifacts"] = artifact_contract(directory)
    path.write_text(json.dumps(manifest))
    with pytest.raises(DataError):
        execution_digest(
            directory, cutoff="2020-01-02", expected_sessions=3 if change == "sessions" else 2
        )


def test_plan_has_no_arbitrary_commands_or_unbounded_work() -> None:
    from pydantic import ValidationError

    from alpha_cli.research_execution import BaselineExecutionPlan, command_args

    plan = BaselineExecutionPlan(symbol="TEST", snapshot="frozen", as_of="2020-01-02")
    for stage in ("baseline", "validation"):
        args = command_args(plan, stage)
        assert args[args.index("--as-of") + 1] == "2020-01-02"
        assert args[args.index("--snapshot") + 1] == "frozen"
        assert "--research-gate-override" not in args
    for fields in (
        {"command": "rm -rf /"},
        {"strategy": "kronos"},
        {"seconds": 100000},
        {"as_of": "tomorrow"},
        {"snapshot": "../elsewhere"},
        {"max_leverage": float("nan")},
    ):
        with pytest.raises(ValidationError):
            BaselineExecutionPlan.model_validate({**plan.model_dump(), **fields})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", True),
        ("seed", True),
        ("target_vol", True),
    ],
)
def test_plan_rejects_boolean_numeric_coercion(field: str, value: object) -> None:
    from pydantic import ValidationError

    rules_spec = (
        '{"name":"fixed","long_when":[{"left":{"source":"close"},"op":">","right":{"value":1}}]}'
    )
    payload: dict[str, object] = {
        "symbol": "TEST",
        "snapshot": "frozen",
        "as_of": "2020-01-02",
        "strategy": "rules",
        "rules_spec": rules_spec,
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        BaselineExecutionPlan.model_validate_json(json.dumps(payload))


def test_plan_preserves_numeric_coercions_and_canonical_plan_identity() -> None:
    import hashlib

    common: dict[str, object] = {
        "symbol": "TEST",
        "snapshot": "frozen",
        "as_of": "2020-01-02",
        "strategy": "rules",
        "rules_spec": (
            '{"name":"fixed","long_when":[{"left":{"source":"close"},'
            '"op":">","right":{"value":1}}]}'
        ),
    }
    canonical = BaselineExecutionPlan.model_validate_json(
        json.dumps(
            {
                **common,
                "schema_version": 1,
                "skip": 1,
                "rebalance_every": 1,
                "target_vol": 1.0,
            }
        )
    )
    coerced = BaselineExecutionPlan.model_validate_json(
        json.dumps(
            {
                **common,
                "schema_version": 1.0,
                "skip": "1",
                "rebalance_every": 1.0,
                "target_vol": 1,
            }
        )
    )
    canonical_plan = json.dumps(canonical.model_dump(mode="json"), sort_keys=True)
    coerced_plan = json.dumps(coerced.model_dump(mode="json"), sort_keys=True)

    assert coerced.skip == 1
    assert coerced.rebalance_every == 1
    assert coerced.target_vol == 1.0
    assert (
        hashlib.sha256(coerced_plan.encode()).digest()
        == hashlib.sha256(canonical_plan.encode()).digest()
    )


def test_child_timeout_reaps_and_returns_receipt(tmp_path: Path) -> None:
    import sys

    from alpha_cli.research_execution import run_child

    outcome = run_child(
        [sys.executable, "-c", "import time; print('started',flush=True); time.sleep(30)"],
        output=tmp_path / "child.log",
        seconds=0.1,
    )
    assert outcome["status"] == "timeout"
    assert outcome["returncode"] is not None
    assert "started" in (tmp_path / "child.log").read_text()


def controller_setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[ModuleType, BaselineExecutionPlan]:
    from types import SimpleNamespace

    from alpha_cli import research_execution as controller

    monkeypatch.setattr(_runner, "load_bars", lambda *a, **kw: ([SimpleNamespace()] * 2, "frozen"))
    monkeypatch.setattr(_runner, "verified_snapshot_hash", lambda *a: "a" * 64)
    plan = controller.BaselineExecutionPlan(symbol="TEST", snapshot="frozen", as_of="2020-01-02")
    return controller, plan


def test_failed_baseline_stops_and_replay_does_not_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    controller, plan = controller_setup(monkeypatch, tmp_path)
    calls = []

    def failed(args: list[str], *, output: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append(args)
        output.write_text("exact engine failure")
        return {"status": "failed", "returncode": 2}

    monkeypatch.setattr(controller, "run_child", failed)
    first = controller.execute_plan(plan, data_dir=tmp_path)
    assert first["status"] == "honest_block"
    assert first["missing_evidence"] == ["baseline", "validation"]
    assert "exact engine failure" in first["attempts"][0]["error_tail"]
    assert controller.execute_plan(plan, data_dir=tmp_path) == first
    assert len(calls) == 1


def test_interrupted_attempt_cannot_replenish_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    controller, plan = controller_setup(monkeypatch, tmp_path)

    def crashed(*args: Any, **kwargs: Any) -> None:
        raise SystemExit("simulated process death")

    monkeypatch.setattr(controller, "run_child", crashed)
    with pytest.raises(SystemExit):
        controller.execute_plan(plan, data_dir=tmp_path)
    result = controller.execute_plan(plan, data_dir=tmp_path)
    assert result["status"] == "infrastructure_invalid"
    assert result["stop_reason"] == "interrupted_attempt_not_retried"
    assert len(result["attempts"]) == 1


@pytest.mark.usefixtures("owned_test_process")
def test_sigterm_reaps_child_and_returns_interrupted(tmp_path: Path) -> None:
    import os
    import signal
    import subprocess
    import sys
    import time

    marker = tmp_path / "child.pid"
    descendant_marker = tmp_path / "descendant.pid"
    descendant_script = (
        "import os,time,pathlib,signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"marker=pathlib.Path({str(descendant_marker)!r}); pending=marker.with_suffix('.ready'); "
        "pending.write_text(str(os.getpid())); pending.replace(marker); time.sleep(30)"
    )
    script = (
        "import os,time,pathlib,subprocess; "
        f"subprocess.Popen({[sys.executable, '-c', descendant_script]!r}); "
        f"marker=pathlib.Path({str(marker)!r}); pending=marker.with_suffix('.ready'); "
        "pending.write_text(str(os.getpid())); pending.replace(marker); time.sleep(30)"
    )
    parent_script = (
        "import json; from pathlib import Path; "
        "from alpha_cli.research_execution import run_child; "
        f"print(json.dumps(run_child({[sys.executable, '-c', script]!r}, "
        f"output=Path({str(tmp_path / 'log')!r}), seconds=20)), flush=True)"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", parent_script], stdout=subprocess.PIPE, text=True
    )
    child = None
    try:
        deadline = time.monotonic() + 5
        while (
            not marker.exists() or not descendant_marker.exists()
        ) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists() and descendant_marker.exists()
        child = int(marker.read_text())
        parent.terminate()
        output, _ = parent.communicate(timeout=8)
        assert parent.returncode == 0
        assert json.loads(output)["status"] == "interrupted"
        with pytest.raises(ProcessLookupError):
            os.kill(child, 0)
        with pytest.raises(ProcessLookupError):
            os.kill(int(descendant_marker.read_text()), 0)
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()
        if child is not None:
            with suppress(ProcessLookupError):
                os.killpg(child, signal.SIGKILL)
        if parent.stdout is not None:
            parent.stdout.close()


def test_success_replay_and_receipt_tamper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    controller, plan = controller_setup(monkeypatch, tmp_path)
    calls = []

    def success(args: list[str], *, output: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append(args)
        output.write_text("terminal run")
        return {"status": "completed", "returncode": 0}

    monkeypatch.setattr(controller, "run_child", success)
    monkeypatch.setattr(controller, "_collect", lambda *args: {"source_fingerprint": "same"})
    first = controller.execute_plan(plan, data_dir=tmp_path)
    assert first["status"] == "completed_evidence"
    assert first["missing_evidence"] == []
    assert controller.execute_plan(plan, data_dir=tmp_path) == first
    assert len(calls) == 2
    receipt_path = Path(first["receipt"])
    receipt_path.write_text(
        receipt_path.read_text().replace("fixed_measurements_completed", "altered")
    )
    with pytest.raises(DataError, match="immutable"):
        controller.execute_plan(plan, data_dir=tmp_path)


def test_reserve_prevents_dispatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    controller, plan = controller_setup(monkeypatch, tmp_path)
    ticks = iter([0, 25])
    monkeypatch.setattr(controller.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(controller, "run_child", lambda *a, **k: pytest.fail("must not launch"))
    result = controller.execute_plan(plan.model_copy(update={"seconds": 30}), data_dir=tmp_path)
    assert result["stop_reason"] == "budget_reserved_for_reconciliation"
    assert result["attempts"] == []


def test_digest_wrong_schedule_fails_even_when_count_matches(tmp_path: Path) -> None:
    directory = run_fixture(tmp_path)
    with pytest.raises(DataError, match="schedule"):
        execution_digest(
            directory,
            cutoff="2020-01-02",
            expected_timestamps=[
                datetime(2019, 12, 31, tzinfo=UTC),
                datetime(2020, 1, 2, tzinfo=UTC),
            ],
        )


def test_restart_after_completed_baseline_does_not_launch_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    controller, plan = controller_setup(monkeypatch, tmp_path)
    publish = controller._publish

    def crash_after_record(path: Path, value: dict[str, Any]) -> None:
        publish(path, value)
        if path.name == "baseline.result.json":
            raise SystemExit("controller died between steps")

    def success(args: list[str], *, output: Path, **kwargs: Any) -> dict[str, Any]:
        output.write_text("terminal run")
        return {"status": "completed", "returncode": 0}

    monkeypatch.setattr(controller, "_publish", crash_after_record)
    monkeypatch.setattr(controller, "run_child", success)
    monkeypatch.setattr(controller, "_collect", lambda *args: {"source_fingerprint": "same"})
    with pytest.raises(SystemExit):
        controller.execute_plan(plan, data_dir=tmp_path)
    monkeypatch.setattr(controller, "_publish", publish)
    monkeypatch.setattr(controller, "run_child", lambda *a, **k: pytest.fail("must not launch"))
    result = controller.execute_plan(plan, data_dir=tmp_path)
    assert result["status"] == "infrastructure_invalid"
    assert result["missing_evidence"] == ["validation"]
    assert result["stop_reason"] == "interrupted_budget_not_replenished"


def test_identical_concurrent_execution_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    controller, plan = controller_setup(monkeypatch, tmp_path)

    def success(args: list[str], *, output: Path, **kwargs: Any) -> dict[str, Any]:
        with pytest.raises(DataError, match="already running"):
            controller.execute_plan(plan, data_dir=tmp_path)
        output.write_text("bounded failure")
        return {"status": "failed", "returncode": 2}

    monkeypatch.setattr(controller, "run_child", success)
    assert controller.execute_plan(plan, data_dir=tmp_path)["status"] == "honest_block"


@pytest.mark.parametrize(
    "mismatch",
    [
        None,
        "symbol",
        "snapshot_id",
        "max_leverage",
        "strategy_name",
        "execution_fingerprint",
        "rules_spec",
    ],
)
def test_collect_checks_terminal_receipt_and_frozen_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mismatch: str | None
) -> None:
    from types import SimpleNamespace

    from alpha_cli import _identity, research_execution

    (tmp_path / "runs").mkdir()
    directory = run_fixture(tmp_path / "runs")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan = BaselineExecutionPlan(symbol="TEST", snapshot="frozen", as_of="2020-01-02")
    config = plan.model_dump(mode="json")
    config.update(
        strategy_name=plan.strategy, account_type="CASH", allow_short=False, periods_per_year=252
    )
    manifest["params"] = config
    if mismatch in {"max_leverage", "strategy_name", "rules_spec"}:
        config[mismatch] = "wrong"
    elif mismatch is not None:
        manifest[mismatch] = "c" * 64 if mismatch == "execution_fingerprint" else "wrong"
    manifest_path.write_text(json.dumps(manifest))
    log = tmp_path / "child.log"
    log.write_text(f"backtest TEST -> run {directory.name}: done\n")
    monkeypatch.setattr(_identity, "execution_fingerprint", lambda: "b" * 64)
    monkeypatch.setattr(
        _runner,
        "load_bars",
        lambda *a, **kw: (
            [
                SimpleNamespace(ts=datetime(2020, 1, 1, tzinfo=UTC)),
                SimpleNamespace(ts=datetime(2020, 1, 2, tzinfo=UTC)),
            ],
            "frozen",
        ),
    )
    if mismatch is not None:
        with pytest.raises(DataError):
            research_execution._collect(plan, "baseline", log, tmp_path, "a" * 64, 2)
    else:
        result = research_execution._collect(plan, "baseline", log, tmp_path, "a" * 64, 2)
        assert result["sessions"]["expectation_source"] == "snapshot_schedule"
        assert result["denied_or_rejected_orders"] == 1
        log.write_text("child exited without a receipt")
        with pytest.raises(DataError, match="terminal run receipt"):
            research_execution._collect(plan, "baseline", log, tmp_path, "a" * 64, 2)


def test_digest_cli_exposes_denials_and_rejects_path_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    from alpha_cli.research_diagnostic_cmds import diagnostic_app

    (tmp_path / "runs").mkdir()
    directory = run_fixture(tmp_path / "runs")
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(
        diagnostic_app, ["execution-digest", directory.name, "--as-of", "2020-01-02"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["denied_or_rejected_orders"] == 1
    invalid = runner.invoke(
        diagnostic_app, ["execution-digest", "../../other", "--as-of", "2020-01-02"]
    )
    assert invalid.exit_code != 0
    assert "16-hex run ID" in invalid.output


def test_rule_plan_freezes_canonical_spec_and_pairs_strategy() -> None:
    from pydantic import ValidationError

    TREND = (
        '{"name":"fixed","long_when":[{"left":{"source":"close"},"op":">","right":{"value":1}}]}'
    )

    values = dict(symbol="TEST", snapshot="frozen", as_of="2020-01-02")
    with pytest.raises(ValidationError):
        BaselineExecutionPlan(**values, strategy="rules")
    with pytest.raises(ValidationError):
        BaselineExecutionPlan(**values, rules_spec=TREND)
    plan = BaselineExecutionPlan(**values, strategy="rules", rules_spec=TREND)
    assert plan.rules_spec is not None
    assert plan.rules_spec == json.dumps(
        json.loads(plan.rules_spec), sort_keys=True, separators=(",", ":")
    )


def test_rules_dispatch_frozen_file_and_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from alpha_cli.rules_cmds import resolve_rules_spec

    TREND = (
        '{"name":"fixed","long_when":[{"left":{"source":"close"},"op":">","right":{"value":1}}]}'
    )

    controller, base = controller_setup(monkeypatch, tmp_path)
    plan = BaselineExecutionPlan(**{**base.model_dump(), "strategy": "rules", "rules_spec": TREND})
    calls = []

    def success(args: list[str], *, output: Path, **kwargs: Any) -> dict[str, Any]:
        path = Path(args[args.index("--rules-file") + 1])
        sha = args[args.index("--rules-sha256") + 1]
        assert (
            resolve_rules_spec("rules", None, tmp_path, rules_file=path, rules_sha256=sha)
            == plan.rules_spec
        )
        calls.append(str(path))
        output.write_text("terminal run")
        return {"status": "completed", "returncode": 0}

    monkeypatch.setattr(controller, "run_child", success)
    monkeypatch.setattr(controller, "_collect", lambda *a: {"source_fingerprint": "same"})
    first = controller.execute_plan(plan, data_dir=tmp_path)
    assert first["status"] == "completed_evidence"
    assert len(calls) == 2 and calls[0] == calls[1]
    assert controller.execute_plan(plan, data_dir=tmp_path) == first
    assert len(calls) == 2
    Path(calls[0]).write_text("changed")
    with pytest.raises(DataError):
        controller.execute_plan(plan, data_dir=tmp_path)


def test_rules_changed_between_stages_stop_before_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from alpha_cli.rules_cmds import resolve_rules_spec

    controller, base = controller_setup(monkeypatch, tmp_path)
    plan = BaselineExecutionPlan(
        **{
            **base.model_dump(),
            "strategy": "rules",
            "rules_spec": (
                '{"name":"fixed","long_when":[{"left":{"source":"close"},'
                '"op":">","right":{"value":1}}]}'
            ),
        }
    )
    executed = []

    def child(args: list[str], *, output: Path, **kwargs: Any) -> dict[str, Any]:
        path = Path(args[args.index("--rules-file") + 1])
        sha = args[args.index("--rules-sha256") + 1]
        resolve_rules_spec("rules", None, tmp_path, rules_file=path, rules_sha256=sha)
        executed.append(output.name)
        output.write_text("terminal run")
        path.write_text("tampered")
        return {"status": "completed", "returncode": 0}

    monkeypatch.setattr(controller, "run_child", child)
    monkeypatch.setattr(controller, "_collect", lambda *a: {"source_fingerprint": "same"})
    result = controller.execute_plan(plan, data_dir=tmp_path)
    assert executed == ["baseline.log"]
    assert result["status"] == "infrastructure_invalid"
    assert result["missing_evidence"] == ["validation"]
    assert "hash mismatch" in result["attempts"][-1]["error"]


@pytest.mark.parametrize("stage", ["baseline", "validation"])
@pytest.mark.parametrize("returned", ["matching", "missing", "different"])
def test_collect_binds_rule_specification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str, returned: str
) -> None:
    from types import SimpleNamespace

    from alpha_cli import _identity
    from alpha_cli import research_execution as controller

    (tmp_path / "runs").mkdir()
    directory = run_fixture(tmp_path / "runs")
    plan = BaselineExecutionPlan(
        symbol="TEST",
        snapshot="frozen",
        as_of="2020-01-02",
        strategy="rules",
        rules_spec='{"name":"fixed","long_when":[{"left":{"source":"close"},"op":">","right":{"value":1}}]}',
    )
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    config = plan.model_dump(mode="json")
    config.pop("rules_spec")
    config.update(
        strategy_name="rules", account_type="CASH", allow_short=False, periods_per_year=252
    )
    manifest["params" if stage == "baseline" else "metadata"] = config
    if stage == "validation":
        del manifest["params"]
        manifest.update(command="validate", folds=[{"n_test": 1}])
    destination = config if stage == "baseline" else manifest
    if returned != "missing":
        destination["rules_spec"] = plan.rules_spec if returned == "matching" else "{}"
    path.write_text(json.dumps(manifest))
    log = tmp_path / "child.log"
    log.write_text(f"run TEST -> run {directory.name}: done\n")
    monkeypatch.setattr(_identity, "execution_fingerprint", lambda: "b" * 64)
    monkeypatch.setattr(
        _runner,
        "load_bars",
        lambda *a, **kw: (
            [SimpleNamespace(ts=datetime(2020, 1, day, tzinfo=UTC)) for day in [1, 2]],
            "frozen",
        ),
    )
    monkeypatch.setattr(
        controller, "walk_forward_splits", lambda *a, **kw: [SimpleNamespace(test=range(1))]
    )
    if returned == "matching":
        assert (
            controller._collect(plan, stage, log, tmp_path, "a" * 64, 2)["run_id"] == directory.name
        )
    else:
        with pytest.raises(DataError, match="rule specification mismatch"):
            controller._collect(plan, stage, log, tmp_path, "a" * 64, 2)
