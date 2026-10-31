"""Bounded daily native evidence publication and read-back, without scientific reruns."""

from __future__ import annotations

import json
import math
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from nautilus_trader.model.objects import Price
from pydantic import TypeAdapter, ValidationError

from alpha_backtest.results import BacktestResult
from alpha_cli import _artifacts
from alpha_cli._native_daily_rule_protocol import (
    MAX_DAILY_RECEIPT_BYTES,
    canonical,
    daily_position_payload,
    daily_worker_request,
    reopen_daily_study,
    sha,
    study_from_contract,
    validate_daily_contract,
)
from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli._native_rule_economics import fixed_costed_study
from alpha_cli._native_rule_protocol import position_payload
from alpha_cli.artifact_contract import (
    ARTIFACT_CONTRACT_VERSION,
    MANIFEST_SCHEMA_VERSION,
    verify_manifest_artifacts,
)
from alpha_core import DataError

PILOT_COMMAND = "research_daily_rule_pilot_v1"
NATIVE_COMMAND = "research_daily_rule_native_v1"


def _finite(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    return True


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise DataError("daily result timestamp is invalid")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as error:
        raise DataError("daily result timestamp is invalid") from error
    if result.utcoffset() != timedelta(0):
        raise DataError("daily result timestamp must be UTC")
    return result


def same_artifact(path: Path, expected: bytes) -> bool:
    """Compare the exact expected bytes without materializing a forged oversized file."""
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as stream:
        return stream.read(len(expected) + 1) == expected


def read_json_artifact(path: Path, *, maximum_bytes: int) -> Any:
    if path.is_symlink() or not path.is_file():
        raise DataError("daily JSON artifact is missing or unsafe")
    with path.open("rb") as stream:
        raw = stream.read(maximum_bytes + 1)
    if len(raw) > maximum_bytes:
        raise DataError("daily JSON artifact exceeds frozen byte bound")
    try:
        return json.loads(raw)
    except ValueError as error:
        raise DataError("daily JSON artifact is malformed") from error


def _accounting(study: DailyRuleStudyV1, raw: dict[str, Any], rows: object) -> None:
    if not isinstance(rows, list) or not rows or len(rows) > 4_400:
        raise DataError("daily result requires bounded actual cash/fee/position observations")
    fills = raw["fill_trace"]
    seen: set[int] = set()
    cash = study.economics.starting_cash
    units = 0.0
    fees = 0.0
    previous: datetime | None = None
    expected_keys = {
        "ts",
        "instrument_id",
        "currency",
        "cash",
        "cash_free",
        "position_units",
        "commission",
        "fees_total",
        "event",
        "fill_sequence_id",
    }
    quote_times: list[datetime] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected_keys or not _finite(row):
            raise DataError("daily accounting observation shape/numerics changed")
        try:
            timestamp = datetime.fromisoformat(row["ts"])
        except (TypeError, ValueError) as error:
            raise DataError("daily accounting timestamp is invalid") from error
        if timestamp.utcoffset() != timedelta(0) or (previous is not None and timestamp < previous):
            raise DataError("daily accounting observations are not UTC chronological")
        previous = timestamp
        if row["currency"] != "USDT" or row["instrument_id"] != "BTC/USDT.SIM":
            raise DataError("daily accounting observation instrument/currency changed")
        if any(
            type(row[key]) not in (int, float)
            for key in ("cash", "cash_free", "position_units", "commission", "fees_total")
        ):
            raise DataError("daily accounting values require finite numeric units")
        commission = row["commission"]
        if commission < 0 or row["cash_free"] < -1e-8:
            raise DataError("daily accounting has negative commission/free cash")
        if row["event"] == "fill":
            sequence = row["fill_sequence_id"]
            if (
                type(sequence) is not int
                or sequence < 1
                or sequence > len(fills)
                or sequence in seen
            ):
                raise DataError("daily accounting fill identity is missing or duplicated")
            fill = fills[sequence - 1]
            if fill["sequence_id"] != sequence or fill["ts"] != row["ts"]:
                raise DataError("daily accounting fill timestamp/sequence differs")
            sign = 1 if fill["side"] == "BUY" else -1
            cash -= sign * fill["quantity"] * fill["price"] + commission
            units += sign * fill["quantity"]
            fees += commission
            seen.add(sequence)
            expected_commission = (
                fill["quantity"] * fill["price"] * study.economics.fee_bps_per_side / 10_000
            )
            if not math.isclose(commission, expected_commission, rel_tol=0, abs_tol=1e-8):
                raise DataError("daily observed commission differs from frozen per-side fee")
            if units < -1e-8 or units > study.economics.fixed_quantity_btc + 1e-8:
                raise DataError("daily accounting exceeds fixed long/flat units")
        elif row["event"] == "opening_quote_before_fills":
            if row["fill_sequence_id"] is not None or commission != 0:
                raise DataError("daily quote observation cannot masquerade as a fill")
            quote_times.append(timestamp)
        else:
            raise DataError("daily accounting observation event is unknown")
        for actual, expected in (
            (row["cash"], cash),
            (row["position_units"], units),
            (row["fees_total"], fees),
        ):
            if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-6):
                raise DataError(
                    "daily actual accounting disagrees with chronological fill cash/units/fees"
                )
    if seen != set(range(1, len(fills) + 1)):
        raise DataError("daily accounting omits canonical fills")
    query_rows = json.loads(study.query_document)["rows"]
    expected_quotes = [
        datetime.fromisoformat(row["open_time"]) + timedelta(microseconds=1)
        for row in query_rows[study.warmup_bars :]
    ]
    if quote_times != expected_quotes:
        raise DataError("daily accounting omits or changes opening cash/position observations")
    quote_rows = [row for row in rows if row["event"] == "opening_quote_before_fills"]
    curve = raw["equity_curve"]
    for index, (quote, source, sample) in enumerate(
        zip(quote_rows, query_rows[study.warmup_bars :], curve, strict=True)
    ):
        state = rows[-1] if index == len(quote_rows) - 1 else quote
        bid = float(
            Price(
                source["open"] * (1 - study.economics.half_spread_and_slippage_bps / 10_000),
                study.economics.price_precision,
            )
        )
        expected_equity = state["cash"] + state["position_units"] * bid
        if _timestamp(sample[0]) != expected_quotes[index] or not math.isclose(
            sample[1], expected_equity, rel_tol=1e-10, abs_tol=1e-6
        ):
            raise DataError(
                "daily equity differs from observed quote cash/units and frozen price mark"
            )


def validate_daily_economics(study: DailyRuleStudyV1, value: object) -> dict[str, Any]:
    """Validate recorded results and accounting only; never run another backtest."""
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema",
            "baseline",
            "control",
            "accounting",
            "scientific_acceptance",
            "outcome",
            "real_market_evidence",
            "data_origin",
            "claim_scope",
        }
        or not _finite(value)
    ):
        raise DataError("daily canonical replay result shape/numerics changed")
    if (
        value["schema"] != "DailyRuleReplayResultV1"
        or value["scientific_acceptance"] != "not_admitted"
        or value["outcome"] not in {"exploratory_complete", "accounting_rejection_inconclusive"}
        or value["data_origin"] != study.data_origin
        or value["real_market_evidence"] is not (study.data_origin == "captured_provider_history")
        or value["claim_scope"] != study.claim_scope
    ):
        raise DataError("daily replay cannot confer a different evidence claim")
    accounting = value["accounting"]
    if not isinstance(accounting, dict) or set(accounting) != {"baseline", "control"}:
        raise DataError("daily replay requires actual accounting for baseline and control")
    query_rows = json.loads(study.query_document)["rows"]
    positions = daily_position_payload(study)
    decision_times = [
        datetime.fromisoformat(row["open_time"]) + timedelta(days=1)
        for row in query_rows[study.warmup_bars :]
    ]
    fill_times = {
        datetime.fromisoformat(row["open_time"]) + timedelta(microseconds=1)
        for row in query_rows[study.warmup_bars + 1 :]
    }
    opening_prices = {
        datetime.fromisoformat(row["open_time"]) + timedelta(microseconds=1): row["open"]
        for row in query_rows[study.warmup_bars + 1 :]
    }
    for role in ("baseline", "control"):
        raw = value[role]
        if not isinstance(raw, dict) or any(
            type(raw.get(key)) is not int or raw[key] < 0 for key in ("orders", "fills", "rejected")
        ):
            raise DataError("daily replay counts must be nonnegative strict integers")
        try:
            replay = TypeAdapter(BacktestResult).validate_python(raw)
        except (ValidationError, ValueError) as error:
            raise DataError("daily replay differs from canonical BacktestResult") from error
        if (
            len(replay.equity_curve) != 1096 - study.warmup_bars
            or replay.starting_equity != study.economics.starting_cash
        ):
            raise DataError("daily replay equity coverage/starting cash differs")
        decisions = raw.get("decision_trace")
        if (
            not isinstance(decisions, list)
            or [_timestamp(row["ts"]) for row in decisions] != decision_times
            or [row["signal"] for row in decisions] != positions[role]
        ):
            raise DataError("daily replay decisions differ from exact chronological rule/control")
        fills = raw.get("fill_trace")
        orders = raw.get("order_trace")
        if (
            not isinstance(fills, list)
            or not isinstance(orders, list)
            or len(fills) != raw["fills"]
            or len(orders) != raw["orders"]
        ):
            raise DataError("daily replay order/fill counts differ from canonical traces")
        for index, fill in enumerate(fills, 1):
            if (
                type(fill.get("sequence_id")) is not int
                or fill["sequence_id"] != index
                or type(fill.get("order_sequence_id")) is not int
                or fill["order_sequence_id"] not in range(1, len(orders) + 1)
                or _timestamp(fill.get("ts")) not in fill_times
                or fill.get("side") not in {"BUY", "SELL"}
                or fill.get("instrument_id") != "BTC/USDT.SIM"
                or not math.isclose(
                    fill.get("quantity", 0),
                    study.economics.fixed_quantity_btc,
                    rel_tol=0,
                    abs_tol=1e-8,
                )
            ):
                raise DataError("daily fill changed identity, timing, instrument or fixed units")
            direction = 1 if fill["side"] == "BUY" else -1
            expected_price = float(
                Price(
                    opening_prices[_timestamp(fill["ts"])]
                    * (1 + direction * study.economics.half_spread_and_slippage_bps / 10_000),
                    study.economics.price_precision,
                )
            )
            if not math.isclose(fill["price"], expected_price, rel_tol=0, abs_tol=1e-10):
                raise DataError("daily fill price differs from frozen next-open costs/precision")
        if role == "control" and (
            len(fills) > 1
            or len(orders) > 1
            or len(raw.get("execution_rejections", [])) > 1
            or any(fill["side"] != "BUY" for fill in fills)
        ):
            raise DataError("daily predeclared buy-once control was rebalanced")
        if role == "control" and fills and _timestamp(fills[0]["ts"]) != min(fill_times):
            raise DataError("daily control entry moved past its first eligible opening")
        _accounting(study, raw, accounting[role])
    rejected = any(value[role]["rejected"] > 0 for role in ("baseline", "control"))
    if value["outcome"] != (
        "accounting_rejection_inconclusive" if rejected else "exploratory_complete"
    ):
        raise DataError("daily accounting rejection must remain distinct from valid conclusion")
    return cast(dict[str, Any], value)


def validate_daily_workspace(work: Path, study: DailyRuleStudyV1) -> None:
    """Bound accepted workspace evidence after cleanup; scratch IO is not a total-byte quota."""
    allowed = {
        "daily-admission.json",
        "baseline.json",
        "control.json",
        "rule-origins.json",
        "receipt.json",
        "progress.json",
        "payload.pid",
        "synthetic.key",
        "synthetic.key.lock",
    }
    stages = ("direct_exp_gen", "coding", "running", "feedback", "record")
    allowed.update(f"logs/__session__/0/{index}_{stage}" for index, stage in enumerate(stages))
    log = re.compile(
        r"logs/Loop_0/(?:direct_exp_gen|coding|running|feedback|record)/time_info/[0-9]{1,3}/[0-9TZ:.+_-]{1,64}\.pkl"
    )
    total, count = 0, 0
    for path in work.rglob("*"):
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        relative = path.relative_to(work).as_posix()
        if not stat.S_ISREG(metadata.st_mode) or (
            relative not in allowed and log.fullmatch(relative) is None
        ):
            raise DataError("daily workspace contains an unregistered or unsafe evidence path")
        count += 1
        total += metadata.st_size
        if count > 64 or total > study.resources.max_artifact_bytes:
            raise DataError("daily workspace exceeds aggregate admitted artifact allowance")


def _prepared_parent_manifest(rdir: Path, manifest: dict[str, Any]) -> bytes:
    """Use the canonical writer to measure the exact completion marker before admission."""
    with tempfile.TemporaryDirectory(prefix=".daily-manifest-", dir=rdir.parent) as temporary:
        staged = Path(temporary) / rdir.name
        staged.mkdir()
        for path in rdir.iterdir():
            if path.name == "manifest.json":
                continue
            if not stat.S_ISREG(path.lstat().st_mode):
                raise DataError("daily parent evidence path is unsafe")
            os.link(path, staged / path.name)
        _artifacts.write_manifest(staged, manifest)
        return (staged / "manifest.json").read_bytes()


def _publication_bytes(
    data_dir: Path,
    run_id: str,
    selectors: object,
    study: DailyRuleStudyV1,
    *,
    parent_manifest: bytes | None = None,
) -> None:
    if not isinstance(selectors, dict) or not isinstance(selectors.get("roles"), dict):
        raise DataError("daily publication requires its bounded canonical selectors")
    roots = [
        data_dir / "runs" / run_id,
        *(
            data_dir / "runs" / str(selectors["roles"][role]["run_id"])
            for role in ("baseline", "control")
        ),
        data_dir / "snapshots" / str(selectors["chart_snapshot_id"]),
    ]
    total = len(parent_manifest) if parent_manifest is not None else 0
    count = 1 if parent_manifest is not None else 0
    if total > study.resources.max_artifact_bytes:
        raise DataError("daily publication exceeds aggregate admitted artifact allowance")
    parent_path = data_dir / "runs" / run_id / "manifest.json"
    for root in roots:
        for path in root.rglob("*"):
            metadata = path.lstat()
            if stat.S_ISDIR(metadata.st_mode):
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise DataError("daily publication evidence path is unsafe")
            if parent_manifest is not None and path == parent_path:
                if not same_artifact(path, parent_manifest):
                    raise DataError("daily parent manifest differs from prepared completion marker")
                continue
            count += 1
            total += metadata.st_size
            if count > 64 or total > study.resources.max_artifact_bytes:
                raise DataError("daily publication exceeds aggregate admitted artifact allowance")


def validate_daily_native_result(
    work: Path,
    admission: dict[str, object] | None,
    study: DailyRuleStudyV1,
    expected_helpers: dict[str, str],
) -> bytes:
    from alpha_cli._native_loop_admission import SOURCE_SHA256

    validate_daily_workspace(work, study)
    path = work / "receipt.json"
    if path.is_symlink() or not path.is_file():
        raise DataError("daily native receipt is missing or unsafe")
    with path.open("rb") as stream:
        raw = stream.read(min(MAX_DAILY_RECEIPT_BYTES, study.resources.max_artifact_bytes) + 1)
    if len(raw) > min(MAX_DAILY_RECEIPT_BYTES, study.resources.max_artifact_bytes):
        raise DataError("daily native receipt exceeds frozen artifact allowance")
    try:
        receipt = json.loads(raw)
    except ValueError as error:
        raise DataError("daily native receipt is malformed") from error
    if (
        not isinstance(receipt, dict)
        or admission is None
        or receipt.get("admission") != admission
        or admission.get("schema") != "DailyNativeAdmissionV1"
        or admission.get("image_id") != study.container_image_id
        or admission.get("query_sha256") != study.query_sha256
        or admission.get("rule_request") != daily_worker_request(study)
        or receipt.get("rule_positions") != daily_position_payload(study)
        or receipt.get("authority") != "none"
        or receipt.get("synthetic") is not (study.data_origin == "artificial_fixture")
        or receipt.get("routes_enabled") is not False
        or receipt.get("imported_worker_sha256") != expected_helpers
        or receipt.get("binding_sha256") != sha(admission)
        or receipt.get("scientific_acceptance") != "not_admitted"
        or receipt.get("source_tree_sha256") != SOURCE_SHA256
        or receipt.get("checkpoint_binding_verified") is not True
        or receipt.get("checks")
        != {"events": ["direct_exp_gen", "coding", "running", "feedback", "record"]}
    ):
        raise DataError("daily native result changed admitted identity/source/positions")
    validate_daily_economics(study, receipt.get("economics"))
    positions = daily_position_payload(study)
    for role in ("baseline", "control"):
        artifact = work / (role + ".json")
        if not same_artifact(
            artifact,
            canonical(
                {
                    "schema": "RulePositionArtifactV1",
                    "unit": "position",
                    "positions": positions[role],
                }
            ).encode(),
        ):
            raise DataError("daily native position artifact differs")
    return raw


def _identity(
    contract: Mapping[str, object],
    operator: dict[str, object],
    *,
    native: bool,
    project_id: str,
    contract_id: str,
    execution_fingerprint: str,
) -> dict[str, object]:
    study = study_from_contract(contract)
    fixture = cast(dict[str, object], operator["fixture"])
    return {
        "command": NATIVE_COMMAND if native else PILOT_COMMAND,
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": sha(contract),
        "dataset_hash": study.query_sha256 if native else fixture["definition_fingerprint"],
        "execution_fingerprint": execution_fingerprint,
    }


def _parent_manifest(
    contract: Mapping[str, object],
    operator: dict[str, object],
    study: DailyRuleStudyV1,
    identity: dict[str, object],
    run_id: str,
    *,
    native: bool,
) -> dict[str, Any]:
    from alpha_cli._native_daily_rule_projection import daily_context

    project_id = str(identity["project_id"])
    watermark = (
        "ARTIFICIAL FIXTURE / NO MARKET EVIDENCE"
        if not native or study.data_origin == "artificial_fixture"
        else "EXPLORATORY / RECONSTRUCTED DISCOVERY; NOT PROMOTED"
    )
    manifest: dict[str, Any] = {
        **identity,
        **daily_context(project_id, study),
        "run_id": run_id,
        "run_identity_version": 3,
        "kind": "research",
        "source_pack_id": contract["source_pack_id"],
        "research_fingerprints": contract["hashes"],
        "evidence_zone": "D1" if native else "D0",
        "synthetic": not native or study.data_origin == "artificial_fixture",
        "data_origin": study.data_origin if native else "artificial_fixture",
        "real_market_evidence": native and study.data_origin == "captured_provider_history",
        "scientific_acceptance": "not_admitted",
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "strategy_fingerprint": None,
        "source_fingerprint": sha(contract),
        "d0_operator": operator,
        "d0_operator_fingerprint": operator["fingerprint"],
        "d0_acceptance_artifact": "d0_acceptance.json",
        "daily_rule": {
            "parent_run_id": run_id,
            "role": "parent",
            "data_origin": study.data_origin if native else "artificial_fixture",
            "query_sha256": study.query_sha256,
            "crypto_snapshot_id": study.snapshot_sha256,
        },
    }
    manifest["research_gate"]["watermark"] = watermark
    return manifest


def publish_daily_rule_run(
    data_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    execution_fingerprint: str,
    native_receipt: Mapping[str, object] | None = None,
    native_receipt_bytes: bytes | None = None,
) -> dict[str, Any]:
    from alpha_cli._native_daily_rule_projection import publish_daily_projections

    operator = validate_daily_contract(contract)
    study = study_from_contract(contract)
    native = native_receipt is not None
    if native and (
        native_receipt_bytes is None
        or canonical(json.loads(native_receipt_bytes)) != canonical(native_receipt)
    ):
        raise DataError("daily publication requires trusted observed receipt bytes")
    if not native and native_receipt_bytes is not None:
        raise DataError("daily D0 cannot carry native execution bytes")
    economics = (
        validate_daily_economics(study, native_receipt.get("economics"))
        if native_receipt is not None
        else None
    )
    if native:
        reopen_daily_study(data_dir, study)
    identity = _identity(
        contract,
        operator,
        native=native,
        project_id=project_id,
        contract_id=contract_id,
        execution_fingerprint=execution_fingerprint,
    )
    run_id = sha(identity)[:16]
    rdir = _artifacts.run_dir(data_dir, run_id)
    positions = daily_position_payload(study) if native else position_payload(True)
    payloads: dict[str, object] = {
        role + ".json": {
            "schema": "RulePositionArtifactV1",
            "unit": "position",
            "positions": positions[role],
        }
        for role in ("baseline", "control")
    }
    payloads["rule_positions.json" if native else "d0_acceptance.json"] = {
        "schema": "DailyNativeRuleResultV1" if native else "DailyRuleD0AcceptanceV1",
        **identity,
        "run_id": run_id,
        "positions": positions,
        "study": study.to_dict() if native else fixed_costed_study().to_dict(),
    }
    if native_receipt is not None and economics is not None:
        payloads.update(
            {
                "study.json": study.to_dict(),
                "query.json": json.loads(study.query_document),
                "economics.json": economics,
            }
        )
        payloads["projections.json"] = publish_daily_projections(
            data_dir,
            run_id,
            dict(native_receipt),
            study,
            project_id=project_id,
            source_fingerprint=str(cast(dict[str, object], contract["hashes"])["code"]),
        )
    for name, payload in payloads.items():

        def write_json(path: Path, text: str = canonical(payload)) -> None:
            path.write_text(text)

        _artifacts.publish_artifact(rdir / name, write_json)
    if native_receipt_bytes is not None:
        _artifacts.publish_artifact(
            rdir / "native_receipt.json", lambda path: path.write_bytes(native_receipt_bytes)
        )
    manifest = _parent_manifest(contract, operator, study, identity, run_id, native=native)
    if native_receipt is not None:
        _publication_bytes(
            data_dir,
            run_id,
            payloads["projections.json"],
            study,
            parent_manifest=_prepared_parent_manifest(rdir, manifest),
        )
    _artifacts.write_manifest(rdir, manifest)
    return _artifacts.read_manifest(rdir)


def validate_daily_rule_artifacts(
    rdir: Path,
    manifest: Mapping[str, object],
    contract: Mapping[str, object],
    *,
    source_data_dir: Path | None = None,
) -> None:
    from alpha_cli._native_daily_rule_projection import validate_daily_projections

    operator = validate_daily_contract(contract)
    study = study_from_contract(contract)
    verify_manifest_artifacts(rdir, manifest)
    native = manifest.get("command") == NATIVE_COMMAND
    if (
        manifest.get("command") not in {PILOT_COMMAND, NATIVE_COMMAND}
        or manifest.get("d0_operator") != operator
    ):
        raise DataError("daily artifact operator/command changed")
    identity = _identity(
        contract,
        operator,
        native=native,
        project_id=str(manifest["project_id"]),
        contract_id=str(manifest["research_contract_id"]),
        execution_fingerprint=str(manifest["execution_fingerprint"]),
    )
    if (
        manifest.get("run_id") != sha(identity)[:16]
        or rdir.name != manifest["run_id"]
        or manifest.get("contract_hash") != sha(contract)
    ):
        raise DataError("daily immutable parent identity differs")
    semantic_manifest = _parent_manifest(
        contract, operator, study, identity, str(manifest["run_id"]), native=native
    )
    semantic_manifest.update(
        schema_version=MANIFEST_SCHEMA_VERSION, artifact_contract_version=ARTIFACT_CONTRACT_VERSION
    )
    if canonical(
        {key: value for key, value in manifest.items() if key != "artifacts"}
    ) != canonical(semantic_manifest):
        raise DataError("daily parent semantic manifest differs from frozen contract")
    positions = daily_position_payload(study) if native else position_payload(True)
    expected = {
        role + ".json": {
            "schema": "RulePositionArtifactV1",
            "unit": "position",
            "positions": positions[role],
        }
        for role in ("baseline", "control")
    }
    expected["rule_positions.json" if native else "d0_acceptance.json"] = {
        "schema": "DailyNativeRuleResultV1" if native else "DailyRuleD0AcceptanceV1",
        **identity,
        "run_id": manifest["run_id"],
        "positions": positions,
        "study": study.to_dict() if native else fixed_costed_study().to_dict(),
    }
    if native:
        receipt = read_json_artifact(
            rdir / "native_receipt.json", maximum_bytes=study.resources.max_artifact_bytes
        )
        admission = receipt.get("admission")
        if (
            not isinstance(admission, dict)
            or admission.get("image_id") != study.container_image_id
            or admission.get("rule_request") != daily_worker_request(study)
            or admission.get("query_sha256") != study.query_sha256
            or admission.get("study_id") != study.content_sha256
            or admission.get("trial_id") != admission.get("reservation_id")
            or admission.get("spec_sha256") != manifest["execution_fingerprint"]
            or receipt.get("binding_sha256") != sha(admission)
            or receipt.get("rule_positions") != positions
        ):
            raise DataError("daily native receipt differs from frozen study/positions")
        economics = validate_daily_economics(study, receipt.get("economics"))
        expected.update(
            {
                "study.json": study.to_dict(),
                "query.json": json.loads(study.query_document),
                "economics.json": economics,
            }
        )
        validate_daily_projections(
            rdir.parent.parent,
            read_json_artifact(rdir / "projections.json", maximum_bytes=64 * 1024),
            receipt,
            study,
            project_id=str(manifest["project_id"]),
            parent_run_id=str(manifest["run_id"]),
            source_fingerprint=str(cast(dict[str, object], contract["hashes"])["code"]),
            source_data_dir=source_data_dir,
        )
    for name, payload in expected.items():
        if not same_artifact(rdir / name, canonical(payload).encode()):
            raise DataError("daily artifact differs from immutable source/numerical result")
