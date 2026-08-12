"""One safe error contract for REST and SSE launch surfaces."""

from collections.abc import Mapping
from typing import Protocol, cast

import pytest
from fastapi.testclient import TestClient

from alpha_web import _invoke
from alpha_web.app import create_app


class _Response(Protocol):
    @property
    def headers(self) -> Mapping[str, str]: ...

    def json(self) -> object: ...


def _assert_contract(response: _Response, *, code: str) -> dict[str, object]:
    body = cast(dict[str, object], response.json())
    assert body["schema_version"] == 1
    assert body["code"] == code
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["recovery_action"], str) and body["recovery_action"]
    assert isinstance(body["field_errors"], list)
    assert body["request_id"] == response.headers["x-request-id"]
    assert "detail" not in body
    return body


def test_validation_and_sse_errors_share_api_error_v1() -> None:
    client = TestClient(create_app())
    invalid = client.post(
        "/api/jobs",
        json={
            "command": "validate",
            "args": "SPY",
            "run_context": {"schema_version": 1, "kind": "governed_project"},
        },
    )
    missing_stream = client.get("/api/jobs/missing/stream")

    invalid_body = _assert_contract(invalid, code="request_invalid")
    assert invalid_body["field_errors"]
    _assert_contract(missing_stream, code="not_found")


def test_unhandled_errors_redact_secret_path_terminal_and_account_sentinels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = (
        "\x1b[31mTraceback secret=TOP_SECRET_SENTINEL "
        "/Users/private-owner/project DU123456789\x1b[0m"
    )

    def explode(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError(sentinel)

    monkeypatch.setattr(_invoke, "launch", explode)
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post("/api/jobs", json={"args": "info"})

    body = _assert_contract(response, code="internal_error")
    rendered = response.text
    assert "TOP_SECRET_SENTINEL" not in rendered
    assert "/Users/private-owner" not in rendered
    assert "DU123456789" not in rendered
    assert "Traceback" not in rendered
    assert "\x1b" not in rendered
    assert body["message"] == "The Workstation could not complete this request."
