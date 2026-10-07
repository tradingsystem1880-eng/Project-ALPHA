"""Generated owner-action contracts track the server without parsing TypeScript source.

The frontend's type test checks the explicit semantic-event exclusion. Here the generated
OpenAPI vocabulary is compared to the authoritative request model.
"""

from __future__ import annotations

import json
import typing
from pathlib import Path

from alpha_web.api.owner_auth import OwnerActionChallengeRequest


def test_generated_owner_actions_match_server_vocabulary() -> None:
    root = Path(__file__).resolve().parents[2]
    openapi = json.loads((root / "apps/alpha-web/frontend/openapi.json").read_text())
    schema = openapi["components"]["schemas"]["OwnerActionChallengeRequest"]
    generated = set(schema["properties"]["action_type"]["enum"])
    annotation = OwnerActionChallengeRequest.model_fields["action_type"].annotation
    assert generated == set(typing.get_args(annotation))
    assert "record_semantic_event" in generated
