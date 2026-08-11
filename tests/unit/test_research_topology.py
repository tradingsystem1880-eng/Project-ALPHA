"""Chronological discovery/confirmation/final-holdout topology."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from alpha_core import DataError
from alpha_research import EvidenceDependencyGroup, EvidenceWindow, ResearchEvidenceTopology


def test_sixty_twenty_twenty_topology_is_contiguous_and_conservative() -> None:
    topology = ResearchEvidenceTopology.for_observations(11)

    assert topology.discovery == EvidenceWindow("discovery", 0, 6)
    assert topology.confirmation == EvidenceWindow("confirmation", 6, 8)
    assert topology.final_holdout == EvidenceWindow("final_holdout", 8, 11)
    assert topology.partition_for(0) == "discovery"
    assert topology.partition_for(7) == "confirmation"
    assert topology.partition_for(10) == "final_holdout"


def test_exact_multiple_of_five_has_exact_sixty_twenty_twenty_lengths() -> None:
    topology = ResearchEvidenceTopology.for_observations(100)

    assert topology.discovery.length == 60
    assert topology.confirmation.length == 20
    assert topology.final_holdout.length == 20


def test_topology_rejects_too_few_observations_and_out_of_range_index() -> None:
    with pytest.raises(DataError, match="at least 5"):
        ResearchEvidenceTopology.for_observations(4)

    topology = ResearchEvidenceTopology.for_observations(10)
    with pytest.raises(DataError, match="outside"):
        topology.partition_for(10)

    with pytest.raises(DataError, match="integers"):
        EvidenceWindow("discovery", 0.5, 2)  # type: ignore[arg-type]
    with pytest.raises(DataError, match="phase"):
        EvidenceWindow("other", 0, 2)  # type: ignore[arg-type]
    with pytest.raises(DataError, match="start < stop"):
        EvidenceWindow("discovery", 2, 2)


def test_topology_rejects_noncanonical_manual_boundaries() -> None:
    with pytest.raises(DataError, match="canonical 60/20/20"):
        ResearchEvidenceTopology(
            total_observations=10,
            discovery=EvidenceWindow("discovery", 0, 5),
            confirmation=EvidenceWindow("confirmation", 5, 8),
            final_holdout=EvidenceWindow("final_holdout", 8, 10),
        )


def test_topology_is_frozen_and_hash_is_deterministic() -> None:
    first = ResearchEvidenceTopology.for_observations(25)
    second = ResearchEvidenceTopology.for_observations(25)

    assert first.contract_hash == second.contract_hash
    assert len(first.contract_hash) == 64
    with pytest.raises(FrozenInstanceError):
        first.total_observations = 30  # type: ignore[misc]


def test_intraday_observations_are_partitioned_by_complete_session() -> None:
    session_ids = tuple(
        f"2026-07-{session:02d}:SPY:RTH" for session in range(1, 11) for _bar in range(4)
    )

    topology = ResearchEvidenceTopology.for_dependency_groups(
        session_ids,
        forward_outcome_observations=0,
    )

    assert topology.total_observations == 40
    assert topology.discovery == EvidenceWindow("discovery", 0, 24)
    assert topology.confirmation == EvidenceWindow("confirmation", 24, 32)
    assert topology.final_holdout == EvidenceWindow("final_holdout", 32, 40)
    assert tuple(group.key for group in topology.dependency_groups) == tuple(
        f"2026-07-{session:02d}:SPY:RTH" for session in range(1, 11)
    )
    for group in topology.dependency_groups:
        assert {topology.partition_for(index) for index in range(group.start, group.stop)} == {
            topology.partition_for(group.start)
        }


def test_dependency_groups_must_be_ordered_contiguous_and_sufficient() -> None:
    with pytest.raises(DataError, match="contiguous"):
        ResearchEvidenceTopology.for_dependency_groups(
            ("day-1", "day-2", "day-1"),
            forward_outcome_observations=0,
        )

    with pytest.raises(DataError, match="at least 5 dependency groups"):
        ResearchEvidenceTopology.for_dependency_groups(
            tuple(f"day-{day}" for day in range(1, 5) for _bar in range(10)),
            forward_outcome_observations=0,
        )


def test_registered_forward_horizon_embargoes_each_evidence_boundary() -> None:
    session_ids = tuple(f"session-{session}" for session in range(10) for _bar in range(4))
    topology = ResearchEvidenceTopology.for_dependency_groups(
        session_ids,
        forward_outcome_observations=2,
    )

    assert topology.boundary_embargo_observations == 2
    assert topology.eligible_event_window("discovery") == EvidenceWindow("discovery", 0, 22)
    assert topology.eligible_event_window("confirmation") == EvidenceWindow("confirmation", 24, 30)
    assert topology.event_partition_for(21) == "discovery"
    assert topology.validate_outcome_window(21, 23) == "discovery"
    assert topology.partition_for(22) == "discovery"
    assert topology.to_dict()["outcome_boundary_policy"] == {
        "forward_outcome_observations": 2,
        "right_boundary_embargo_observations": 2,
        "cross_boundary_outcomes": "REJECT",
    }
    with pytest.raises(DataError, match="crosses the discovery boundary"):
        topology.event_partition_for(22)
    with pytest.raises(DataError, match="crosses the confirmation boundary"):
        topology.validate_outcome_window(30, 32)


def test_outcome_window_cannot_exceed_registered_horizon() -> None:
    topology = ResearchEvidenceTopology.for_observations(
        20,
        forward_outcome_observations=2,
    )

    with pytest.raises(DataError, match="exceeds the registered forward outcome horizon"):
        topology.validate_outcome_window(1, 4)

    with pytest.raises(DataError, match="leaves no eligible event observations"):
        ResearchEvidenceTopology.for_observations(5, forward_outcome_observations=1)

    with pytest.raises(DataError, match="non-negative integer"):
        ResearchEvidenceTopology.for_observations(
            20,
            forward_outcome_observations=True,
        )


def test_grouping_and_embargo_are_bound_into_topology_hash() -> None:
    observation_topology = ResearchEvidenceTopology.for_observations(40)
    grouped_topology = ResearchEvidenceTopology.for_dependency_groups(
        tuple(f"session-{session}" for session in range(10) for _bar in range(4)),
        forward_outcome_observations=0,
    )
    embargoed_topology = ResearchEvidenceTopology.for_dependency_groups(
        tuple(f"session-{session}" for session in range(10) for _bar in range(4)),
        forward_outcome_observations=1,
    )

    assert observation_topology.contract_hash != grouped_topology.contract_hash
    assert grouped_topology.contract_hash != embargoed_topology.contract_hash


def test_dependency_group_value_and_sequence_validation_fail_closed() -> None:
    with pytest.raises(DataError, match="non-empty string"):
        EvidenceDependencyGroup("", 0, 1)
    with pytest.raises(DataError, match="indices must be integers"):
        EvidenceDependencyGroup("day-1", True, 1)
    with pytest.raises(DataError, match="start < stop"):
        EvidenceDependencyGroup("day-1", 1, 1)
    with pytest.raises(DataError, match="non-empty ordered sequence"):
        ResearchEvidenceTopology.for_dependency_groups(
            "day-1",
            forward_outcome_observations=0,
        )
    with pytest.raises(DataError, match="non-empty strings"):
        ResearchEvidenceTopology.for_dependency_groups(
            ("day-1", "day-2", "", "day-4", "day-5"),
            forward_outcome_observations=0,
        )


def test_manual_dependency_group_contract_rejects_every_structural_mismatch() -> None:
    windows = (
        EvidenceWindow("discovery", 0, 3),
        EvidenceWindow("confirmation", 3, 4),
        EvidenceWindow("final_holdout", 4, 5),
    )

    def build(groups: object) -> ResearchEvidenceTopology:
        return ResearchEvidenceTopology(
            5,
            *windows,
            dependency_groups=groups,  # type: ignore[arg-type]
        )

    with pytest.raises(DataError, match="immutable tuple"):
        build([])
    with pytest.raises(DataError, match="at least 5 dependency groups"):
        build((EvidenceDependencyGroup("one", 0, 5),))
    with pytest.raises(DataError, match="unsupported value"):
        build((1, 2, 3, 4, 5))
    with pytest.raises(DataError, match="contiguously"):
        build(
            tuple(
                EvidenceDependencyGroup(f"day-{index}", index + 1, index + 2) for index in range(5)
            )
        )
    with pytest.raises(DataError, match="unique and ordered"):
        build(tuple(EvidenceDependencyGroup("duplicate", index, index + 1) for index in range(5)))
    with pytest.raises(DataError, match="cover every observation"):
        build(
            tuple(EvidenceDependencyGroup(f"day-{index}", index, index + 1) for index in range(4))
            + (EvidenceDependencyGroup("day-4", 4, 6),)
        )


def test_topology_rejects_unknown_phase_and_backward_outcome() -> None:
    topology = ResearchEvidenceTopology.for_observations(
        20,
        forward_outcome_observations=2,
    )
    with pytest.raises(DataError, match="unsupported evidence phase"):
        topology.eligible_event_window("other")  # type: ignore[arg-type]
    with pytest.raises(DataError, match="cannot precede"):
        topology.validate_outcome_window(2, 1)


def test_size_skewed_groups_cannot_starve_the_final_holdout() -> None:
    """Group-count cuts with skewed group sizes must not leave a token holdout."""
    keys = ["g1"] * 40 + ["g2", "g3", "g4", "g5", "g6"]
    with pytest.raises(DataError, match="final holdout"):
        ResearchEvidenceTopology.for_dependency_groups(
            keys,
            forward_outcome_observations=0,
        )
