"""Deterministic, research-only primitives for falsifiable strategy investigation.

This package owns no network, persistence, credentials, execution, or dynamic-code surface. It
imports only ``alpha_core`` internally; orchestration belongs to ``alpha_cli``.
"""

from __future__ import annotations

from importlib.metadata import version

from alpha_research.artifacts import (
    ArtifactKind,
    ChartEvidencePhase,
    ChartWatermark,
    ResearchArtifactRef,
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
)
from alpha_research.boundary import (
    ResearchChartFingerprintV1,
    ResearchD2BoundaryV1,
    ResearchEvidenceSharesV1,
    ResearchEvidenceZoneBoundaryV1,
)
from alpha_research.conditional_returns import (
    conditional_return_summary,
    difference_in_means,
    forward_returns,
    quantile_breakdown,
)
from alpha_research.confirmation import (
    ClaimDirection,
    ConfirmationEvidence,
    ConfirmationOutcome,
    ConfirmationStatus,
    classify_confirmation,
)
from alpha_research.data import EqualDurationResearchBars, ResearchBar, ResearchDatasetRef
from alpha_research.descriptives import (
    autocorrelation,
    coverage_summary,
    effective_sample_size,
    return_distribution,
    seasonality_by_weekday,
    volatility_regime_tags,
)
from alpha_research.event_study import (
    EventStudyObservation,
    MatchedEventControlPair,
    MatchedEventStudy,
    PredictiveAssociationEstimate,
    PreEventCovariate,
    PurgedEventStudy,
    evaluate_event_association,
    evaluate_matched_association,
    match_event_controls,
    purge_overlapping_outcomes,
)
from alpha_research.gate_packet import (
    ResearchDisposition,
    ResearchGatePacket,
    ResearchOutcome,
    build_research_gate_packet,
    confirmation_classification_from_evidence,
)
from alpha_research.ic import rank_ic, rolling_rank_ic
from alpha_research.leadlag import leadlag_profile, leakage_diagnostic
from alpha_research.market_state import (
    MarketSessionCloseV1,
    MarketStateArtifactV1,
    MarketStateConditionalValueV1,
    MarketStateContractV1,
    MarketStatePointV1,
    condition_values_by_market_state,
    derive_market_state,
)
from alpha_research.multiple_testing import (
    FrozenSecondaryFamily,
    HolmAdjustedHypothesis,
    SecondaryHypothesis,
    holm_adjust_secondary_family,
)
from alpha_research.patterns import (
    DoubleBottomEvent,
    DoubleBottomSpec,
    detect_double_bottom_events,
)
from alpha_research.power import (
    ProspectivePowerResult,
    projected_confirmation_power,
    required_observations_known_sigma,
    simulate_prospective_power_known_sigma,
)
from alpha_research.rendering import render_research_line_chart
from alpha_research.stability import (
    rolling_effect_size,
    subsample_consistency,
    temporal_split_effects,
)
from alpha_research.topology import (
    EvidenceDependencyGroup,
    EvidencePhase,
    EvidenceWindow,
    ResearchEvidenceTopology,
)

__version__ = version("alpha-research")
__all__ = [
    "ArtifactKind",
    "ChartEvidencePhase",
    "ChartWatermark",
    "ClaimDirection",
    "ConfirmationEvidence",
    "ConfirmationOutcome",
    "ConfirmationStatus",
    "DoubleBottomEvent",
    "DoubleBottomSpec",
    "EqualDurationResearchBars",
    "EventStudyObservation",
    "EvidenceDependencyGroup",
    "EvidencePhase",
    "EvidenceWindow",
    "FrozenSecondaryFamily",
    "HolmAdjustedHypothesis",
    "MatchedEventControlPair",
    "MatchedEventStudy",
    "MarketSessionCloseV1",
    "MarketStateArtifactV1",
    "MarketStateConditionalValueV1",
    "MarketStateContractV1",
    "MarketStatePointV1",
    "PreEventCovariate",
    "PredictiveAssociationEstimate",
    "ProspectivePowerResult",
    "PurgedEventStudy",
    "ResearchArtifactRef",
    "ResearchBar",
    "ResearchChartData",
    "ResearchChartFingerprintV1",
    "ResearchChartPoint",
    "ResearchChartSeries",
    "ResearchD2BoundaryV1",
    "ResearchDatasetRef",
    "ResearchDisposition",
    "ResearchEvidenceSharesV1",
    "ResearchEvidenceTopology",
    "ResearchEvidenceZoneBoundaryV1",
    "ResearchGatePacket",
    "ResearchOutcome",
    "SecondaryHypothesis",
    "autocorrelation",
    "build_research_gate_packet",
    "classify_confirmation",
    "conditional_return_summary",
    "condition_values_by_market_state",
    "confirmation_classification_from_evidence",
    "coverage_summary",
    "detect_double_bottom_events",
    "difference_in_means",
    "derive_market_state",
    "effective_sample_size",
    "evaluate_event_association",
    "evaluate_matched_association",
    "forward_returns",
    "holm_adjust_secondary_family",
    "leadlag_profile",
    "leakage_diagnostic",
    "match_event_controls",
    "purge_overlapping_outcomes",
    "quantile_breakdown",
    "projected_confirmation_power",
    "rank_ic",
    "render_research_line_chart",
    "required_observations_known_sigma",
    "return_distribution",
    "rolling_effect_size",
    "rolling_rank_ic",
    "seasonality_by_weekday",
    "simulate_prospective_power_known_sigma",
    "subsample_consistency",
    "temporal_split_effects",
    "volatility_regime_tags",
]
