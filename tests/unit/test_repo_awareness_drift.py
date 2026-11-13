"""Every ADR is listed in the ADR index, its one listing.

Awareness that is remembered rots; awareness that is derived does not. The ADR files are the
derived fact; ``docs/adr/README.md`` is the one place that lists them (one home per fact). That
every workspace has a ``CONTEXT.md`` is checked by ``tests/unit/test_filesystem_contract.py``.
"""

from __future__ import annotations

import harness_awareness

from tests.unit._harness_support import REPO_ROOT as ROOT


def test_every_adr_file_is_listed_in_the_adr_index() -> None:
    assert harness_awareness.adr_files(ROOT), "docs/adr has no ADR files"
    missing = harness_awareness.adr_drift(ROOT)
    assert missing == [], f"add a row linking each of these to docs/adr/README.md: {missing}"
