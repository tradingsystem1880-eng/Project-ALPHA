"""Socket-free contracts for the isolated model gateway."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

import pytest

if TYPE_CHECKING:
    from workers.rdagent.model_gateway import ChatResult, Gateway

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    """Repository test defaults may place pytest temp paths inside git."""
    with tempfile.TemporaryDirectory(prefix="gateway-unit-", dir="/tmp") as directory:
        yield Path(directory)


@pytest.fixture
def mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "gateway_contract", ROOT / "workers/rdagent/model_gateway.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def gateway(mod: ModuleType, tmp_path: Path) -> Gateway:
    return cast(
        "Gateway",
        mod.Gateway(
            mod.Settings(
                data_dir=tmp_path, run_id="test", chat_route="fake", embedding_route="fake"
            )
        ),
    )


def request(**extra: Any) -> dict[str, Any]:
    return {
        "model": "alpha-chat",
        "messages": [
            {"role": "system", "content": "system secret"},
            {"role": "user", "content": "prompt secret"},
        ],
        **extra,
    }


def logged(gateway: Gateway) -> list[dict[str, Any]]:
    return [json.loads(line) for line in gateway.log_path.read_text().splitlines()]


@pytest.mark.parametrize(
    "key,value",
    [
        ("temperature", 0),
        ("top_p", 1),
        ("seed", 3),
        ("frequency_penalty", 1),
        ("presence_penalty", -1),
        ("max_tokens", 10),
        ("max_completion_tokens", 10),
    ],
)
def test_waivable_parameters(mod: ModuleType, gateway: Gateway, key: str, value: object) -> None:
    with pytest.raises(mod.GatewayError) as error:
        gateway.chat(request(**{key: value}))
    assert error.value.code == "unsupported_parameter"
    assert key in error.value.message
    assert logged(gateway)[-1]["refused"] == [key]
    gateway.settings.accept_unhonoured = (key,)
    gateway.chat(request(**{key: value}))
    assert logged(gateway)[-1]["waived"] == [key]


@pytest.mark.parametrize(
    "key,value",
    [
        ("n", 2),
        ("stop", "END"),
        ("tools", []),
        ("tool_choice", "auto"),
        ("functions", []),
        ("function_call", "auto"),
        ("logprobs", False),
        ("top_logprobs", 1),
        ("logit_bias", {}),
        ("parallel_tool_calls", False),
        ("audio", {}),
        ("modalities", []),
        ("prediction", {}),
        ("user", "a"),
        ("metadata", {}),
        ("unknown", True),
        ("reasoning_effort", "extreme"),
        ("response_format", {"type": "text"}),
    ],
)
def test_never_waivable(mod: ModuleType, gateway: Gateway, key: str, value: object) -> None:
    gateway.settings.accept_unhonoured = (key,)
    with pytest.raises(mod.GatewayError) as error:
        gateway.chat(request(**{key: value}))
    assert error.value.status == 400
    assert error.value.code == "unsupported_parameter"
    assert logged(gateway)[-1]["attempts"] == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"frequency_penalty": 0},
        {"presence_penalty": 0},
        {"n": 1},
        {"max_tokens": None},
        {"max_completion_tokens": None},
        {"reasoning_effort": "low"},
        {"reasoning_effort": "medium"},
        {"reasoning_effort": "high"},
        {"stream": False},
    ],
)
def test_honoured_parameters(gateway: Gateway, extra: dict[str, Any]) -> None:
    gateway.chat(request(**extra))
    assert not logged(gateway)[-1]["waived"]
    assert not logged(gateway)[-1]["refused"]


def test_messages_and_model_validation(mod: ModuleType, gateway: Gateway) -> None:
    for messages in (
        [{"role": "user", "content": "a"}],
        [{"role": "system", "content": [{"type": "image_url"}]}],
    ):
        with pytest.raises(mod.GatewayError, match="system|text"):
            gateway.chat(request(messages=messages))
    with pytest.raises(mod.GatewayError) as error:
        gateway.chat(request(model="lm_studio/alpha-chat"))
    assert error.value.code == "model_not_served"
    gateway.chat(
        request(
            messages=[
                {"role": "system", "content": [{"type": "text", "text": "first"}]},
                {"role": "system", "content": "second"},
                {"role": "user", "content": "one"},
                {"role": "assistant", "content": "two"},
            ]
        )
    )
    row = logged(gateway)[-1]
    assert "messages_rendered_as_transcript" in row["enforced"]
    assert row["prompt_sha256"] == mod.digest("[user]\none\n[assistant]\ntwo\n")


@pytest.mark.parametrize("bad,retries,status,attempts", [(1, 2, 200, 2), (4, 2, 502, 3)])
def test_json_retries(
    mod: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad: int,
    retries: int,
    status: int,
    attempts: int,
) -> None:
    monkeypatch.setenv("ALPHA_GATEWAY_FAKE_BAD_JSON_FIRST", str(bad))
    gw = mod.Gateway(
        mod.Settings(data_dir=tmp_path, run_id="json", chat_route="fake", json_retries=retries)
    )
    if status == 502:
        with pytest.raises(mod.GatewayError) as error:
            gw.chat(request(response_format={"type": "json_object"}))
        assert error.value.code == "invalid_json_from_model"
    else:
        reply = gw.chat(request(response_format={"type": "json_object"}))
        assert json.loads(reply["choices"][0]["message"]["content"])["fake"] is True
    assert logged(gw)[-1]["attempts"] == attempts
    assert gw.budget.status()["months"][mod.month()]["calls"] == attempts


def test_budget_caps_and_atomic_concurrency(mod: ModuleType, tmp_path: Path) -> None:
    settings = mod.Settings(data_dir=tmp_path, run_id="a", run_max_calls=7)
    budget = mod.Budget(settings)

    def reserve(_: int) -> bool:
        try:
            budget.reserve(0)
            return True
        except mod.GatewayError as exc:
            assert exc.code == "budget_exhausted"
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        assert sum(pool.map(reserve, range(60))) == 7
    assert budget.status()["runs"]["a"]["calls"] == 7
    settings.run_id = "b"
    settings.month_max_calls = 7
    with pytest.raises(mod.GatewayError, match="month_max_calls"):
        budget.reserve(0)


@pytest.mark.parametrize("cap", ["run_max_usd", "month_max_usd"])
def test_usd_reservation_and_settlement(mod: ModuleType, tmp_path: Path, cap: str) -> None:
    settings = mod.Settings(data_dir=tmp_path, run_id="a", run_max_usd=1, month_max_usd=1)
    budget = mod.Budget(settings)
    ticket = budget.reserve(0.8)
    budget.settle(ticket, 0.2)
    assert budget.status()["runs"]["a"]["usd"] == pytest.approx(0.2)
    if cap == "month_max_usd":
        settings.run_id = "b"
    with pytest.raises(mod.GatewayError, match=cap):
        budget.reserve(0.9)


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "{}",
        '{"schema_version":1,"months":[],"runs":{}}',
        '{"schema_version":1,"months":{},"runs":{"a":{"calls":-1,"usd":0}}}',
    ],
)
def test_malformed_budget_fails_closed(mod: ModuleType, gateway: Gateway, raw: str) -> None:
    gateway.budget.path.write_text(raw)
    with pytest.raises(mod.GatewayError) as error:
        gateway.chat(request())
    assert error.value.status == 503
    assert error.value.code == "budget_state_unreadable"
    assert gateway.budget.path.read_text() == raw


def test_settings_validation(mod: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="50 USD"):
        mod.Gateway(mod.Settings(data_dir=tmp_path, run_id="x", month_max_usd=51))
    git = tmp_path / "git"
    git.mkdir()
    (git / ".git").write_text("gitdir: somewhere")
    child = git / "child"
    child.mkdir()
    for path in (child, Path("relative"), tmp_path / "missing"):
        with pytest.raises(ValueError):
            mod.Gateway(mod.Settings(data_dir=path, run_id="x"))
    for url in ("http://example.com:11434", "https://example.com", "file:///tmp/model"):
        with pytest.raises(ValueError, match="loopback"):
            mod.Gateway(mod.Settings(data_dir=tmp_path, run_id="x", ollama_url=url))


@pytest.mark.parametrize(
    "extra",
    [
        {"encoding_format": "base64"},
        {"dimensions": 8},
        {"user": "a"},
        {"other": 1},
        {"input": [1, 2]},
    ],
)
def test_embedding_policy(mod: ModuleType, gateway: Gateway, extra: dict[str, Any]) -> None:
    with pytest.raises(mod.GatewayError):
        gateway.embeddings({"model": "alpha-embed", "input": "a", **extra})


def test_embeddings_and_private_logs(gateway: Gateway) -> None:
    result = gateway.embeddings(
        {"model": "alpha-embed", "input": ["a", "b"], "encoding_format": "float"}
    )
    assert result["object"] == "list"
    assert len(result["data"]) == 2
    assert len(result["data"][0]["embedding"]) == 8
    assert result == gateway.embeddings({"model": "alpha-embed", "input": ["a", "b"]})
    gateway.chat(request())
    raw = gateway.log_path.read_text()
    assert "prompt secret" not in raw and "system secret" not in raw
    assert logged(gateway)[-1]["model_used"] == "fake"
    assert logged(gateway)[-1]["route"] == "fake"


def fake_codex(
    tmp_path: Path, events: list[dict[str, Any]] | None = None, delay: float = 0
) -> tuple[Path, Path]:
    record = tmp_path / "record.json"
    exe = tmp_path / "codex"
    exe.write_text(f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast
args = sys.argv[1:]
instructions = next(x for x in args if x.startswith('model_instructions_file='))
payload = {{"args": args, "env": dict(os.environ), "stdin": sys.stdin.read(),
"cwd": os.getcwd(), "instructions": Path(json.loads(instructions.split('=',1)[1])).read_text()}}
if '--output-schema' in args:
    payload['schema'] = json.loads(Path(args[args.index('--output-schema')+1]).read_text())
Path({str(record)!r}).write_text(json.dumps(payload))
time.sleep({delay})
Path(args[args.index('-o')+1]).write_text('{{"ok":true}}')
for event in {events!r} or [{{"type":"turn.completed","usage":{{"input_tokens":7,
"cached_input_tokens":2,"output_tokens":4,"reasoning_output_tokens":1}}}}]:
    print(json.dumps(event))
""")
    exe.chmod(0o700)
    return exe, record


def test_codex_confinement(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe, record = fake_codex(tmp_path)
    monkeypatch.setenv("ALPHA_GATEWAY_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "not-in-child")
    monkeypatch.setenv("LITELLM_SECRET", "not-in-child")
    gw = mod.Gateway(mod.Settings(data_dir=tmp_path, run_id="x", codex_bin=str(exe)))
    result = gw.chat(
        request(
            response_format={"type": "json_schema", "json_schema": {"schema": {"type": "object"}}},
            reasoning_effort="high",
        )
    )
    assert result["model"] == "gpt-6.1-sol"
    data = json.loads(record.read_text())
    args = data["args"]
    work = data["cwd"]
    temp = str(Path(work).parent)
    expected = [
        "exec",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--ephemeral",
        "-s",
        "read-only",
        "-C",
        work,
        "-m",
        "gpt-6.1-sol",
    ]
    for value in [
        'model_reasoning_effort="high"',
        'approval_policy="never"',
        'web_search="disabled"',
        f'model_instructions_file="{temp}/instructions.md"',
        "include_environment_context=false",
        "include_permissions_instructions=false",
        "include_collaboration_mode_instructions=false",
        "include_apps_instructions=false",
        "skills.include_instructions=false",
        "skills.bundled.enabled=false",
        "agents.enabled=false",
    ]:
        expected += ["-c", value]
    features = (
        "shell_tool",
        "unified_exec",
        "apps",
        "plugins",
        "remote_plugin",
        "browser_use",
        "browser_use_external",
        "computer_use",
        "image_generation",
        "multi_agent",
        "multi_agent_v2",
        "memories",
        "hooks",
        "view_image",
        "sleep_tool",
        "goals",
        "skill_search",
        "tool_suggest",
        "in_app_browser",
        "workspace_dependencies",
        "code_mode_host",
    )
    for feature in features:
        expected += ["--disable", feature]
    expected += [
        "--output-schema",
        f"{temp}/schema.json",
        "--json",
        "-o",
        f"{temp}/last.txt",
        "--color",
        "never",
        "-",
    ]
    assert args == expected
    assert data["stdin"] == "prompt secret"
    assert data["instructions"] == "system secret"
    assert data["schema"] == {"type": "object"}
    assert set(data["env"]) <= {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "CODEX_HOME"}
    assert not Path(temp).exists()
    row = logged(gw)[-1]
    assert [
        row[k] for k in ("prompt_tokens", "cached_tokens", "completion_tokens", "reasoning_tokens")
    ] == [7, 2, 4, 1]
    assert "sk-test-not-real" not in gw.log_path.read_text()


@pytest.mark.parametrize(
    "events,code,status",
    [
        (
            [{"type": "item.started", "item": {"type": "command_execution"}}],
            "codex_used_a_tool",
            502,
        ),
        (
            [{"type": "turn.failed", "error": {"message": "usageLimitExceeded"}}],
            "codex_usage_limit",
            429,
        ),
        ([{"type": "error", "message": "rate limit 429"}], "codex_usage_limit", 429),
        ([{"type": "error", "message": "failure"}], "codex_failed", 502),
    ],
)
def test_codex_failures(
    mod: ModuleType, tmp_path: Path, events: list[dict[str, Any]], code: str, status: int
) -> None:
    exe, _ = fake_codex(tmp_path, events)
    gw = mod.Gateway(mod.Settings(data_dir=tmp_path, run_id="x", codex_bin=str(exe)))
    with pytest.raises(mod.GatewayError) as error:
        gw.chat(request())
    assert (error.value.code, error.value.status) == (code, status)
    assert logged(gw)[-1]["attempts"] == 1


def test_codex_timeout(mod: ModuleType, tmp_path: Path) -> None:
    exe, _ = fake_codex(tmp_path, delay=2)
    gw = mod.Gateway(
        mod.Settings(data_dir=tmp_path, run_id="x", codex_bin=str(exe), codex_timeout=0.1)
    )
    with pytest.raises(mod.GatewayError) as error:
        gw.chat(request())
    assert error.value.status == 504


@pytest.mark.parametrize(
    "missing",
    [
        "ALPHA_GATEWAY_API_KEY",
        "ALPHA_GATEWAY_API_BASE",
        "api_model",
        "api_price_in_per_mtok",
        "api_price_out_per_mtok",
    ],
)
def test_api_requires_configuration(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.setenv("ALPHA_GATEWAY_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("ALPHA_GATEWAY_API_BASE", "https://example.com/v1")
    values = dict(api_model="model", api_price_in_per_mtok=1, api_price_out_per_mtok=2)
    if missing.startswith("ALPHA"):
        monkeypatch.delenv(missing)
    else:
        values.pop(missing)
    with pytest.raises(ValueError, match=missing):
        mod.Gateway(mod.Settings(data_dir=tmp_path, run_id="x", chat_route="api", **values))


def test_queue_timeout(mod: ModuleType, tmp_path: Path) -> None:
    entered, release = threading.Event(), threading.Event()

    class Backend:
        def complete(
            self,
            request: dict[str, Any],
            prompt: str,
            instructions: str,
            effort: str,
            schema: dict[str, Any] | None,
        ) -> ChatResult:
            entered.set()
            assert release.wait(5)
            return cast("ChatResult", mod.ChatResult("{}", "injected"))

    gw = mod.Gateway(
        mod.Settings(
            data_dir=tmp_path, run_id="x", chat_route="fake", max_concurrency=1, queue_timeout=0.01
        ),
        chat_backend=Backend(),
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(gw.chat, request())
        assert entered.wait(5)
        try:
            with pytest.raises(mod.GatewayError) as error:
                gw.chat(request())
            assert error.value.code == "gateway_busy"
        finally:
            release.set()
        first.result()
    assert sorted(row["status"] for row in logged(gw)) == [200, 503]


def test_codex_usage_limit_after_long_message(mod: ModuleType, tmp_path: Path) -> None:
    exe, _ = fake_codex(tmp_path, [{"type": "error", "message": "x" * 400 + " quota"}])
    backend = mod.CodexChat(mod.Settings(data_dir=tmp_path, run_id="x", codex_bin=str(exe)))
    with pytest.raises(mod.GatewayError) as error:
        backend.complete({}, "prompt", "instructions", "medium", None)
    assert error.value.code == "codex_usage_limit"
    assert error.value.status == 429
    assert len(error.value.message) <= 300


def test_api_parameters_are_for_provider_to_judge(mod: ModuleType, tmp_path: Path) -> None:
    # Parameter planning is pure: API messages and unknown fields go to the provider unchanged.
    gw = object.__new__(mod.Gateway)
    gw.settings = mod.Settings(data_dir=tmp_path, run_id="x", chat_route="api")
    payload = {"model": "alpha-chat", "messages": [], "future_provider_option": {"value": 1}}
    row = gw.record("/v1/chat/completions", payload)
    plan = gw.chat_plan(payload, row)
    assert plan.prompt == ""
    assert row["honoured"] == list(payload)
    assert not row["refused"]


def test_sse_emulation_without_sockets(mod: ModuleType) -> None:
    response = {
        "id": "chatcmpl-test",
        "created": 1,
        "model": "actual-model",
        "choices": [{"message": {"content": "verbatim\nreply"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }
    parts = list(mod.sse_chunks(response, True))
    assert parts[-1] == b"data: [DONE]\n\n"
    chunks = [json.loads(part.decode().removeprefix("data: ").strip()) for part in parts[:-1]]
    assert len(chunks) == 3
    assert chunks[0]["choices"][0]["delta"] == {"role": "assistant", "content": "verbatim\nreply"}
    assert chunks[1]["choices"][0] == {"index": 0, "delta": {}, "finish_reason": "stop"}
    assert chunks[2]["choices"] == [] and chunks[2]["usage"] == response["usage"]
    assert all(chunk["model"] == "actual-model" for chunk in chunks)
    assert len(list(mod.sse_chunks(response, False))) == 3


def test_logs_redact_api_key_and_session_token_even_in_content(
    mod: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    key, token = "sk-test-not-real", "local-test-session-nonce"
    monkeypatch.setenv("ALPHA_GATEWAY_API_KEY", key)
    gw = object.__new__(mod.Gateway)
    gw.settings = mod.Settings(data_dir=tmp_path, run_id="x", chat_route="fake", log_content=True)
    gw.settings.state_dir.mkdir()
    gw.log_path = gw.settings.state_dir / "calls.jsonl"
    gw.log_lock = threading.Lock()
    gw.session_token = token
    gw.log(gw.record("/health", {"model": key + token}), key + " prompt", token + " reply")
    records = (
        gw.log_path.read_text()
        + (gw.settings.state_dir / "content.jsonl").read_text()
        + capsys.readouterr().err
    )
    assert key not in records
    assert token not in records


def test_api_forwarding_and_actual_prices(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = "sk-test-not-real"
    monkeypatch.setenv("ALPHA_GATEWAY_API_KEY", key)
    monkeypatch.setenv("ALPHA_GATEWAY_API_BASE", "https://example.com/v1")
    settings = mod.Settings(
        data_dir=tmp_path,
        run_id="x",
        api_model="real-model",
        api_price_in_per_mtok=2,
        api_price_out_per_mtok=5,
    )
    payload = request(
        temperature=0.7,
        stream=True,
        provider_option={"keep": [1, 2]},
        response_format={"type": "json_object"},
    )
    captured: list[tuple[str, dict[str, Any], str | None]] = []

    def provider(url: str, body: dict[str, Any], api_key: str | None) -> dict[str, Any]:
        captured.append((url, body, api_key))
        return {
            "id": "provider-id",
            "created": 1,
            "model": "provider-internal",
            "choices": [{"message": {"role": "assistant", "content": '{"ok": true}'}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "prompt_tokens_details": None,
                "completion_tokens_details": None,
            },
        }

    monkeypatch.setattr(mod, "post_json", provider)
    result = mod.ApiChat(settings).complete(payload, "prompt", "system", "medium", None)
    assert captured == [
        (
            "https://example.com/v1/chat/completions",
            {**payload, "model": "real-model", "stream": False},
            key,
        )
    ]
    assert payload["model"] == "alpha-chat" and payload["stream"] is True
    assert result.model == "real-model"
    assert result.response["model"] == "real-model"
    assert result.usd == pytest.approx(0.0003)
    assert result.prompt_tokens == 100 and result.completion_tokens == 20
    assert result.cached_tokens is None and result.reasoning_tokens is None


def test_ollama_preserves_input_and_usage(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[str, dict[str, Any]]] = []
    texts = ["  a\n", "b"]

    def provider(url: str, body: dict[str, Any], key: str | None = None) -> dict[str, Any]:
        captured.append((url, body))
        return {"embeddings": [[1.0, 2.0], [3.0, 4.0]], "prompt_eval_count": 17}

    monkeypatch.setattr(mod, "post_json", provider)
    backend = mod.OllamaEmbeddings(mod.Settings(data_dir=tmp_path, run_id="x"))
    result = backend.embed(texts)
    assert captured == [
        ("http://127.0.0.1:11434/api/embed", {"model": "nomic-embed-text", "input": texts})
    ]
    assert result.vectors == [[1.0, 2.0], [3.0, 4.0]] and result.tokens == 17


@pytest.mark.parametrize("usage", [{"input_tokens": -1}, {"output_tokens": "2"}, [1]])
def test_codex_rejects_invalid_usage(mod: ModuleType, tmp_path: Path, usage: object) -> None:
    exe, _ = fake_codex(tmp_path, [{"type": "turn.completed", "usage": usage}])
    backend = mod.CodexChat(mod.Settings(data_dir=tmp_path, run_id="x", codex_bin=str(exe)))
    with pytest.raises(mod.GatewayError) as error:
        backend.complete({}, "prompt", "instructions", "medium", None)
    assert error.value.status == 502
    assert error.value.code == "codex_failed"


def test_ollama_rejects_invalid_token_count(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mod, "post_json", lambda *args: {"embeddings": [[1.0]], "prompt_eval_count": -3}
    )
    backend = mod.OllamaEmbeddings(mod.Settings(data_dir=tmp_path, run_id="x"))
    with pytest.raises(mod.GatewayError) as error:
        backend.embed(["a"])
    assert error.value.status == 502


def test_budget_lock_failure_is_openai_shaped(mod: ModuleType, tmp_path: Path) -> None:
    # Isolate the lock primitive; no gateway or data directory is started here.
    budget = object.__new__(mod.Budget)
    budget.lock_path = tmp_path  # Opening a directory as a lock file must fail closed.
    with pytest.raises(mod.GatewayError) as error, budget.locked():
        pytest.fail("unreadable lock granted a reservation")
    assert error.value.status == 503
    assert error.value.code == "budget_state_unreadable"


def test_codex_notice_items_are_not_tools(mod: ModuleType, tmp_path: Path) -> None:
    # codex-cli 0.167.0 reports "code mode fails closed" as an item of type "error".
    events = [
        {
            "type": "item.completed",
            "item": {"type": "error", "message": "Code Mode is unavailable"},
        },
        {"type": "item.completed", "item": {"type": "agent_message", "text": '{"ok":true}'}},
        {"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 2}},
    ]
    exe, _ = fake_codex(tmp_path, events)
    gw = mod.Gateway(mod.Settings(data_dir=tmp_path, run_id="x", codex_bin=str(exe)))
    gw.chat(request())
    assert logged(gw)[-1]["tool_events"] == 0
