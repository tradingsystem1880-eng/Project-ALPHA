"""nautilus_trader is the spec-mandated engine; confirm it's installed and importable in CI."""

from __future__ import annotations

import nautilus_trader
import pandas as pd


def test_nautilus_trader_available_and_recent() -> None:
    major, minor, *_ = (int(x) for x in nautilus_trader.__version__.split(".")[:2])
    assert (major, minor) >= (1, 228)


def test_pandas_is_engine_compatible() -> None:
    # nautilus requires pandas<3; the workspace pins to the 2.x line so the engine loads.
    assert int(pd.__version__.split(".")[0]) == 2
