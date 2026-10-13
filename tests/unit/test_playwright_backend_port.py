"""Concurrent checkout gates must launch their own disposable backend port."""

import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest
from fastapi import FastAPI


@pytest.fixture(autouse=True)
def restore_investigation_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    # The disposable server patches dispatch in its own process; these tests share one.
    import sys

    from alpha_web import _invoke

    monkeypatch.setattr(_invoke, "_command", _invoke._command)
    monkeypatch.setattr(sys, "path", list(sys.path))


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


def test_combined_backend_keeps_disposable_fixtures_and_restores_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    monkeypatch.setattr(module.os, "environ", dict(os.environ))
    monkeypatch.setenv("ALPHA_BULK_DATA_DIR", str(tmp_path / "owner-bulk"))
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "synthetic-forbidden-key")
    original = Path.cwd()
    observed = []

    def serve(app: FastAPI, **kwargs: object) -> None:
        store = Path(os.environ["ALPHA_DATA_DIR"])
        observed.append(store)
        assert Path.cwd() == store.resolve()
        assert os.environ["ALPHA_BULK_DATA_DIR"] == str(store / "bulk")
        assert "ALPHA_TIINGO_API_KEY" not in os.environ
        assert any(
            getattr(route, "path", None) == "/__fixture/investigations" for route in app.routes
        )
        assert (store / "store").is_dir()

    monkeypatch.setattr(module.uvicorn, "run", serve)
    try:
        module.main()
        assert Path.cwd() == original
        assert len(observed) == 1
        assert not observed[0].exists()
    finally:
        os.chdir(original)
