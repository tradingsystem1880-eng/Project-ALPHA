"""Project ALPHA strategies package.

Strategy classes live in their own modules (``ts_momentum``, ``signal_replay``, ...) and
are imported lazily by consumers — importing this package must never drag in nautilus.
"""

from __future__ import annotations

__version__ = "0.0.0"
