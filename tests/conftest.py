"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture(scope="session", autouse=True)
def _nautilus_logging() -> Iterator[None]:
    """Initialize nautilus's global logger once per session and hold its guard.

    A live ``TradingNode`` initializes the global (Rust) logging subsystem on first start and tears
    it down when its ``LogGuard`` drops on dispose. A second live node in the same process then runs
    against a dead logger and aborts the interpreter (SIGABRT). Initializing once here (bypassed, no
    output) and holding the guard for the session means every node sees logging as already
    initialized, skips its own init, and never tears it down — so any number of live nodes coexist.
    """
    from nautilus_trader.common.component import init_logging, is_logging_initialized

    guard: Any = None
    if not is_logging_initialized():
        guard = init_logging(bypass=True)
    try:
        yield
    finally:
        del guard  # released only at session teardown


@pytest.fixture
def paper_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """A fresh event loop per paper-trading sandbox test.

    A nautilus ``TradingNode`` binds to ``asyncio.get_event_loop()`` at construction; without a
    per-test loop, a disposed node's loop leaks into the next test. This installs a new loop (so a
    node built in the test body captures it) and detaches it afterwards.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        asyncio.set_event_loop(None)
