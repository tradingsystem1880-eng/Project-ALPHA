"""Frozen chronological evidence topology for adaptive strategy research."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from alpha_core import DataError
from alpha_research._canonical import canonical_sha256

EvidencePhase = Literal["discovery", "confirmation", "final_holdout"]
_EVIDENCE_PHASES = {"discovery", "confirmation", "final_holdout"}
# Group-count cuts guarantee ~20% of GROUPS to the final holdout, not of observations;
# this floor guarantees the holdout keeps a defensible observation mass regardless of
# group-size skew. Unit groups (one observation per group) always realize exactly 20%.
_MIN_HOLDOUT_OBSERVATION_SHARE = 0.10
_EVIDENCE_PHASE_ORDER: tuple[EvidencePhase, ...] = (
    "discovery",
    "confirmation",
    "final_holdout",
)


@dataclass(frozen=True, slots=True)
class EvidenceWindow:
    """One half-open observation-index window in the research topology."""

    phase: EvidencePhase
    start: int
    stop: int

    def __post_init__(self) -> None:
        if self.phase not in _EVIDENCE_PHASES:
            raise DataError(f"unsupported evidence phase {self.phase!r}")
        if (
            isinstance(self.start, bool)
            or not isinstance(self.start, int)
            or isinstance(self.stop, bool)
            or not isinstance(self.stop, int)
        ):
            raise DataError("evidence-window indices must be integers")
        if self.start < 0 or self.stop <= self.start:
            raise DataError(
                f"evidence window must satisfy 0 <= start < stop, got [{self.start}, {self.stop})"
            )

    @property
    def length(self) -> int:
        return self.stop - self.start

    def to_dict(self) -> dict[str, int | str]:
        return {"phase": self.phase, "start": self.start, "stop": self.stop}


@dataclass(frozen=True, slots=True)
class EvidenceDependencyGroup:
    """One indivisible, contiguous date/session/dependence group."""

    key: str
    start: int
    stop: int

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise DataError("evidence dependency-group key must be a non-empty string")
        if (
            isinstance(self.start, bool)
            or not isinstance(self.start, int)
            or isinstance(self.stop, bool)
            or not isinstance(self.stop, int)
        ):
            raise DataError("evidence dependency-group indices must be integers")
        if self.start < 0 or self.stop <= self.start:
            raise DataError(
                "evidence dependency group must satisfy "
                f"0 <= start < stop, got [{self.start}, {self.stop})"
            )

    def to_dict(self) -> dict[str, int | str]:
        return {"key": self.key, "start": self.start, "stop": self.stop}


def _validate_total(total: int) -> None:
    if isinstance(total, bool) or not isinstance(total, int) or total < 5:
        raise DataError(f"60/20/20 evidence topology needs at least 5 observations, got {total!r}")


def _unit_groups(total: int) -> tuple[EvidenceDependencyGroup, ...]:
    _validate_total(total)
    return tuple(
        EvidenceDependencyGroup(key=f"observation:{index}", start=index, stop=index + 1)
        for index in range(total)
    )


def _groups_from_keys(keys: Sequence[str]) -> tuple[EvidenceDependencyGroup, ...]:
    if isinstance(keys, (str, bytes)) or not isinstance(keys, Sequence) or not keys:
        raise DataError("dependency-group keys must be a non-empty ordered sequence")
    groups: list[EvidenceDependencyGroup] = []
    seen: set[str] = set()
    active_key: str | None = None
    active_start = 0
    for index, key in enumerate(keys):
        if not isinstance(key, str) or not key.strip():
            raise DataError("dependency-group keys must be non-empty strings")
        if active_key is None:
            active_key = key
            seen.add(key)
            continue
        if key == active_key:
            continue
        groups.append(EvidenceDependencyGroup(active_key, active_start, index))
        if key in seen:
            raise DataError(
                f"dependency-group key {key!r} must be contiguous and cannot recur later"
            )
        active_key = key
        active_start = index
        seen.add(key)
    assert active_key is not None
    groups.append(EvidenceDependencyGroup(active_key, active_start, len(keys)))
    if len(groups) < 5:
        raise DataError(
            f"60/20/20 evidence topology needs at least 5 dependency groups, got {len(groups)}"
        )
    return tuple(groups)


def _validate_groups(
    total: int, groups: tuple[EvidenceDependencyGroup, ...]
) -> tuple[EvidenceDependencyGroup, ...]:
    _validate_total(total)
    if not isinstance(groups, tuple):
        raise DataError("evidence dependency groups must be an immutable tuple")
    if not groups:
        return _unit_groups(total)
    if len(groups) < 5:
        raise DataError(
            f"60/20/20 evidence topology needs at least 5 dependency groups, got {len(groups)}"
        )
    cursor = 0
    keys: set[str] = set()
    for group in groups:
        if not isinstance(group, EvidenceDependencyGroup):
            raise DataError("evidence dependency groups contain an unsupported value")
        if group.start != cursor:
            raise DataError("evidence dependency groups must cover observations contiguously")
        if group.key in keys:
            raise DataError("evidence dependency-group keys must be unique and ordered")
        cursor = group.stop
        keys.add(group.key)
    if cursor != total:
        raise DataError(
            "evidence dependency groups must cover every observation exactly once, "
            f"stopped at {cursor} of {total}"
        )
    return groups


def _canonical_windows(
    total: int, groups: tuple[EvidenceDependencyGroup, ...]
) -> tuple[EvidenceWindow, EvidenceWindow, EvidenceWindow]:
    validated_groups = _validate_groups(total, groups)
    group_count = len(validated_groups)
    # Integer group cut points avoid floating-point drift. Any indivisible remainder stays in the
    # newest, most protected final-holdout window rather than expanding adaptive discovery. Cuts
    # resolve to group stops, so no date/session/dependence group can straddle two evidence zones.
    discovery_group_stop = group_count * 3 // 5
    confirmation_group_stop = group_count * 4 // 5
    discovery_stop = validated_groups[discovery_group_stop - 1].stop
    confirmation_stop = validated_groups[confirmation_group_stop - 1].stop
    return (
        EvidenceWindow("discovery", 0, discovery_stop),
        EvidenceWindow("confirmation", discovery_stop, confirmation_stop),
        EvidenceWindow("final_holdout", confirmation_stop, total),
    )


@dataclass(frozen=True, slots=True)
class ResearchEvidenceTopology:
    """A group-atomic 60/20/20 split with a fail-closed forward-outcome embargo."""

    total_observations: int
    discovery: EvidenceWindow
    confirmation: EvidenceWindow
    final_holdout: EvidenceWindow
    dependency_groups: tuple[EvidenceDependencyGroup, ...] = ()
    forward_outcome_observations: int = 0

    def __post_init__(self) -> None:
        groups = _validate_groups(self.total_observations, self.dependency_groups)
        if groups != self.dependency_groups:
            object.__setattr__(self, "dependency_groups", groups)
        if (
            isinstance(self.forward_outcome_observations, bool)
            or not isinstance(self.forward_outcome_observations, int)
            or self.forward_outcome_observations < 0
        ):
            raise DataError("forward_outcome_observations must be a non-negative integer")
        expected = _canonical_windows(self.total_observations, groups)
        actual = (self.discovery, self.confirmation, self.final_holdout)
        if actual != expected:
            raise DataError(
                "research evidence windows must equal the canonical 60/20/20 group-atomic "
                "chronological split"
            )
        # Cuts are made on group COUNTS, so size-skewed dependence groups can shift the
        # realized observation shares. A token holdout would silently hollow out the
        # program's strongest protection, so it is rejected rather than warned about.
        holdout_share = self.final_holdout.length / self.total_observations
        if holdout_share < _MIN_HOLDOUT_OBSERVATION_SHARE:
            raise DataError(
                "group-atomic 60/20/20 allocation left the final holdout with "
                f"{self.final_holdout.length} of {self.total_observations} observations "
                f"({holdout_share:.1%}, below the {_MIN_HOLDOUT_OBSERVATION_SHARE:.0%} "
                "floor); dependence groups are too size-skewed — regroup or extend the "
                "sample"
            )
        for window in actual:
            if window.length <= self.forward_outcome_observations:
                raise DataError(
                    f"{window.phase} boundary embargo of "
                    f"{self.forward_outcome_observations} observations leaves no eligible event "
                    "observations"
                )

    @classmethod
    def for_observations(
        cls,
        total_observations: int,
        *,
        forward_outcome_observations: int = 0,
    ) -> ResearchEvidenceTopology:
        """Build the legacy one-observation-per-group topology for contemporaneous data.

        A non-zero forward horizon must be registered explicitly; its final observations in every
        evidence window become ineligible event anchors.
        """

        groups = _unit_groups(total_observations)
        discovery, confirmation, final_holdout = _canonical_windows(total_observations, groups)
        return cls(
            total_observations,
            discovery,
            confirmation,
            final_holdout,
            groups,
            forward_outcome_observations,
        )

    @classmethod
    def for_dependency_groups(
        cls,
        dependency_group_keys: Sequence[str],
        *,
        forward_outcome_observations: int,
    ) -> ResearchEvidenceTopology:
        """Partition groups after explicitly registering even a zero forward horizon."""

        groups = _groups_from_keys(dependency_group_keys)
        total = len(dependency_group_keys)
        discovery, confirmation, final_holdout = _canonical_windows(total, groups)
        return cls(
            total,
            discovery,
            confirmation,
            final_holdout,
            groups,
            forward_outcome_observations,
        )

    def partition_for(self, observation_index: int) -> EvidencePhase:
        if (
            isinstance(observation_index, bool)
            or not isinstance(observation_index, int)
            or not 0 <= observation_index < self.total_observations
        ):
            raise DataError(
                f"observation index {observation_index!r} is outside [0, {self.total_observations})"
            )
        if observation_index < self.discovery.stop:
            return "discovery"
        if observation_index < self.confirmation.stop:
            return "confirmation"
        return "final_holdout"

    @property
    def boundary_embargo_observations(self) -> int:
        """Right-edge observations excluded as event anchors in every evidence zone."""

        return self.forward_outcome_observations

    def eligible_event_window(self, phase: EvidencePhase) -> EvidenceWindow:
        """Return event-anchor indices whose registered outcome stays inside ``phase``."""

        windows = {
            "discovery": self.discovery,
            "confirmation": self.confirmation,
            "final_holdout": self.final_holdout,
        }
        if phase not in windows:
            raise DataError(f"unsupported evidence phase {phase!r}")
        window = windows[phase]
        return EvidenceWindow(
            window.phase,
            window.start,
            window.stop - self.forward_outcome_observations,
        )

    def event_partition_for(self, observation_index: int) -> EvidencePhase:
        """Classify an event only when its registered forward outcome cannot cross a boundary."""

        phase = self.partition_for(observation_index)
        outcome_index = observation_index + self.forward_outcome_observations
        if outcome_index >= self.total_observations or self.partition_for(outcome_index) != phase:
            raise DataError(
                "registered forward outcome horizon crosses the "
                f"{phase} boundary: event={observation_index}, outcome={outcome_index}"
            )
        return phase

    def validate_outcome_window(self, event_index: int, outcome_index: int) -> EvidencePhase:
        """Validate an actual forward endpoint against the registered within-zone horizon."""

        phase = self.event_partition_for(event_index)
        outcome_phase = self.partition_for(outcome_index)
        if outcome_index < event_index:
            raise DataError("outcome index cannot precede its event index")
        if outcome_index - event_index > self.forward_outcome_observations:
            raise DataError("outcome window exceeds the registered forward outcome horizon")
        # ``event_partition_for`` proves the registered maximum endpoint stays in ``phase``.
        # Because evidence windows are contiguous, every non-negative endpoint no farther than
        # that maximum necessarily remains in the same phase too.
        assert outcome_phase == phase
        return phase

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "allocation_unit": "dependency_group",
            "total_observations": self.total_observations,
            "dependency_groups": [group.to_dict() for group in self.dependency_groups],
            "discovery": self.discovery.to_dict(),
            "confirmation": self.confirmation.to_dict(),
            "final_holdout": self.final_holdout.to_dict(),
            "outcome_boundary_policy": {
                "forward_outcome_observations": self.forward_outcome_observations,
                "right_boundary_embargo_observations": self.boundary_embargo_observations,
                "cross_boundary_outcomes": "REJECT",
            },
            "eligible_event_windows": {
                phase: self.eligible_event_window(phase).to_dict()
                for phase in _EVIDENCE_PHASE_ORDER
            },
        }

    @property
    def contract_hash(self) -> str:
        return canonical_sha256(self.to_dict())
