"""Suite-wide terminal determinism for CLI assertions.

``typer.rich_utils`` forces a colour terminal at import time whenever ``GITHUB_ACTIONS``,
``FORCE_COLOR`` or ``PY_COLORS`` is set (it does not honour ``NO_COLOR``), so on GitHub
runners help and error panels carry ANSI sequences and plain-token assertions fail
CI-only. This conftest runs before any test module imports typer: it strips the forcing
variables and sets ``NO_COLOR`` so the suite renders identically on every terminal.
"""

import os

os.environ["NO_COLOR"] = "1"
for _name in ("GITHUB_ACTIONS", "FORCE_COLOR", "PY_COLORS"):
    os.environ.pop(_name, None)
