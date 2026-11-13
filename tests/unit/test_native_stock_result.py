"""Owner-observed native result workflow; fresh synthetic stores and offline workers only."""

from __future__ import annotations

import os
import unittest

from alpha_cli.native_stock_inspect import recover_stock_result
from tests.unit._native_stock_test_support import event_rows, record


class RecoveryTests(unittest.TestCase):
    def test_sqlite_fixture_preserves_rows_controls_and_closes(self) -> None:
        import sqlite3
        from contextlib import closing

        with closing(sqlite3.connect(":memory:")) as source:
            source.row_factory = sqlite3.Row
            source.execute(
                "CREATE TABLE job_events (job_id TEXT, sequence INTEGER, event_type TEXT, "
                "occurred_at TEXT, payload_json TEXT)"
            )
            original = {
                "job_id": "synthetic",
                "sequence": 1,
                "event_type": "native_outcome",
                "occurred_at": "2026-11-08T00:00:00Z",
                "payload_json": '{"fixture":1}',
            }
            source.execute(
                "INSERT INTO job_events VALUES (?, ?, ?, ?, ?)", tuple(original.values())
            )
            source.execute(
                "CREATE TRIGGER protect_rows BEFORE UPDATE ON job_events "
                "BEGIN SELECT RAISE(ABORT, 'fixture append only'); END"
            )
            source.commit()
            changed = original | {"payload_json": '{"fixture":2}'}
            with event_rows(source, [changed], "synthetic") as cloned:
                self.assertEqual(
                    dict(source.execute("SELECT * FROM job_events").fetchone()), original
                )
                self.assertEqual(
                    dict(cloned.execute("SELECT * FROM main.job_events").fetchone()), original
                )
                self.assertEqual(
                    dict(cloned.execute("SELECT * FROM temp.job_events").fetchone()), changed
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    cloned.execute("UPDATE main.job_events SET payload_json='changed'")
            with self.assertRaises(sqlite3.ProgrammingError):
                cloned.execute("SELECT 1")
            self.assertEqual(dict(source.execute("SELECT * FROM job_events").fetchone()), original)

    def test_owner_hash_and_profile_required_no_resume_or_science_authority(self) -> None:
        artifacts: dict[str, object] = {
            "status": "current_bytes_validated_only",
            "receipt_sha256": "a" * 64,
            "profile_declaration": {"status": "verified"},
        }
        profile: dict[str, object] = {"status": "verified"}
        outcome = {
            "reason": "exit",
            "returncode": 0,
            "stock_result": {"schema": "StockRDLoopObservationV1", "receipt_sha256": "a" * 64},
        }
        report = recover_stock_result(artifacts, profile, outcome, uncertain=False)
        self.assertEqual(report["status"], "verified")
        self.assertFalse(report["resume_allowed"])
        self.assertEqual(report["scientific_acceptance"], "not_admitted")
        blocked = recover_stock_result(
            artifacts, profile, outcome, uncertain=False, cancelled_or_failed=True
        )
        self.assertEqual(blocked["status"], "unavailable")
        self.assertEqual(blocked["owner_receipt_match"], "verified")
        cases: tuple[
            tuple[dict[str, object], dict[str, object], dict[str, object] | None, bool, str], ...
        ] = (
            (artifacts, profile, None, False, "unavailable"),
            (artifacts, profile, {"reason": "exit", "returncode": 0}, False, "unavailable"),
            (artifacts, profile, outcome, True, "unavailable"),
            (artifacts | {"receipt_sha256": "b" * 64}, profile, outcome, False, "mismatch"),
            (artifacts, {"status": "mismatch"}, outcome, False, "mismatch"),
            (artifacts, {"status": "unavailable"}, outcome, False, "unavailable"),
            ({"status": "unavailable"}, profile, outcome, False, "unavailable"),
        )
        for altered, selected, observation, uncertain, expected in cases:
            with self.subTest(expected=expected):
                report = recover_stock_result(altered, selected, observation, uncertain=uncertain)
                self.assertEqual(report["status"], expected)
                self.assertFalse(report["resume_allowed"])


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit installed offline synthetic assets required",
)
class NativeResultWorkflow(unittest.TestCase):
    def test_checkpoint_resume_owner_capture_and_recovery_in_new_process(self) -> None:
        import hashlib
        import json
        import subprocess
        import sys
        from pathlib import Path
        from unittest.mock import patch

        from alpha_cli._native_fixture_store import _events
        from alpha_cli.native_stock_inspect import inspect_run
        from alpha_cli.native_stock_profile import ProfileSelection
        from alpha_cli.native_supervisor import start_synthetic_owner
        from alpha_core import DataError
        from tests.unit.test_native_stock_dispatch import JOB, case

        with case() as (root, store, launch):
            with store._readonly_transaction() as connection:
                before = dict(
                    connection.execute("SELECT * FROM research_launch_reservations").fetchone()
                )
            process = start_synthetic_owner(
                root, JOB, fixture="native_loop", seconds=40, native=launch
            )
            try:
                self.assertEqual(process.wait(timeout=50), 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            selected = ProfileSelection(launch.source, launch.stock_runtime, "resume")
            report = inspect_run(root, JOB, profile_selection=selected)
            self.assertEqual(record(report["result_recovery"])["status"], "verified")
            self.assertFalse(report["resume_allowed"])
            self.assertEqual(report["scientific_acceptance"], "not_admitted")
            work = root / f"payload-{JOB}"
            receipt_raw = (work / "stock-receipt.json").read_bytes()
            receipt = json.loads(receipt_raw)
            self.assertTrue(receipt["resumed_without_repeating"])
            self.assertTrue(receipt["replay_rejected"])
            self.assertEqual(
                receipt["charged_stages"],
                ["direct_exp_gen", "coding", "running", "feedback", "record"],
            )
            with store._readonly_transaction() as connection:
                events = _events(connection, JOB)
                after = dict(
                    connection.execute("SELECT * FROM research_launch_reservations").fetchone()
                )
                consumption = connection.execute(
                    "SELECT count(*) FROM job_events WHERE event_type='native_invocation'"
                ).fetchone()[0]
                rows = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM job_events WHERE job_id=? ORDER BY sequence", (JOB,)
                    )
                ]
            self.assertEqual(before, after)
            self.assertEqual(consumption, 1)
            outcome = events["native_outcome"]
            self.assertNotIn("rule_result", outcome)
            self.assertEqual(
                outcome["stock_result"],
                {
                    "schema": "StockRDLoopObservationV1",
                    "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
                },
            )
            with patch("subprocess.Popen") as duplicate, self.assertRaises(DataError):
                start_synthetic_owner(root, JOB, fixture="native_loop", native=launch)
            duplicate.assert_not_called()
            cli = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "alpha_cli.native_stock_inspect",
                    "--data-dir",
                    str(root),
                    "--job-id",
                    JOB,
                    "--profile-source",
                    str(launch.source),
                    "--profile-runtime",
                    str(launch.stock_runtime),
                    "--profile-mode",
                    "resume",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
            self.assertEqual(json.loads(cli.stdout), report)
            evidence = Path(os.environ["ALPHA_STOCK_RECEIPTS"]) / "native-result"
            evidence.mkdir()
            (evidence / "recovered.json").write_text(cli.stdout)
            (evidence / "owner-outcome.json").write_text(json.dumps(outcome, sort_keys=True))
            (evidence / "stock-receipt.json").write_bytes(receipt_raw)
            (evidence / "stock-trace.json").write_bytes((work / "stock-trace.json").read_bytes())
            # Parsed semantics still validate, but changed exact bytes cannot borrow
            # the owner's durable hash. Never modify the journal or replenish a budget.
            (work / "stock-receipt.json").write_bytes(receipt_raw + b" ")
            changed = inspect_run(root, JOB, profile_selection=selected)
            self.assertEqual(
                record(changed["artifact_validation"])["status"], "current_bytes_validated_only"
            )
            self.assertEqual(record(changed["result_recovery"])["status"], "mismatch")
            (evidence / "changed-bytes.json").write_text(json.dumps(changed, sort_keys=True))
            (work / "stock-receipt.json").write_bytes(receipt_raw)
            stale = inspect_run(
                root,
                JOB,
                profile_selection=ProfileSelection(launch.source, launch.stock_runtime, "cancel"),
            )
            self.assertEqual(record(stale["result_recovery"])["status"], "mismatch")
            (evidence / "stale-profile.json").write_text(json.dumps(stale, sort_keys=True))
            # Read-only corrupted-row doubles exercise closed protocol validation;
            # no malformed observation is written into the actual journal.
            for mutation in ("schema", "digest", "extra", "rule", "failed", "owner"):
                changed_rows = [dict(row) for row in rows]
                for row in changed_rows:
                    if row["event_type"] != "native_outcome":
                        continue
                    payload = json.loads(row["payload_json"])
                    if mutation == "schema":
                        record(payload["stock_result"])["schema"] = (
                            "SyntheticNativeRuleObservationV1"
                        )
                    if mutation == "digest":
                        record(payload["stock_result"])["receipt_sha256"] = "g" * 64
                    if mutation == "extra":
                        record(payload["stock_result"])["extra"] = "forbidden"
                    if mutation == "rule":
                        payload["rule_result"] = dict(payload["stock_result"])
                    if mutation == "failed":
                        payload["reason"] = "cancelled"
                    if mutation == "owner":
                        payload["owner_id"] = "other-owner"
                    row["payload_json"] = json.dumps(payload)
                with (
                    store._readonly_transaction() as connection,
                    event_rows(connection, changed_rows, JOB) as corrupted,
                    self.subTest(mutation=mutation),
                    self.assertRaises(DataError),
                ):
                    _events(corrupted, JOB)
            # Legacy successful rows remain readable, but never backfilled from files.
            for row in rows:
                if row["event_type"] == "native_outcome":
                    legacy = json.loads(row["payload_json"])
                    legacy.pop("stock_result")
                    row["payload_json"] = json.dumps(legacy)
            with (
                store._readonly_transaction() as connection,
                event_rows(connection, rows, JOB) as legacy_connection,
            ):
                legacy_events = _events(legacy_connection, JOB)
            legacy = recover_stock_result(
                record(report["artifact_validation"]),
                record(report["profile_verification"]),
                legacy_events["native_outcome"],
                uncertain=False,
            )
            self.assertEqual(legacy["status"], "unavailable")
            (evidence / "legacy-unavailable.json").write_text(json.dumps(legacy, sort_keys=True))
            # Mutation of a detached read copy cannot replace the persisted receipt.
            record(outcome["stock_result"])["receipt_sha256"] = "0" * 64
            self.assertEqual(
                record(inspect_run(root, JOB, profile_selection=selected)["result_recovery"])[
                    "status"
                ],
                "verified",
            )
            store.request_job_cancellation(
                JOB, actor="synthetic", reason="late cancellation fixture"
            )
            blocked = inspect_run(root, JOB, profile_selection=selected)
            self.assertTrue(blocked["job_cancellation_or_failure"])
            self.assertEqual(record(blocked["result_recovery"])["status"], "unavailable")
            self.assertEqual(record(blocked["result_recovery"])["owner_receipt_match"], "verified")
            (evidence / "late-cancellation.json").write_text(json.dumps(blocked, sort_keys=True))
            (work / "stock-receipt.json").unlink()
            self.assertEqual(
                record(inspect_run(root, JOB, profile_selection=selected)["result_recovery"])[
                    "status"
                ],
                "unavailable",
            )

    def test_lost_owner_and_nested_observation_mutation_cannot_record(self) -> None:
        from collections.abc import Mapping, MutableMapping
        from typing import cast
        from unittest.mock import patch

        from alpha_cli._native_fixture_store import _events
        from alpha_cli._native_fixture_store import record as record_observation
        from alpha_cli.native_supervisor import _open_lock, _Owner
        from alpha_core import DataError
        from tests.unit.test_native_stock_dispatch import JOB, case

        with case() as (root, store, launch), _open_lock(root, JOB) as lock:
            owner = _Owner(root, JOB, "native_loop", 40, lock, native=launch)
            store.claim_native_fixture(JOB, owner)
            binding = {"schema": "StockRDLoopObservationV1", "receipt_sha256": "a" * 64}
            observation = owner._issue("native_outcome", {"stock_result": binding})
            binding["receipt_sha256"] = "b" * 64
            frozen = observation.fields["stock_result"]
            assert isinstance(frozen, Mapping)
            self.assertEqual(frozen["receipt_sha256"], "a" * 64)
            with self.assertRaises(TypeError):
                # Deliberately violate the immutable interface to check the runtime boundary.
                cast(MutableMapping[str, object], frozen)["receipt_sha256"] = "c" * 64
            with patch("os.getpid", return_value=owner.pid + 1), self.assertRaises(DataError):
                record_observation(store, JOB, observation)
            lock.close()
            with self.assertRaises(DataError):
                record_observation(store, JOB, observation)
            with store._readonly_transaction() as connection:
                self.assertEqual(set(_events(connection, JOB)), {"native_claim"})

    def test_stale_profile_and_consumed_invocation_cannot_spawn(self) -> None:
        from unittest.mock import patch

        from alpha_cli._native_stock_launch import StockFixtureLaunch, consume_before_spawn
        from alpha_cli.native_supervisor import _open_lock, _Owner
        from alpha_core import DataError
        from tests.unit.test_native_stock_dispatch import JOB, case

        with case() as (root, store, launch), _open_lock(root, JOB) as lock:
            owner = _Owner(root, JOB, "native_loop", 40, lock, native=launch)
            store.claim_native_fixture(JOB, owner)
            with (
                patch.object(StockFixtureLaunch, "measure", return_value="0" * 64),
                patch("subprocess.Popen") as spawn,
                self.assertRaises(DataError),
            ):
                owner.spawn()
            spawn.assert_not_called()
            consume_before_spawn(owner)
            with patch("subprocess.Popen") as spawn, self.assertRaises(DataError):
                owner.spawn()
            spawn.assert_not_called()
