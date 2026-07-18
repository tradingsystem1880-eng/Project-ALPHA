"""Project ALPHA Workstation: an institutional research & trading terminal in the browser.

A purely-additive FastAPI JSON+SSE backend that serves a Vite/React/Dockview single-page app and
shells out to the installed ``alpha`` CLI, reading the byte-stable artifacts it writes. It composes
nothing itself, so it sits at the very top of the architecture DAG (nothing imports it). Local
single-user, $0, no auth, loopback only.
"""

from __future__ import annotations

from importlib.metadata import version

__version__ = version("alpha-web")
