"""Golden pins for content-addressed identities and canonical-JSON conventions.

These digests pin the CURRENT serialization behavior byte-for-byte. A failing golden
means a content-identity convention drifted: either revert the drift, or — if the
change is a conscious breaking generation change — update the pin together with the
required version bumps (see the generation policy in alpha_cli.research_runtime).

Two canonical-JSON conventions are DELIBERATELY in production and are pinned apart:

* escaped (``ensure_ascii=True``): ``alpha_cli.control_store._canonical_json`` and
  ``alpha_cli.research_runtime._canonical`` — every non-ASCII code point serialized
  as ``\\uXXXX``.
* raw UTF-8 (``ensure_ascii=False``): ``alpha_research._canonical.canonical_sha256``
  and ``alpha_research.gate_packet._canonical_json_bytes``.

Consolidating them would change one family's stored bytes and content IDs for zero
behavioral gain; the risk worth guarding is silent future divergence, which these
pins convert into a loud test failure.
"""

from __future__ import annotations

import hashlib

from alpha_cli.control_store import _canonical_json
from alpha_cli.research_runtime import (
    _GENERATION_60M,
    _GENERATION_DAILY,
    _d0_fixture_definition,
    _sha,
)
from alpha_research._canonical import canonical_sha256
from alpha_research.gate_packet import _canonical_json_bytes
from alpha_research.multiple_testing import FrozenSecondaryFamily, SecondaryHypothesis
from alpha_research.topology import ResearchEvidenceTopology

_UNICODE_PROBE = {"n": 1.5, "text": "Résumé — ümlaut"}


def test_escaped_serializer_family_pins_exact_bytes() -> None:
    escaped = '{"n":1.5,"text":"R\\u00e9sum\\u00e9 \\u2014 \\u00fcmlaut"}'
    assert _canonical_json(_UNICODE_PROBE, "golden probe") == escaped
    assert _sha(_UNICODE_PROBE) == hashlib.sha256(escaped.encode("utf-8")).hexdigest()
    assert _sha(_UNICODE_PROBE) == (
        "df268715b613ddad768fe2f4235d0a49c3a36337e94e8252599fe837f21834cc"
    )


def test_raw_utf8_serializer_family_pins_exact_bytes() -> None:
    raw = '{"n":1.5,"text":"Résumé — ümlaut"}'.encode()
    assert _canonical_json_bytes(_UNICODE_PROBE) == raw
    assert canonical_sha256(_UNICODE_PROBE) == hashlib.sha256(raw).hexdigest()
    assert canonical_sha256(_UNICODE_PROBE) == (
        "ce6241e92db32cc7e86ea935937bdaf06972d75a76a6b4ac5a16fd8d685f8ce2"
    )


def test_registered_topology_contract_hash_is_pinned() -> None:
    topology = ResearchEvidenceTopology.for_observations(25, forward_outcome_observations=4)
    assert topology.contract_hash == (
        "0a6c95a68e55db580046b17a5cd3f7efa217208f7037306c8e45df4b4d8a2c97"
    )


def test_frozen_family_contract_hash_is_pinned() -> None:
    family = FrozenSecondaryFamily(
        family_id="golden-family",
        hypotheses=(
            SecondaryHypothesis("h-a", 0.01),
            SecondaryHypothesis("h-b", 0.04),
        ),
    )
    assert family.contract_hash == (
        "0377644baf1ce9ea35e33b5a419e28db739815bb18421ff7fddaafa3a8d3d7fe"
    )


def test_registered_d0_fixture_definition_hash_is_pinned() -> None:
    assert _sha(_d0_fixture_definition(_GENERATION_60M)) == (
        "c66c38520c10efb2405758dcf46d98a30c35cc35db68b99bfa936b2b95bb8cb4"
    )
    assert _sha(_d0_fixture_definition(_GENERATION_DAILY)) == (
        "8f4a968acb17f90f03ff184f7fb58b2ebf8b61ecc4e6639c32cde895c3e4d978"
    )
