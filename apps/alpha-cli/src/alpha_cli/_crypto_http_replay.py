"""Versioned synthetic response/window bindings, using existing artifacts and accounting.

No database opener, migration, live routing, refund, new quota or independent ledger.
Only a committed final w200 outcome anchors a complete window. Loose files never do.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from urllib.error import HTTPError
from urllib.request import Request

import polars as pl

from alpha_cli._crypto_acquisition import bybit_plan
from alpha_cli._crypto_backfill_accounting import FixtureAccountingBlocked
from alpha_cli._crypto_http_accounting import FixtureHttpAccounting
from alpha_cli._market_data_acquisition_accounting import (
    AcquisitionTransactions,
    _hash,
    _policy_body,
)
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoFamily, CryptoRawReceiptV1
from alpha_data.crypto.ingestion import retain_provider_payload
from alpha_data.crypto.providers._wire import (
    CompleteHttpResponse,
    HttpAttemptHook,
    http_request_hash,
)
from alpha_data.crypto.providers.bybit import bybit_public_url
from alpha_data.crypto.storage import CryptoBulkStore
from alpha_data.crypto.verification import ArtifactVerificationBudget, MetadataVerificationBudget

if TYPE_CHECKING:
    from alpha_cli._crypto_backfill import Ledger

_FORMAT = "alpha-http-response-binding-v1"
_KIND = "http_window_binding_v1"
_MAX_BINDING = 1024 * 1024
_MAX_ATTEMPTS = 400
_FIELDS = {
    "format",
    "scope",
    "policy",
    "attempt",
    "request",
    "retry",
    "window",
    "sequence",
    "page",
    "status",
    "length",
    "framing",
}


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _reference(reason: object) -> tuple[str, str]:
    if type(reason) is not str or re.fullmatch(r"(b200|b429|w200)_[0-9a-f]{64}", reason) is None:
        raise FixtureAccountingBlocked("BOUND_LEGACY_OR_UNAVAILABLE_REFERENCE")
    return reason[:4], reason[5:]


@dataclass(frozen=True, eq=False)
class FixtureBoundHttpAccounting(FixtureHttpAccounting):
    store: CryptoBulkStore
    dataset: CryptoDatasetIdentityV1
    fetched_at: datetime
    retry_429: bool
    hash_byte_limit: int
    metadata_byte_limit: int

    def __post_init__(self) -> None:
        super().__post_init__()
        offset = self.fetched_at.utcoffset()
        if (
            not isinstance(self.store, CryptoBulkStore)
            or self.dataset.provider != "bybit"
            or self.dataset.family not in {"funding", "open_interest"}
            or type(self.retry_429) is not bool
            or self.fetched_at.tzinfo is None
            or offset is None
            or offset.total_seconds() != 0
            or any(
                type(v) is not int or v <= 0
                for v in (self.hash_byte_limit, self.metadata_byte_limit)
            )
        ):
            raise FixtureAccountingBlocked("EXPLICIT_BOUND_FIXTURE_INPUTS_REQUIRED")

    def _scope(self, tx: AcquisitionTransactions) -> None:
        super()._scope(tx)
        for row in tx.scope_attempts(self.scope_id):
            if row["state"] in {"success", "failure", "cancelled"}:
                _reference(row["reason"])

    def _attempt(self, request: str, ordinal: int) -> str:
        return "http_" + _digest(["bound-v1", self.scope_id, request, self.attempt_label, ordinal])

    def _retry_reason_is_429(self, reason: object) -> bool:
        return _reference(reason)[0] == "b429"

    def bind(self, ledger: Ledger, expected_request_hash: str | None = None) -> HttpAttemptHook:
        raise FixtureAccountingBlocked("BOUND_WINDOW_COMPOSITION_REQUIRED")

    def _window(
        self, args: tuple[str, str, str], parameters: Mapping[str, object]
    ) -> dict[str, object]:
        plan = bybit_plan(
            cast(CryptoFamily, args[1]),
            args[2],
            base=str(parameters["base"]),
            quote=str(parameters["quote"]),
            category=str(parameters["category"]),
            frequency=str(parameters["frequency"]),
            start=str(parameters["start"]),
            end=str(parameters["end"]),
            fetched_at=self.fetched_at,
        )
        if (
            args[0] != "bybit"
            or plan.dataset != self.dataset
            or any(k.startswith("http_") for k in parameters)
        ):
            raise FixtureAccountingBlocked("BOUND_WINDOW_IDENTITY_MISMATCH")
        window: dict[str, object] = {
            "args": list(args),
            "parameters": dict(parameters),
            "endpoint": plan.endpoint,
        }
        if len(_canonical(window)) > 8192:
            raise FixtureAccountingBlocked("BOUND_WINDOW_IDENTITY_LIMIT")
        return window

    def _snapshot(self, ledger: Ledger) -> list[dict[str, Any]]:
        self._owned(ledger)
        if self._is_cancelled():
            raise FixtureAccountingBlocked("BOUND_CANCELLED")

        def read(tx: AcquisitionTransactions) -> list[dict[str, Any]]:
            self._scope(tx)
            rows = tx.scope_attempts(self.scope_id)
            for row in rows:
                self._replay(tx, row["request_hash"], row["attempt_id"], row)
            return rows

        return self._transaction(read)

    def _manifest(
        self, mid: object, budget: ArtifactVerificationBudget, meta: MetadataVerificationBudget
    ) -> dict[str, object]:
        if type(mid) is not str or re.fullmatch(r"[0-9a-f]{64}", mid) is None:
            raise FixtureAccountingBlocked("BOUND_MANIFEST_REFERENCE_INVALID")
        self.store.verify_readable()
        self.store.require_active(mid, metadata_budget=meta)
        return self.store.verify_manifest(mid, budget=budget, metadata_budget=meta)

    def _payload(self, manifest: Mapping[str, object]) -> bytes:
        size = manifest.get("artifact_bytes")
        if type(size) is not int or not 0 < size <= _MAX_BINDING:
            raise FixtureAccountingBlocked("BOUND_WINDOW_SIZE_INVALID")
        path = self.store.bulk_root / str(manifest["artifact_key"])
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size != size:
                raise DataError("bound artifact size changed")
            chunks = []
            remaining = size
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    raise DataError("bound artifact truncated")
                chunks.append(chunk)
                remaining -= len(chunk)
            payload = b"".join(chunks)
            after = os.fstat(fd)
            if (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ) or hashlib.sha256(payload).hexdigest() != manifest["artifact_sha256"]:
                raise DataError("bound artifact changed")
            return payload
        finally:
            os.close(fd)

    def _root(
        self, mid: str, budget: ArtifactVerificationBudget, meta: MetadataVerificationBudget
    ) -> dict[str, Any]:
        manifest = self._manifest(mid, budget, meta)
        if manifest.get("artifact_kind") != "derived" or manifest.get("derived_kind") != _KIND:
            raise FixtureAccountingBlocked("BOUND_WINDOW_FORMAT_INVALID")
        # The writer produces exactly one bounded UTF8 JSON cell in actual Parquet.
        payload = self._payload(manifest)
        # PyArrow is already locked via the required Nautilus dependency. Use bounded
        # footer parsing before Polars allocation; this estimates decoder work, not RSS.
        from pyarrow.parquet import ParquetFile

        # Locked C-extension constructor is untyped; layout/size values are validated below.
        footer = ParquetFile(  # type: ignore[no-untyped-call]
            io.BytesIO(payload),
            thrift_string_size_limit=65536,
            thrift_container_size_limit=2048,
            arrow_extensions_enabled=False,
        ).metadata
        if footer.num_rows != 1 or footer.num_columns != 1 or footer.num_row_groups != 1:
            raise FixtureAccountingBlocked("BOUND_PARQUET_LAYOUT_INVALID")
        column = footer.row_group(0).column(0)
        if (
            column.physical_type != "BYTE_ARRAY"
            or column.num_values != 1
            or column.compression != "UNCOMPRESSED"
            or not 0 < column.total_uncompressed_size <= 320 * 1024
            or not 0 < footer.row_group(0).total_byte_size <= 320 * 1024
        ):
            raise FixtureAccountingBlocked("BOUND_PARQUET_DECODE_LIMIT")
        schema = pl.read_parquet_schema(io.BytesIO(payload))
        if schema != {"binding_json": pl.String}:
            raise FixtureAccountingBlocked("BOUND_WINDOW_SCHEMA_INVALID")
        frame = pl.read_parquet(io.BytesIO(payload), n_rows=2)
        if frame.height != 1:
            raise FixtureAccountingBlocked("BOUND_WINDOW_CARDINALITY_INVALID")
        raw = frame.item(0, 0)
        if type(raw) is not str or len(raw.encode()) > 256 * 1024:
            raise FixtureAccountingBlocked("BOUND_WINDOW_JSON_LIMIT")
        data = json.loads(raw)
        keys = {
            "schema_version",
            "kind",
            "scope",
            "policy",
            "label",
            "window",
            "dataset",
            "fetched_at",
            "normalized",
            "quality",
            "attempts",
            "final_anchor",
        }
        if (
            type(data) is not dict
            or set(data) != keys
            or type(data["schema_version"]) is not int
            or data["schema_version"] != 1
            or data["kind"] != _KIND
            or data["final_anchor"] != "last_complete_200"
            or data["scope"] != self.scope_id
            or data["policy"] != _hash(_policy_body(self.policy))
            or data["label"] != self.attempt_label
            or type(data["attempts"]) is not list
            or not 1 <= len(data["attempts"]) <= _MAX_ATTEMPTS
            or manifest.get("input_manifest_ids") != [data["normalized"]]
            or manifest.get("metadata")
            != {
                "binding_schema": _KIND,
                "window_sha256": _digest(data["window"]),
                "binding_sha256": _digest(data),
            }
        ):
            raise FixtureAccountingBlocked("BOUND_WINDOW_IDENTITY_INVALID")
        return cast(dict[str, Any], data)

    def _response(
        self,
        mid: str,
        row: Mapping[str, Any],
        budget: ArtifactVerificationBudget,
        meta: MetadataVerificationBudget,
    ) -> tuple[CryptoRawReceiptV1, dict[str, str]]:
        manifest = self._manifest(mid, budget, meta)
        receipt = CryptoRawReceiptV1.from_dict(manifest.get("receipt"))
        request = dict(receipt.request)
        if (
            manifest.get("artifact_kind") != "raw"
            or receipt.provider_schema != _FORMAT
            or receipt.parser_version != _FORMAT
            or set(request) != _FIELDS
            or request["format"] != _FORMAT
            or request["scope"] != self.scope_id
            or request["policy"] != _hash(_policy_body(self.policy))
            or request["attempt"] != row["attempt_id"]
            or request["request"] != row["request_hash"]
            or request["framing"] != "identity_content_length_and_eof"
            or request["status"] not in {"200", "429"}
            or not request["length"].isdecimal()
            or int(request["length"]) != receipt.response_bytes
            or receipt.response_bytes != manifest.get("artifact_bytes")
            or receipt.response_sha256 != manifest.get("artifact_sha256")
            or any(
                not request[k].isascii() or not request[k].isdecimal()
                for k in ("retry", "sequence", "page")
            )
            or not 0 <= int(request["retry"]) <= 3
            or not 0 <= int(request["sequence"]) < _MAX_ATTEMPTS
            or not 0 <= int(request["page"]) < 100
        ):
            raise FixtureAccountingBlocked("BOUND_RESPONSE_IDENTITY_INVALID")
        return receipt, request

    def _validate(
        self, ledger: Ledger, mid: str, window: Mapping[str, object], *, pending_final: bool = False
    ) -> dict[str, object]:
        rows = self._snapshot(ledger)
        by_id = {r["attempt_id"]: r for r in rows}
        budget = ArtifactVerificationBudget(self.hash_byte_limit)
        meta = MetadataVerificationBudget(self.metadata_byte_limit)
        if (
            not pending_final
            and sum(row["state"] == "success" and row["reason"] == "w200_" + mid for row in rows)
            != 1
        ):
            raise FixtureAccountingBlocked("BOUND_WINDOW_HAS_NO_UNIQUE_DURABLE_ANCHOR")
        data = self._root(mid, budget, meta)
        chain = data["attempts"]
        if (
            data["window"] != window
            or data["dataset"] != self.dataset.to_dict()
            or data["fetched_at"] != self.fetched_at.isoformat()
        ):
            raise FixtureAccountingBlocked("BOUND_WINDOW_REQUEST_CHANGED")
        ids = []
        successes = []
        previous = None
        for index, item in enumerate(chain):
            if type(item) is not dict or set(item) != {
                "attempt",
                "response",
                "request",
                "retry",
                "page",
                "status",
            }:
                raise FixtureAccountingBlocked("BOUND_CHAIN_SHAPE_INVALID")
            if (
                any(
                    type(item[k]) is not str or re.fullmatch(r"[0-9a-f]{64}", item[k]) is None
                    for k in ("request", "response")
                )
                or type(item["attempt"]) is not str
                or re.fullmatch(r"http_[0-9a-f]{64}", item["attempt"]) is None
                or any(type(item[k]) is not int for k in ("retry", "page", "status"))
                or item["status"] not in {200, 429}
            ):
                raise FixtureAccountingBlocked("BOUND_CHAIN_VALUE_INVALID")
            aid = item["attempt"]
            row = by_id.get(aid)
            if row is None or aid in ids or row["cancel_requested"]:
                raise FixtureAccountingBlocked("BOUND_CHAIN_ATTEMPT_MISSING")
            receipt, proof = self._response(item["response"], row, budget, meta)
            if (
                proof["window"] != _digest(window)
                or int(proof["sequence"]) != index
                or any(str(item[k]) != proof[k] for k in ("request", "retry", "page", "status"))
                or receipt.dataset != self.dataset
                or receipt.fetched_at != self.fetched_at
                or aid != self._attempt(item["request"], item["retry"])
            ):
                raise FixtureAccountingBlocked("BOUND_CHAIN_ORDER_OR_IDENTITY_CHANGED")
            if previous is None:
                valid = item["page"] == 0 and item["retry"] == 0
            elif previous["status"] == 429:
                valid = (
                    item["page"] == previous["page"]
                    and item["retry"] == previous["retry"] + 1
                    and item["request"] == previous["request"]
                )
            else:
                valid = (
                    item["page"] == previous["page"] + 1
                    and item["retry"] == 0
                    and item["request"] != previous["request"]
                )
            if not valid:
                raise FixtureAccountingBlocked("BOUND_CHAIN_PROGRESS_INVALID")
            final = index == len(chain) - 1
            if final:
                if item["status"] != 200 or (
                    row["state"] != "intent"
                    if pending_final
                    else row["state"] != "success" or row["reason"] != "w200_" + mid
                ):
                    raise FixtureAccountingBlocked("BOUND_FINAL_ANCHOR_UNAVAILABLE")
            elif (
                row["state"] != ("success" if item["status"] == 200 else "failure")
                or row["reason"] != f"b{item['status']}_" + item["response"]
            ):
                raise FixtureAccountingBlocked("BOUND_RESPONSE_OUTCOME_CHANGED")
            ids.append(aid)
            previous = item
            if item["status"] == 200:
                successes.append((receipt, item["request"]))
        # Accounted attempts are never silently omitted. Resolve raw memberships explicitly;
        # scope_attempts() order is NOT a page/execution order.
        members = []
        for row in rows:
            if row["attempt_id"] == ids[-1] and pending_final:
                members.append(row["attempt_id"])
                continue
            tag, reference = _reference(row["reason"])
            if tag == "w200":
                other = self._root(reference, budget, meta)
                last = other["attempts"][-1]
                if last["attempt"] != row["attempt_id"]:
                    raise FixtureAccountingBlocked("BOUND_ANCHOR_ATTEMPT_CHANGED")
                reference = last["response"]
            _, proof = self._response(reference, row, budget, meta)
            expected_status = "429" if tag == "b429" else "200"
            if proof["status"] != expected_status or row["state"] != (
                "failure" if tag == "b429" else "success"
            ):
                raise FixtureAccountingBlocked("BOUND_SCOPE_OUTCOME_INVALID")
            if proof["window"] == _digest(window):
                members.append(row["attempt_id"])
        if set(members) != set(ids):
            raise FixtureAccountingBlocked("BOUND_WINDOW_ATTEMPTS_OMITTED")
        normalized = self._manifest(data["normalized"], budget, meta)
        if (
            normalized.get("artifact_kind") != "normalized"
            or normalized.get("dataset") != self.dataset.to_dict()
        ):
            raise FixtureAccountingBlocked("BOUND_NORMALIZED_IDENTITY_CHANGED")
        input_ids = normalized["input_manifest_ids"]
        if not isinstance(input_ids, list) or len(input_ids) != len(successes):
            raise FixtureAccountingBlocked("BOUND_PAGE_CARDINALITY_CHANGED")
        for raw_id, (proof_receipt, expected_hash) in zip(input_ids, successes, strict=True):
            raw = self._manifest(raw_id, budget, meta)
            receipt = CryptoRawReceiptV1.from_dict(raw.get("receipt"))
            actual_hash = http_request_hash(
                Request(bybit_public_url(str(window["endpoint"]), dict(receipt.request)))
            )
            if (
                receipt.dataset != self.dataset
                or receipt.response_sha256 != proof_receipt.response_sha256
                or receipt.response_bytes != proof_receipt.response_bytes
                or actual_hash != expected_hash
            ):
                raise FixtureAccountingBlocked("BOUND_NORMALIZED_PAGE_ORDER_CHANGED")
        from alpha_cli._crypto_backfill import BackfillWindow
        from alpha_cli._crypto_backfill_evidence import verify_completed_window

        parameters = cast(dict[str, Any], window["parameters"])
        args = cast(list[str], window["args"])
        verify_completed_window(
            self.store,
            args[2],
            BackfillWindow(
                start=parameters["start"], end=parameters["end"], period=parameters["period"]
            ),
            {"manifest_id": data["normalized"], "quality_state": data["quality"]},
            provider=args[0],
            family=cast(CryptoFamily, args[1]),
            category=parameters["category"],
            frequency=parameters["frequency"],
            quote=parameters["quote"],
            now=self.fetched_at,
            budget=budget,
            metadata_budget=meta,
        )
        return {
            "normalized_manifest_id": data["normalized"],
            "state": data["quality"],
            "http_replay_manifest_id": mid,
        }

    def completion_fields(self, result: Mapping[str, object]) -> dict[str, object]:
        mid = result.get("http_replay_manifest_id")
        if type(mid) is not str or re.fullmatch(r"[0-9a-f]{64}", mid) is None:
            raise FixtureAccountingBlocked("BOUND_COMPLETION_REFERENCE_MISSING")
        return {"http_replay_manifest_id": mid}

    def _verify_window(
        self,
        ledger: Ledger,
        args: tuple[str, str, str],
        parameters: Mapping[str, object],
        entry: Mapping[str, object],
    ) -> None:
        mid = self.completion_fields(entry)["http_replay_manifest_id"]
        result = self._validate(ledger, str(mid), self._window(args, parameters))
        if result["normalized_manifest_id"] != entry.get("manifest_id") or result[
            "state"
        ] != entry.get("quality_state"):
            raise FixtureAccountingBlocked("BOUND_COMPLETION_OUTPUT_CHANGED")

    def verify_window(
        self,
        ledger: Ledger,
        args: tuple[str, str, str],
        parameters: Mapping[str, object],
        entry: Mapping[str, object],
    ) -> None:
        try:
            self._verify_window(ledger, args, parameters, entry)
        except FixtureAccountingBlocked:
            raise
        except Exception:
            raise FixtureAccountingBlocked("BOUND_VERIFICATION_REFUSED") from None

    def dispatch_window(
        self,
        ledger: Ledger,
        acquire: Callable[..., Mapping[str, object]],
        args: tuple[str, str, str],
        parameters: Mapping[str, object],
    ) -> Mapping[str, object]:
        try:
            return self._dispatch_bound(ledger, acquire, args, parameters)
        except FixtureAccountingBlocked:
            raise
        except BaseException:
            raise FixtureAccountingBlocked("BOUND_REPLAY_OR_PUBLICATION_REFUSED") from None

    def _dispatch_bound(
        self,
        ledger: Ledger,
        acquire: Callable[..., Mapping[str, object]],
        args: tuple[str, str, str],
        parameters: Mapping[str, object],
    ) -> Mapping[str, object]:
        self._owned(ledger)
        window = self._window(args, parameters)
        whash = _digest(window)
        rows = self._snapshot(ledger)
        budget = ArtifactVerificationBudget(self.hash_byte_limit)
        meta = MetadataVerificationBudget(self.metadata_byte_limit)
        roots = []
        for row in rows:
            if row["state"] in {"reserved", "intent", "unknown"}:
                raise FixtureAccountingBlocked("BOUND_UNRESOLVED_ATTEMPT")
            tag, reference = _reference(row["reason"])
            if tag == "w200":
                candidate = self._root(reference, budget, meta)
                if candidate["attempts"][-1]["attempt"] != row["attempt_id"]:
                    raise FixtureAccountingBlocked("BOUND_SCOPE_ANCHOR_CHANGED")
                if candidate["window"] == window:
                    roots.append(reference)
                reference = candidate["attempts"][-1]["response"]
            _, proof = self._response(reference, row, budget, meta)
            if proof["status"] != ("429" if tag == "b429" else "200") or row["state"] != (
                "failure" if tag == "b429" else "success"
            ):
                raise FixtureAccountingBlocked("BOUND_SCOPE_OUTCOME_INVALID")
        if roots:
            if len(roots) != 1:
                raise FixtureAccountingBlocked("BOUND_AMBIGUOUS_WINDOW_ROOT")
            recovered = self._validate(ledger, roots[0], window)
            from alpha_cli._crypto_backfill import BackfillWindow

            key = (
                args[2]
                + "|"
                + BackfillWindow(
                    start=str(parameters["start"]),
                    end=str(parameters["end"]),
                    period=cast(str | None, parameters["period"]),
                ).key
            )
            entry = ledger.entry(key)
            if entry is not None and (
                entry.get("manifest_id", recovered["normalized_manifest_id"])
                != recovered["normalized_manifest_id"]
                or entry.get("http_replay_manifest_id", roots[0]) != roots[0]
            ):
                raise FixtureAccountingBlocked("BOUND_RETAINED_PROGRESS_CONFLICT")
            return recovered
        chain: list[dict[str, Any]] = []
        pending: dict[str, Any] | None = None
        observed: CompleteHttpResponse | None = None
        active_request: str | None = None

        def observe(proof: CompleteHttpResponse) -> None:
            nonlocal observed
            if observed is not None or proof.request_hash != active_request:
                raise FixtureAccountingBlocked("BOUND_AMBIGUOUS_RESPONSE_EVIDENCE")
            observed = proof

        def hook(request: str, ordinal: int, send: Callable[[], bytes]) -> bytes:
            nonlocal pending, observed, active_request
            if len(chain) >= _MAX_ATTEMPTS:
                raise FixtureAccountingBlocked("BOUND_CHAIN_LIMIT")
            self._owned(ledger)
            observed = None
            active_request = request
            previous = pending
            if previous is not None:
                prior = next(
                    (r for r in self._snapshot(ledger) if r["attempt_id"] == previous["attempt"]),
                    None,
                )
                if prior is None or prior["state"] != "intent":
                    raise FixtureAccountingBlocked("BOUND_PENDING_RESPONSE_UNAVAILABLE")
                _, proof = self._response(
                    previous["response"],
                    prior,
                    ArtifactVerificationBudget(self.hash_byte_limit),
                    MetadataVerificationBudget(self.metadata_byte_limit),
                )
                if (
                    proof["window"] != whash
                    or proof["status"] != "200"
                    or proof["request"] != previous["request"]
                ):
                    raise FixtureAccountingBlocked("BOUND_PENDING_RESPONSE_CHANGED")

            def flush(tx: AcquisitionTransactions) -> None:
                if previous is None:
                    return
                row = tx.read_attempt(previous["attempt"])
                self._replay(tx, request=previous["request"], attempt=previous["attempt"], row=row)
                if row["state"] != "intent" or row["cancel_requested"]:
                    raise FixtureAccountingBlocked("BOUND_PENDING_RESPONSE_CHANGED")
                tx.record_outcome(
                    "settle_" + previous["attempt"][5:],
                    previous["attempt"],
                    "success",
                    "b200_" + previous["response"],
                )

            if ordinal > 0:
                prior = next(
                    (
                        r
                        for r in self._snapshot(ledger)
                        if r["attempt_id"] == self._attempt(request, ordinal - 1)
                    ),
                    None,
                )
                if prior is None:
                    raise FixtureAccountingBlocked("BOUND_RETRY_PREDECESSOR_MISSING")
                tag, reference = _reference(prior["reason"])
                receipt, proof = self._response(
                    reference,
                    prior,
                    ArtifactVerificationBudget(self.hash_byte_limit),
                    MetadataVerificationBudget(self.metadata_byte_limit),
                )
                if (
                    tag != "b429"
                    or proof["window"] != whash
                    or proof["request"] != request
                    or proof["retry"] != str(ordinal - 1)
                ):
                    raise FixtureAccountingBlocked("BOUND_RETRY_EVIDENCE_CHANGED")
            page = 0 if not chain else chain[-1]["page"] + (1 if ordinal == 0 else 0)
            aid = self._attempt(request, ordinal)

            def retain(body: bytes | None, error: HTTPError | None) -> str:
                nonlocal pending
                proof = observed
                status = 200 if error is None else error.code
                if (
                    proof is None
                    or proof.status_code != status
                    or proof.request_hash != request
                    or (body is not None and proof.body != body)
                ):
                    raise FixtureAccountingBlocked("BOUND_COMPLETE_RESPONSE_UNAVAILABLE")
                fields = {
                    "format": _FORMAT,
                    "scope": self.scope_id,
                    "policy": _hash(_policy_body(self.policy)),
                    "attempt": aid,
                    "request": request,
                    "retry": str(ordinal),
                    "window": whash,
                    "sequence": str(len(chain)),
                    "page": str(page),
                    "status": str(status),
                    "length": str(proof.content_length),
                    "framing": proof.basis,
                }
                _, raw = retain_provider_payload(
                    self.store,
                    dataset=self.dataset,
                    payload=proof.body,
                    request=tuple(sorted(fields.items())),
                    fetched_at=self.fetched_at,
                    provider_schema=_FORMAT,
                    parser_version=_FORMAT,
                    logical_name="http-response.json",
                    max_payload_bytes=8 * 1024 * 1024,
                )
                item = {
                    "attempt": aid,
                    "response": raw["manifest_id"],
                    "request": request,
                    "retry": ordinal,
                    "page": page,
                    "status": status,
                }
                chain.append(item)
                pending = item if status == 200 else None
                return f"b{status}_" + str(raw["manifest_id"])

            return super(FixtureBoundHttpAccounting, self)._send(
                ledger,
                request,
                ordinal,
                send,
                response_reason=retain,
                defer_success=True,
                before_reserve=flush,
            )

        try:
            result = acquire(
                *args,
                **dict(parameters),
                http_attempt_hook=hook,
                http_response_evidence=observe,
                http_error_response_evidence=observe,
                http_retry_429=self.retry_429,
            )
            self._owned(ledger)
            if not chain or pending is None or self._is_cancelled():
                raise FixtureAccountingBlocked("BOUND_WINDOW_INCOMPLETE")
            mid = result.get("normalized_manifest_id")
            quality = result.get("state")
            if (
                type(mid) is not str
                or re.fullmatch(r"[0-9a-f]{64}", mid) is None
                or quality not in {"qualified", "warning", "quarantined", "unavailable"}
            ):
                raise FixtureAccountingBlocked("BOUND_RESULT_INVALID")
            data = {
                "schema_version": 1,
                "final_anchor": "last_complete_200",
                "kind": _KIND,
                "scope": self.scope_id,
                "policy": _hash(_policy_body(self.policy)),
                "label": self.attempt_label,
                "window": window,
                "dataset": self.dataset.to_dict(),
                "fetched_at": self.fetched_at.isoformat(),
                "normalized": mid,
                "quality": quality,
                "attempts": chain,
            }
            encoded = _canonical(data)
            if len(encoded) > 256 * 1024:
                raise FixtureAccountingBlocked("BOUND_WINDOW_JSON_LIMIT")
            stream = io.BytesIO()
            pl.DataFrame({"binding_json": [encoded.decode()]}).write_parquet(
                stream, compression="uncompressed", statistics=False
            )
            binding = self.store.publish_derived(
                stream.getvalue(),
                derived_kind=_KIND,
                input_manifest_ids=(mid,),
                metadata={
                    "binding_schema": _KIND,
                    "window_sha256": whash,
                    "binding_sha256": _digest(data),
                },
            )
            root = str(binding["manifest_id"])
            self._validate(ledger, root, window, pending_final=True)
            self._owned(ledger)
            if self._is_cancelled():
                raise FixtureAccountingBlocked("BOUND_CANCELLED_BEFORE_FINAL_ANCHOR")

            def anchor(tx: AcquisitionTransactions) -> None:
                self._scope(tx)
                row = tx.read_attempt(chain[-1]["attempt"])
                self._replay(tx, chain[-1]["request"], chain[-1]["attempt"], row)
                if row["state"] != "intent" or row["cancel_requested"]:
                    raise FixtureAccountingBlocked("BOUND_FINAL_INTENT_CHANGED")
                tx.record_outcome(
                    "settle_" + row["attempt_id"][5:], row["attempt_id"], "success", "w200_" + root
                )

            try:
                self._transaction(anchor)
            except BaseException:
                # Do NOT mark an already-committed w200 unavailable after lost acknowledgment.
                # This invocation fails; a fresh reader must verify the root or pending intent.
                raise FixtureAccountingBlocked("BOUND_FINAL_COMMIT_UNCERTAIN") from None
            return {**result, "http_replay_manifest_id": root}
        except FixtureAccountingBlocked:
            raise
        except BaseException:
            if pending is not None:
                self._unknown(ledger, pending["attempt"])
            raise FixtureAccountingBlocked("BOUND_WINDOW_PUBLICATION_UNCERTAIN") from None
