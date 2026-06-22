"""Project ALPHA local web IDE: browse, launch, and watch research runs in a browser.

A purely-additive FastAPI + Jinja + HTMX app that shells out to the installed ``alpha`` CLI and
reads the byte-stable artifacts it writes. It composes nothing itself, so it sits at the very top
of the architecture DAG (nothing imports it). Local single-user, $0, no auth.
"""

from __future__ import annotations

__version__ = "1.0.0"
