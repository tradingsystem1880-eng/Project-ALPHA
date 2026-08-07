"""Version stamps that make cached figures self-invalidating.

``RENDERER_VERSION`` is also folded into ``svg.hashsalt``, so bumping it changes output
bytes deterministically instead of by accident, and every cached figure keyed on the old
version becomes unreachable rather than stale.
"""

from __future__ import annotations

from typing import Final

#: Bump on ANY visual change: theme, layout, mark styling, rcParams, tick placement, or a
#: builder that composes a different spec from the same artifacts.
#:
#: 2 — a legibility pass driven by looking at the rendered output: y-labels budgeted to
#:     panel height rather than panel count (a four-panel figure printed rotated labels
#:     that ran into each other), panel notes drawn on a backing box so they no longer sit
#:     on top of the price line, `price_signal` groups indicators by unit and overlays the
#:     price-unit ones on price -- how a moving average is meant to be read -- with the
#:     categorical ramp when several share a panel, and several axis labels shortened so
#:     they fit rather than elide.
RENDERER_VERSION: Final = 2

#: Bump only when the cache key composition, on-disk path, or file format changes.
#:
#: Restated in ``alpha_cli.figure_cache``, which must stay importable without matplotlib.
#: A drift test holds the two equal; bump both together.
FIGURES_CACHE_VERSION: Final = 1
