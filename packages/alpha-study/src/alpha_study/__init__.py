"""Governed research-study composition seam."""

from __future__ import annotations

from importlib.metadata import version

from alpha_study.adapters import (
    adapt_double_bottom_events,
    project_double_bottom_events,
)
from alpha_study.authority import (
    DetectorValidationV1,
    ExplorationMandateV1,
    OperatorRegistrationV1,
)
from alpha_study.projections import (
    AdvisorProposalV1,
    FindingV1,
    MechanismEdgeV1,
    MechanismGraphV1,
    MechanismNodeV1,
    ProjectionRefV1,
    StudyWorkspaceManifestV1,
)
from alpha_study.semantic import (
    BlindSemanticProjectionV1,
    SemanticEventIdentityV1,
    SemanticPointV1,
    blind_semantic_projection,
    normalize_semantic_event,
    project_blind_semantic_read,
)
from alpha_study.tables import (
    EventRowV1,
    EventTableV1,
    FactorObservationTableV1,
    FactorObservationV1,
)
from alpha_study.values import FeatureInputRefV1, FeatureValueV1

__version__ = version("alpha-study")

__all__ = [
    "adapt_double_bottom_events",
    "EventRowV1",
    "EventTableV1",
    "FactorObservationTableV1",
    "FactorObservationV1",
    "FeatureInputRefV1",
    "FeatureValueV1",
    "project_double_bottom_events",
    "DetectorValidationV1",
    "ExplorationMandateV1",
    "OperatorRegistrationV1",
    "AdvisorProposalV1",
    "BlindSemanticProjectionV1",
    "FindingV1",
    "MechanismEdgeV1",
    "MechanismGraphV1",
    "MechanismNodeV1",
    "SemanticEventIdentityV1",
    "SemanticPointV1",
    "ProjectionRefV1",
    "blind_semantic_projection",
    "normalize_semantic_event",
    "project_blind_semantic_read",
    "StudyWorkspaceManifestV1",
    "__version__",
]
