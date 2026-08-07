"""Version stamps that make cached figures self-invalidating.

``RENDERER_VERSION`` is also folded into ``svg.hashsalt``, so bumping it changes output
bytes deterministically instead of by accident, and every cached figure keyed on the old
version becomes unreachable rather than stale.
"""

from __future__ import annotations

from typing import Final

#: Bump on ANY visual change: theme, layout, mark styling, rcParams, tick placement.
RENDERER_VERSION: Final = 1

#: Bump only when the cache key composition, on-disk path, or file format changes.
#:
#: Restated in ``alpha_cli.figure_cache``, which must stay importable without matplotlib.
#: A drift test holds the two equal; bump both together.
FIGURES_CACHE_VERSION: Final = 1
