"""Managed comparison requests retain explicit previews, failures and linked evidence."""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import comparison_acquisition as acquisition
from alpha_cli import comparison_acquisition_worker as worker
from alpha_cli import investigation_workspace as workspace
from alpha_cli import investigation_workspace_data as data
from alpha_cli.comparison_acquisition import AcquisitionPlan
from alpha_cli.investigation_case import Case
from alpha_cli.investigation_workspace_contracts import (
    ComparisonAcquireRequest,
    ComparisonDraftRequest,
    ComparisonProxy,
    InvestigationCreate,
)
from alpha_core import DataError
from alpha_data.adapters.base import FetchResult
from tests.unit.test_comparison_acquisition import fixture_dispatch, provider_result
from tests.unit.test_investigation_workspace import root_with_run


def _parent(tmp_path: Path) -> tuple[Path, str]:
    root = root_with_run(tmp_path)
    view = workspace.create(
        root, InvestigationCreate(run_id="1234567890abcdef", question="Compare losses")
    )
    case = Case.open(workspace._directory(root, view.id))
    case.call("inspect_execution")
    case.call("inspect_losses")
    return root, view.id


def _request(*symbols: str) -> ComparisonDraftRequest:
    return ComparisonDraftRequest(
        series=[
            ComparisonProxy(symbol=symbol, asset_class="etf", role="market") for symbol in symbols
        ]
    )


def _provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(worker, "_fetch", provider_result)
    monkeypatch.setattr(acquisition, "_dispatch", fixture_dispatch)


def test_draft_is_explicit_and_acquisition_creates_one_verified_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, identifier = _parent(tmp_path)
    _provider(monkeypatch)
    draft = data.draft(root, identifier, _request("SPY"))
    assert (draft.start, draft.end) == ("2020-01-02", "2020-01-03")
    assert workspace.show(root, identifier).acquisition_status == "not_started"
    result = data.acquire(root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256))
    assert result.acquisition_status == "succeeded"
    assert result.comparison_child_id is not None
    child = workspace.show(root, result.comparison_child_id)
    assert child.parent_id == identifier
    assert child.case_id != result.case_id
    assert child.run_id == result.run_id
    assert child.authority == "none" and not child.admitted
    child_case = Case.open(workspace._directory(root, child.id))
    child_case.call("inspect_execution")
    losses = child_case.call("inspect_losses")
    assert losses["result"]["comparisons"]["series"][0]["symbol"] == "SPY"
    assert result.requests_remaining == 10
    monkeypatch.delenv("ALPHA_TIINGO_API_KEY")
    monkeypatch.setattr(
        acquisition, "_dispatch", lambda *a: pytest.fail("cached acquisition fetched")
    )
    repeated = data.acquire(
        root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256)
    )
    assert repeated.comparison_child_id == child.id
    assert len(workspace.list_cases(root, result.run_id)) == 2


def test_missing_key_preserves_preview_and_allows_later_explicit_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, identifier = _parent(tmp_path)
    draft = data.draft(root, identifier, _request("SPY"))
    monkeypatch.delenv("ALPHA_TIINGO_API_KEY", raising=False)
    result = data.acquire(root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256))
    assert result.acquisition_status == "not_started"
    assert result.error is not None and "ALPHA_TIINGO_API_KEY" in result.error
    assert result.comparison_child_id is None
    _provider(monkeypatch)
    assert (
        data.acquire(
            root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256)
        ).acquisition_status
        == "succeeded"
    )


def test_stale_preview_rejected_before_provider_or_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, identifier = _parent(tmp_path)
    previous = data.draft(root, identifier, _request("SPY"))
    latest = data.draft(root, identifier, _request("QQQ"))
    monkeypatch.setattr(acquisition, "_dispatch", lambda *a: pytest.fail("stale preview fetched"))
    with pytest.raises(DataError, match="Preview changed"):
        data.acquire(root, identifier, ComparisonAcquireRequest(plan_sha256=previous.plan_sha256))
    assert workspace.show(root, identifier).comparison_draft == latest
    assert not (workspace._directory(root, identifier) / "comparison-acquisition").exists()


def test_draft_tamper_fails_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, identifier = _parent(tmp_path)
    draft = data.draft(root, identifier, _request("SPY"))
    path = workspace._directory(root, identifier) / f"comparison-draft-{draft.plan_sha256}.json"
    value = json.loads(path.read_text())
    value["series"][0]["symbol"] = "QQQ"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(
        acquisition, "_dispatch", lambda *a: pytest.fail("tampered preview fetched")
    )
    with pytest.raises(DataError, match="draft changed"):
        data.acquire(root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256))


def test_partial_batch_keeps_failure_and_never_publishes_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, identifier = _parent(tmp_path)
    _provider(monkeypatch)
    draft = data.draft(root, identifier, _request("SPY", "QQQ"))

    def partial(plan: AcquisitionPlan, index: int, limit: int) -> FetchResult:
        if index == 1:
            raise DataError("fixture provider failure")
        return provider_result(plan, index, limit)

    monkeypatch.setattr(worker, "_fetch", partial)
    result = data.acquire(root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256))
    assert result.acquisition_status == "failed"
    assert result.comparison_child_id is None
    assert result.error is not None and "will not retry" in result.error
    directory = workspace._directory(root, identifier)
    assert not (directory / "comparison-acquisition/comparisons.json").exists()
    monkeypatch.setattr(acquisition, "_dispatch", lambda *a: pytest.fail("failure retried"))
    assert (
        data.acquire(
            root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256)
        ).acquisition_status
        == "failed"
    )
    assert len(workspace.list_cases(root, result.run_id)) == 1


def test_sync_sigterm_restores_handler_and_retains_spent_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, identifier = _parent(tmp_path)
    _provider(monkeypatch)
    draft = data.draft(root, identifier, _request("SPY"))
    previous = signal.getsignal(signal.SIGTERM)

    def interrupted(directory: Path, index: int) -> dict[str, Any]:
        assert (directory / "request.json").is_file()
        os.kill(os.getpid(), signal.SIGTERM)
        raise AssertionError("SIGTERM did not interrupt acquisition")

    monkeypatch.setattr(acquisition, "_dispatch", interrupted)
    result = data.acquire(root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256))
    assert signal.getsignal(signal.SIGTERM) == previous
    assert result.acquisition_status == "incomplete"
    assert result.error is not None and "interrupted" in result.error
    assert result.comparison_child_id is None
    monkeypatch.setattr(
        acquisition, "_dispatch", lambda *a: pytest.fail("interrupted batch retried")
    )
    result = data.acquire(root, identifier, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256))
    assert result.error is not None and "cannot be retried" in result.error


def test_eight_distinct_drafts_allowed_then_cap_is_explicit(tmp_path: Path) -> None:
    root, identifier = _parent(tmp_path)
    for number in range(8):
        data.draft(root, identifier, _request(f"ETF{number}"))
    with pytest.raises(DataError, match="limit"):
        data.draft(root, identifier, _request("ETF8"))


def test_long_valid_parent_question_can_create_comparison_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = root_with_run(tmp_path)
    parent = workspace.create(
        root, InvestigationCreate(run_id="1234567890abcdef", question="q" * 8000)
    )
    case = Case.open(workspace._directory(root, parent.id))
    case.call("inspect_execution")
    case.call("inspect_losses")
    _provider(monkeypatch)
    draft = data.draft(root, parent.id, _request("SPY"))
    result = data.acquire(root, parent.id, ComparisonAcquireRequest(plan_sha256=draft.plan_sha256))
    assert result.comparison_child_id is not None
    assert result.error is None


def test_child_publication_failure_reuses_reserved_identity_without_provider_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, identifier = _parent(tmp_path)
    _provider(monkeypatch)
    draft = data.draft(root, identifier, _request("SPY"))
    request = ComparisonAcquireRequest(plan_sha256=draft.plan_sha256)
    register = workspace._register

    def interrupted_register(*args: Any, **kwargs: Any) -> None:
        raise OSError("fixture publication interruption")

    monkeypatch.setattr(data, "_register", interrupted_register)
    failed = data.acquire(root, identifier, request)
    assert failed.acquisition_status == "succeeded"
    assert failed.comparison_child_id is None
    assert failed.error == "fixture publication interruption"
    directory = workspace._directory(root, identifier)
    reservation = json.loads((directory / "comparison-child-reservation.json").read_text())
    pending = list(directory.parent.glob(".pending-*"))
    assert len(pending) == 1
    assert (pending[0] / "case.sqlite3").exists()
    assert failed.requests_remaining == 10 and failed.turns_remaining == 4
    monkeypatch.setattr(data, "_register", register)
    monkeypatch.setattr(acquisition, "_dispatch", lambda *a: pytest.fail("child retry refetched"))
    recovered = data.acquire(root, identifier, request)
    assert recovered.comparison_child_id == reservation["id"]
    assert recovered.error is None
    assert recovered.requests_remaining == failed.requests_remaining
    assert recovered.turns_remaining == failed.turns_remaining
    assert pending[0].exists()  # Failed staging evidence is retained.
    assert len(workspace.list_cases(root, recovered.run_id)) == 2
    assert data.acquire(root, identifier, request).comparison_child_id == reservation["id"]
