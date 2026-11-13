"""Loopback gateway and optional stock RD-Agent client contracts."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workers/rdagent/model_gateway.py"
pytestmark = pytest.mark.smoke


@contextmanager
def running_gateway(*extra: str) -> Iterator[tuple[dict[str, Any], Path]]:
    with tempfile.TemporaryDirectory(prefix="gateway-smoke-") as directory:
        data_dir = Path(directory)
        session_path = data_dir / "model-gateway/session.json"
        # Files avoid a full stderr pipe blocking the server under test.
        with (data_dir / "stderr").open("w+") as stderr:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(SCRIPT),
                    "serve",
                    "--data-dir",
                    str(data_dir),
                    "--run-id",
                    "smoke",
                    "--chat-route",
                    "fake",
                    "--embedding-route",
                    "fake",
                    "--port",
                    "0",
                    *extra,
                ],
                stdout=subprocess.DEVNULL,
                stderr=stderr,
            )
            try:
                deadline = time.monotonic() + 15
                session = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        stderr.seek(0)
                        pytest.fail(f"gateway exited {process.returncode}: {stderr.read()}")
                    if session_path.exists():
                        # Publication can be observed while the JSON file is being written.
                        raw = session_path.read_text()
                        if raw.endswith("}"):
                            session = json.loads(raw)
                            break
                    time.sleep(0.02)
                assert session is not None, "gateway did not publish its session"
                assert stat.S_IMODE(session_path.stat().st_mode) == 0o600
                assert session["pid"] == process.pid
                assert session["base_url"].startswith("http://127.0.0.1:")
                yield session, data_dir
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                assert not session_path.exists(), "gateway did not remove its session on exit"


def call(
    session: dict[str, Any],
    path: str,
    body: dict[str, Any] | None = None,
    *,
    authenticated: bool = True,
) -> tuple[int, bytes, str]:
    headers = {"Content-Type": "application/json"}
    if authenticated:
        headers["Authorization"] = "Bearer " + session["token"]
    request = urllib.request.Request(
        session["base_url"] + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers.get_content_type()


def chat_request(**extra: Any) -> dict[str, Any]:
    return {
        "model": "alpha-chat",
        "messages": [
            {"role": "system", "content": "Return a JSON object."},
            {"role": "user", "content": "gateway smoke prompt"},
        ],
        **extra,
    }


def read_log(data_dir: Path, count: int) -> list[dict[str, Any]]:
    path = data_dir / "model-gateway/calls.jsonl"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        if len(rows) >= count:
            return rows
        time.sleep(0.02)
    pytest.fail(f"gateway log did not reach {count} records")


def test_http_gateway() -> None:
    with running_gateway() as (session, data_dir):
        count = 0
        status, raw, _ = call(session, "/health", authenticated=False)
        count += 1
        assert status == 200 and json.loads(raw) == {"status": "ok"}
        status, raw, _ = call(session, "/v1/models", authenticated=False)
        count += 1
        assert status == 401 and json.loads(raw)["error"]["code"] == "unauthorized"
        status, raw, _ = call(session, "/v1/models")
        count += 1
        assert status == 200
        assert [model["id"] for model in json.loads(raw)["data"]] == ["alpha-chat", "alpha-embed"]
        status, raw, _ = call(
            session, "/v1/chat/completions", chat_request(response_format={"type": "json_object"})
        )
        count += 1
        assert status == 200
        result = json.loads(raw)
        assert result["model"] == "fake"
        assert json.loads(result["choices"][0]["message"]["content"])["fake"] is True
        status, raw, content_type = call(
            session,
            "/v1/chat/completions",
            chat_request(stream=True, stream_options={"include_usage": True}),
        )
        count += 1
        assert status == 200 and content_type == "text/event-stream"
        events = [event.removeprefix("data: ") for event in raw.decode().split("\n\n") if event]
        assert events[-1] == "[DONE]"
        chunks = [json.loads(event) for event in events[:-1]]
        assert len(chunks) == 3
        assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
        assert json.loads(chunks[0]["choices"][0]["delta"]["content"])["fake"] is True
        assert chunks[1]["choices"][0] == {"index": 0, "delta": {}, "finish_reason": "stop"}
        assert chunks[2]["choices"] == [] and "usage" in chunks[2]
        status, raw, _ = call(
            session, "/v1/embeddings", {"model": "alpha-embed", "input": ["a", "b"]}
        )
        count += 1
        assert status == 200 and len(json.loads(raw)["data"]) == 2
        status, raw, _ = call(session, "/v1/chat/completions", chat_request(temperature=0.1))
        count += 1
        assert status == 400 and json.loads(raw)["error"]["param"] == "temperature"
        status, raw, _ = call(session, "/missing")
        count += 1
        assert status == 404 and json.loads(raw)["error"]["code"] == "not_found"
        rows = read_log(data_dir, count)
        assert len(rows) == count
        raw_log = (data_dir / "model-gateway/calls.jsonl").read_text()
        assert session["token"] not in raw_log
        assert "gateway smoke prompt" not in raw_log
        assert "response_format" in rows[3]["enforced"]
    with running_gateway("--accept-unhonoured", "temperature") as (session, data_dir):
        status, _, _ = call(session, "/v1/chat/completions", chat_request(temperature=0.1))
        assert status == 200
        assert read_log(data_dir, 1)[0]["waived"] == ["temperature"]


def test_stock_rdagent_client() -> None:
    python = os.environ.get("ALPHA_STOCK_PYTHON")
    source = os.environ.get("ALPHA_RDAGENT_SOURCE")
    if not python or not source:
        pytest.skip("ALPHA_STOCK_PYTHON and ALPHA_RDAGENT_SOURCE are required for the stock client")
    script = """
import json, os, sys
sys.path.insert(0, os.environ['ALPHA_RDAGENT_SOURCE'])
from rdagent.oai.llm_utils import APIBackend
backend = APIBackend()
reply = backend.build_messages_and_create_chat_completion(
    user_prompt='Return the fake object.', system_prompt='Return a JSON object.', json_mode=True)
assert json.loads(reply)['fake'] is True
vectors = backend.create_embedding(['a', 'b'])
assert len(vectors) == 2 and all(len(vector) == 8 for vector in vectors)
"""
    with running_gateway("--accept-unhonoured", "temperature") as (session, data_dir):
        home = data_dir / "client-home"
        home.mkdir()
        work = data_dir / "client-work"
        work.mkdir()
        env = {
            **os.environ,
            "ALPHA_RDAGENT_SOURCE": str(Path(source).resolve()),
            "CHAT_MODEL": "lm_studio/alpha-chat",
            "EMBEDDING_MODEL": "lm_studio/alpha-embed",
            "LM_STUDIO_API_BASE": session["base_url"] + "/v1",
            "LM_STUDIO_API_KEY": session["token"],
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            "MAX_RETRY": "1",
            "HOME": str(home),
        }
        process = subprocess.Popen(
            [python, "-c", script],
            env=env,
            cwd=work,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=60)
            # Do not echo client diagnostics containing credentials to the test report.
            detail = (stdout + stderr).replace(session["token"], "[redacted]")
            assert process.returncode == 0, detail
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        rows = read_log(data_dir, 2)
        chat = [row for row in rows if row["endpoint"] == "/v1/chat/completions"]
        assert chat and "response_format" in chat[-1]["enforced"]
        assert any(row["endpoint"] == "/v1/embeddings" for row in rows)
