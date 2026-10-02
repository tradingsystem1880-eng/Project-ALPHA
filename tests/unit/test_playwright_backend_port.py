"""Concurrent checkout gates must launch their own disposable backend port."""

import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest


def load_module() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts/run_playwright_backend.py"
    spec = importlib.util.spec_from_file_location("playwright_backend", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_isolated_backend_port_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    monkeypatch.setattr(module.os, "environ", dict(os.environ))
    monkeypatch.setenv("ALPHA_PLAYWRIGHT_PORT", "18802")
    calls = []
    monkeypatch.setattr(module.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))
    module.main()
    assert calls[0]["port"] == 18802
    assert calls[0]["host"] == "127.0.0.1"
    assert os.environ["ALPHA_WEB_PORT"] == "18802"
    assert os.environ["ALPHA_PAPER_ENABLED"] == "false"


@pytest.mark.parametrize("value", ["0", "1023", "65536", "8801", "wrong", "8802.5"])
def test_invalid_or_owner_port_is_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    module = load_module()
    monkeypatch.setenv("ALPHA_PLAYWRIGHT_PORT", value)
    with pytest.raises(ValueError, match="ALPHA_PLAYWRIGHT_PORT"):
        module.playwright_port()


def test_default_port_is_retained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHA_PLAYWRIGHT_PORT", raising=False)
    assert load_module().playwright_port() == 8802
