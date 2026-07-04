"""Upstream Kronos model code (github.com/shiyu-coder/Kronos), pinned @ 67b630e6, MIT.

Import surface for the alpha_forecast facade; nothing else may import this package.
Importing it pulls in torch — keep it out of module-level imports (lazy-load only).
"""

from alpha_forecast._vendor.kronos.kronos import Kronos, KronosPredictor, KronosTokenizer

__all__ = ["Kronos", "KronosPredictor", "KronosTokenizer"]
