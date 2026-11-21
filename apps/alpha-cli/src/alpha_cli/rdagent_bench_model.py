"""The replay bench: stored prompts, the plan with its caps, the clients and the resumable run.

The bench sends stored prompts to candidate models and stores every output. It takes no ledger and
no memory folder, so it cannot write to either. The caps are the owner's and are never raised.
"""

from __future__ import annotations

import json
import math
import os
import time
import tomllib
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

RUN_MAX_CALLS = 60
RUN_MAX_USD = 10.0
MONTH_MAX_USD = 50.0
TOKEN_VARIABLE = "ALPHA_BENCH_GATEWAY_TOKEN"


class BenchError(Exception):
    """A refusal in plain words."""


@dataclass(frozen=True)
class StoredPrompt:
    id: str
    stage: str
    messages: list[dict[str, Any]]
    prompt_tokens: int | None
    completion_tokens: int | None


@dataclass(frozen=True)
class Reply:
    text: str
    provider: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float | None


@dataclass(frozen=True)
class Plan:
    calls: int
    usd: float
    per_model: dict[str, tuple[int, float]]


@dataclass
class RunResult:
    new_calls: int
    finished: bool


class Client(Protocol):
    def complete(self, model: str, prompt: StoredPrompt, sample: int) -> Reply: ...


def _count(value: object, where: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise BenchError(f"{where}: a token count must be a whole number of zero or more.")
    return value


def load_prompts(folder: Path, stages: list[str] | None) -> list[StoredPrompt]:
    if not folder.is_dir():
        raise BenchError(f"The prompt folder does not exist: {folder}")
    found: list[StoredPrompt] = []
    for path in sorted(folder.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            prompt = StoredPrompt(
                id=str(raw["id"]),
                stage=str(raw["stage"]),
                messages=list(raw["messages"]),
                prompt_tokens=_count(raw.get("prompt_tokens"), path.name),
                completion_tokens=_count(raw.get("completion_tokens"), path.name),
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise BenchError(f"{path.name} is not a stored prompt: {error!r}") from error
        if "/" in prompt.id or not prompt.id:
            raise BenchError(f"{path.name}: the id must be a plain name.")
        if stages is None or prompt.stage in stages:
            found.append(prompt)
    if len({p.id for p in found}) != len(found):
        raise BenchError("Two stored prompts share one id.")
    if not found:
        raise BenchError("No stored prompt matches. Nothing to do.")
    return found


def load_prices(path: Path, models: list[str]) -> dict[str, tuple[float, float]]:
    """Dollars per million tokens, in and out, for every candidate. A missing price is a refusal."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise BenchError(f"The price file cannot be read: {error}") from error
    prices: dict[str, tuple[float, float]] = {}
    for model in models:
        entry = raw.get(model)
        if not isinstance(entry, dict):
            raise BenchError(f"There is no price for model '{model}' in {path}.")
        try:
            price = (float(entry["in_per_mtok"]), float(entry["out_per_mtok"]))
        except (KeyError, TypeError, ValueError) as error:
            raise BenchError(
                f"The price for '{model}' needs in_per_mtok and out_per_mtok."
            ) from error
        if not all(math.isfinite(v) and v >= 0 for v in price):
            raise BenchError(f"The price for '{model}' must be finite and not negative.")
        prices[model] = price
    return prices


def make_plan(
    prompts: list[StoredPrompt],
    models: list[str],
    samples: int,
    prices: Mapping[str, tuple[float, float]],
    month_spent: float,
) -> Plan:
    if samples < 1 or not models:
        raise BenchError("Give at least one model and one sample.")
    per_model: dict[str, tuple[int, float]] = {}
    for model in models:
        usd = 0.0
        for p in prompts:
            if p.prompt_tokens is None or p.completion_tokens is None:
                raise BenchError(
                    f"Prompt '{p.id}' has no recorded token counts; the cost is unknown."
                )
            price_in, price_out = prices[model]
            usd += samples * (p.prompt_tokens * price_in + p.completion_tokens * price_out) / 1e6
        per_model[model] = (samples * len(prompts), usd)
    calls = sum(c for c, _ in per_model.values())
    usd = sum(u for _, u in per_model.values())
    if calls > RUN_MAX_CALLS:
        raise BenchError(f"The plan has {calls} calls. The cap is {RUN_MAX_CALLS} per run.")
    if usd > RUN_MAX_USD:
        raise BenchError(f"The plan costs about {usd:.2f} USD. The cap is {RUN_MAX_USD:g} per run.")
    if month_spent + usd > MONTH_MAX_USD:
        raise BenchError(
            f"The plan plus {month_spent:.2f} USD already spent this month passes "
            f"the {MONTH_MAX_USD:g} USD monthly cap."
        )
    return Plan(calls=calls, usd=usd, per_model=per_model)


class FakeClient:
    """Deterministic outputs from a fixture: {model: {prompt id: [reply, ...]}}. No network."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self.fixture = fixture
        self.calls = 0

    def complete(self, model: str, prompt: StoredPrompt, sample: int) -> Reply:
        try:
            raw = self.fixture[model][prompt.id][sample % len(self.fixture[model][prompt.id])]
        except (KeyError, IndexError, ZeroDivisionError) as error:
            raise BenchError(f"The fixture has no reply for {model} / {prompt.id}.") from error
        self.calls += 1
        return Reply(
            text=str(raw["text"]),
            provider=raw.get("provider"),
            prompt_tokens=raw.get("prompt_tokens"),
            completion_tokens=raw.get("completion_tokens"),
            latency_ms=raw.get("latency_ms"),
        )


class GatewayClient:
    """Posts to a running local gateway, one gateway address per model. The token is read from
    the environment and is never stored. The gateway holds the provider pin and the call caps."""

    def __init__(self, urls: Mapping[str, str]) -> None:
        self.urls = urls
        self.token = os.environ.get(TOKEN_VARIABLE, "")

    def complete(self, model: str, prompt: StoredPrompt, sample: int) -> Reply:
        if model not in self.urls or not self.token:
            raise BenchError(f"No gateway address for '{model}', or {TOKEN_VARIABLE} is not set.")
        if not self.urls[model].startswith(("http://127.0.0.1", "http://localhost")):
            raise BenchError("The gateway address must be on this machine.")
        body = json.dumps({"model": model, "messages": prompt.messages}).encode()
        request = urllib.request.Request(
            self.urls[model].rstrip("/") + "/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        started = time.monotonic()
        with urllib.request.urlopen(request, timeout=900) as response:
            data = json.loads(response.read())
        usage = data.get("usage") or {}
        return Reply(
            text=str(data["choices"][0]["message"]["content"]),
            provider=data.get("provider"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_ms=(time.monotonic() - started) * 1000,
        )


def check_outside_git(path: Path) -> None:
    probe = path.resolve()
    if any((p / ".git").exists() for p in (probe, *probe.parents)):
        raise BenchError("The bench store must be outside every git work tree.")


def month_spent(store: Path, now: datetime) -> float:
    spend = store / "spend.jsonl"
    if not spend.exists():
        return 0.0
    stem = f"{now:%Y-%m}"
    rows = [json.loads(line) for line in spend.read_text().splitlines() if line.strip()]
    return sum(float(r["usd"]) for r in rows if r["ts"].startswith(stem))


def output_path(store: Path, model: str, prompt_id: str, sample: int) -> Path:
    return store / "outputs" / model.replace("/", "__") / f"{prompt_id}.{sample}.json"


def _record(
    model: str, p: StoredPrompt, sample: int, reply: Reply, price: tuple[float, float]
) -> dict[str, Any]:
    usd: float | None = None
    reason = None
    if reply.prompt_tokens is None or reply.completion_tokens is None:
        reason = "the model did not report token counts"
    else:
        usd = (reply.prompt_tokens * price[0] + reply.completion_tokens * price[1]) / 1e6
    return {
        "schema": "AlphaBenchOutputV1",
        "model": model,
        "prompt_id": p.id,
        "stage": p.stage,
        "sample": sample,
        "text": reply.text,
        "provider": reply.provider,
        "provider_reason": None if reply.provider else "the call did not report its provider",
        "prompt_tokens": reply.prompt_tokens,
        "completion_tokens": reply.completion_tokens,
        "usd": usd,
        "usd_reason": reason,
        "latency_ms": reply.latency_ms,
        "latency_reason": None
        if reply.latency_ms is not None
        else "the call did not report latency",
    }


def run_bench(
    prompts: list[StoredPrompt],
    models: list[str],
    samples: int,
    prices: Mapping[str, tuple[float, float]],
    client: Client,
    store: Path,
    max_new_calls: int | None = None,
) -> RunResult:
    """Send each stored prompt to each model `samples` times. An output already stored is kept."""
    check_outside_git(store)
    now = datetime.now(UTC)
    make_plan(prompts, models, samples, prices, month_spent(store, now))
    new = 0
    for model in models:
        for p in prompts:
            for sample in range(samples):
                path = output_path(store, model, p.id, sample)
                if path.exists():
                    continue
                if max_new_calls is not None and new >= max_new_calls:
                    return RunResult(new_calls=new, finished=False)
                record = _record(model, p, sample, client.complete(model, p, sample), prices[model])
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                if record["usd"] is not None:
                    with (store / "spend.jsonl").open("a", encoding="utf-8") as spend:
                        spend.write(
                            json.dumps({"ts": now.isoformat(), "usd": record["usd"]}) + "\n"
                        )
                new += 1
    return RunResult(new_calls=new, finished=True)
