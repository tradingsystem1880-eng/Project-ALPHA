"""Project ALPHA strategies package.

Strategy classes live in their own modules (``ts_momentum``, ``signal_replay``, ...) and
are imported lazily by consumers — importing this package must never drag in nautilus.
"""

from __future__ import annotations

from importlib.metadata import version

__version__ = version("alpha-strategies")
