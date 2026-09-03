"""The SPA's owner-action vocabulary must be exactly the server's (ADR-0030).

``OwnerActionButton`` and ``ownerAuth.ts`` can only offer what ``owner_auth.py`` dispatches; a
type added on one side and not the other would either dead-end a button (server 422) or hide a
step the owner can complete. ``record_semantic_event`` is the one deliberate exception: it is
special-dispatched by the Study tab's server-owned cycle and never offered as a button.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

from alpha_web.api.owner_auth import OwnerActionChallengeRequest

_CLIENT = (
    Path(__file__).resolve().parents[2]
    / "apps"
    / "alpha-web"
    / "frontend"
    / "src"
    / "api"
    / "client.ts"
)

_SPA_EXCLUDED = {"record_semantic_event"}


def _spa_action_types() -> set[str]:
    source = _CLIENT.read_text(encoding="utf-8")
    start = source.index("export type OwnerActionType =")
    end = source.index("\n\n", start)
    return set(re.findall(r"\|\s*'([a-z_0-9]+)'", source[start:end]))


def _server_action_types() -> set[str]:
    annotation = OwnerActionChallengeRequest.model_fields["action_type"].annotation
    return set(typing.get_args(annotation))


def test_spa_owner_action_types_match_the_server_vocabulary() -> None:
    spa = _spa_action_types()
    server = _server_action_types()
    assert spa, "no OwnerActionType members parsed from client.ts"
    assert spa - server == set(), (
        f"SPA offers actions the server does not dispatch: {sorted(spa - server)}"
    )
    assert server - spa == _SPA_EXCLUDED, (
        f"server actions the SPA cannot offer: {sorted(server - spa - _SPA_EXCLUDED)}"
    )
