"""One synthetic position-study request, with no reservation or execution authority.

This is an engineering prerequisite for a future registered rules/control protocol.
The always-flat rule is a position control, never an event-study control or statistic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from alpha_core import DataError
from alpha_research import EqualDurationResearchBars, ResearchArtifactRef, ResearchDatasetRef
from alpha_strategies.rules import canonical_json, rule_spec_from_json

_DATA_SHA256 = "fe98e729f4af4687dd41dc91eee6a0f69819b7f78e6831024c44c2ae236ac7d1"
_RULE = (
    '{"history":2,"long_when":[{"left":{"source":"close"},"op":">",'
    '"right":{"value":10}}],"name":"synthetic-close-above-ten","short_when":[],"version":1}'
)
_CONTROL = (
    '{"history":2,"long_when":[{"left":{"source":"close"},"op":"<",'
    '"right":{"value":0}}],"name":"synthetic-always-flat","short_when":[],"version":1}'
)


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@dataclass(frozen=True, slots=True)
class SyntheticRuleStudy:
    """Immutable fixed inputs, explicitly unadmitted to existing study/trial authority."""

    rules_spec: str
    control_spec: str
    data: EqualDurationResearchBars
    data_artifact: ResearchArtifactRef
    cutoff: datetime
    horizon_bars: int
    price_unit: str
    signal_unit: str
    capability: str

    def __post_init__(self) -> None:
        for name, expected in (("rules_spec", _RULE), ("control_spec", _CONTROL)):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise DataError(f"fixed synthetic {name} must be canonical RuleSpec text")
            canonical = canonical_json(rule_spec_from_json(value))
            if canonical != canonical_json(rule_spec_from_json(expected)):
                raise DataError(f"fixed synthetic {name} changed")
            object.__setattr__(self, name, canonical)
        if (
            type(self.cutoff) is not datetime
            or self.cutoff.isoformat() != datetime(2000, 1, 5, tzinfo=UTC).isoformat()
            or type(self.horizon_bars) is not int
            or self.horizon_bars != 1
            or self.price_unit != "synthetic_price"
            or self.signal_unit != "position"
            or self.capability != "frozen_rule_positions_v1"
        ):
            raise DataError("fixed synthetic cutoff/horizon/units/capability changed")
        expected_dataset = ResearchDatasetRef(
            dataset_id="synthetic-rules-v1",
            provider="synthetic",
            provider_symbol="RULES",
            symbol="RULES",
            venue="SYNTHETIC",
            timeframe="1d",
            timezone="UTC",
            session="UTC_DAY",
            content_sha256=_DATA_SHA256,
        )
        if (
            type(self.data) is not EqualDurationResearchBars
            or self.data.dataset != expected_dataset
        ):
            raise DataError("fixed synthetic data identity changed")
        raw = _bytes(
            [
                [
                    bar.start.isoformat(),
                    bar.end.isoformat(),
                    bar.available_at.isoformat(),
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                ]
                for bar in self.data.bars
            ]
        )
        if hashlib.sha256(raw).hexdigest() != _DATA_SHA256:
            raise DataError("fixed synthetic data bytes changed")
        expected_artifact = ResearchArtifactRef(
            artifact_id="synthetic-bars.json",
            kind="table",
            media_type="application/json",
            content_sha256=_DATA_SHA256,
            size_bytes=len(raw),
            row_count=5,
        )
        if (
            type(self.data_artifact) is not ResearchArtifactRef
            or self.data_artifact != expected_artifact
        ):
            raise DataError("fixed synthetic data artifact provenance changed or missing")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "SyntheticRuleStudyRequestV1",
            "authority": "none",
            "scientific_acceptance": "not_admitted",
            "rules_spec": self.rules_spec,
            "control_spec": self.control_spec,
            "dataset": self.data.dataset.to_dict(),
            "data_artifact": self.data_artifact.to_dict(),
            "cutoff": self.cutoff.isoformat(),
            "horizon_bars": self.horizon_bars,
            "price_unit": self.price_unit,
            "signal_unit": self.signal_unit,
            "capability": self.capability,
        }

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(_bytes(self.to_dict())).hexdigest()
