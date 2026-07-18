"""Project ALPHA CLI package."""

from importlib.metadata import version

from alpha_cli.run_store import RUN_DIRS

__version__ = version("alpha-cli")

__all__ = ["RUN_DIRS", "__version__"]
