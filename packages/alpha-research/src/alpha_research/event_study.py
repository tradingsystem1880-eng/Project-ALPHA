"""Point-in-time-valid predictive event-study observations and inference."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from alpha_core import DataError

CovariateScalar = str | int | float | bool
_PREDICTIVE_CAVEAT = "Conditional predictive association; not a causal effect."


def _nonempty(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"{name} must be a non-empty string")
    return value


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"{name} must be timezone-aware")


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _overlaps(left: EventStudyObservation, right: EventStudyObservation) -> bool:
    return (
        left.outcome_start_at < right.outcome_end_at
        and right.outcome_start_at < left.outcome_end_at
    )


@dataclass(frozen=True, slots=True)
class PreEventCovariate:
    """One declared matching value with its observation and knowledge timestamps."""

    name: str
    value: CovariateScalar
    observed_at: datetime
    available_at: datetime

    def __post_init__(self) -> None:
        _nonempty("PreEventCovariate.name", self.name)
        for name in ("observed_at", "available_at"):
            _aware(f"PreEventCovariate.{name}", getattr(self, name))
        if self.available_at < self.observed_at:
            raise DataError("covariate availability cannot precede its observation timestamp")
        if isinstance(self.value, str):
            _nonempty("PreEventCovariate.value", self.value)
        elif isinstance(self.value, float):
            if not math.isfinite(self.value):
                raise DataError("PreEventCovariate.value must be finite")
        elif not isinstance(self.value, int | bool):
            raise DataError("PreEventCovariate.value must be a scalar string, number, or boolean")

    @property
    def matching_key(self) -> tuple[str, str]:
        """Return a type-stable exact-match key (``True`` never aliases integer ``1``)."""
        if isinstance(self.value, bool):
            return ("bool", "true" if self.value else "false")
        if isinstance(self.value, int):
            return ("int", str(self.value))
        if isinstance(self.value, float):
            return ("float", format(self.value, ".17g"))
        return ("str", self.value)


@dataclass(frozen=True, slots=True)
class EventStudyObservation:
    """One event or pseudo-event whose forward outcome has an explicit knowledge time."""

    observation_id: str
    is_event: bool
    event_at: datetime
    event_available_at: datetime
    outcome_start_at: datetime
    outcome_end_at: datetime
    outcome_available_at: datetime
    outcome: float
    cluster_id: str
    covariates: tuple[PreEventCovariate, ...]

    def __post_init__(self) -> None:
        _nonempty("EventStudyObservation.observation_id", self.observation_id)
        _nonempty("EventStudyObservation.cluster_id", self.cluster_id)
        if not isinstance(self.is_event, bool):
            raise DataError("EventStudyObservation.is_event must be boolean")
        for name in (
            "event_at",
            "event_available_at",
            "outcome_start_at",
            "outcome_end_at",
            "outcome_available_at",
        ):
            _aware(f"EventStudyObservation.{name}", getattr(self, name))
        if self.event_available_at < self.event_at:
            raise DataError("event availability cannot precede the registered event timestamp")
        if self.outcome_start_at < self.event_available_at:
            raise DataError("outcome start cannot precede event availability")
        if self.outcome_end_at <= self.outcome_start_at:
            raise DataError("outcome end must occur after outcome start")
        if self.outcome_available_at < self.outcome_end_at:
            raise DataError("outcome availability cannot precede the outcome end")
        if not math.isfinite(self.outcome):
            raise DataError("EventStudyObservation.outcome must be finite")
        if not isinstance(self.covariates, tuple):
            raise DataError("EventStudyObservation.covariates must be an immutable tuple")
        names = [item.name for item in self.covariates]
        if len(names) != len(set(names)):
            raise DataError("EventStudyObservation covariate names must be unique")
        if any(item.available_at > self.event_at for item in self.covariates):
            raise DataError("all matching covariates must be available pre-event")

    def covariate_key(self, names: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
        by_name = {item.name: item for item in self.covariates}
        missing = [name for name in names if name not in by_name]
        if missing:
            raise DataError(
                f"observation {self.observation_id!r} lacks declared covariate(s): "
                + ", ".join(missing)
            )
        return tuple(by_name[name].matching_key for name in names)


@dataclass(frozen=True, slots=True)
class PurgedEventStudy:
    observations: tuple[EventStudyObservation, ...]
    dropped_observation_ids: tuple[str, ...]
    effective_event_count: int


def purge_overlapping_outcomes(
    observations: tuple[EventStudyObservation, ...],
) -> PurgedEventStudy:
    """Greedily keep the first available event when registered outcome windows overlap."""
    if not isinstance(observations, tuple):
        raise DataError("event-study observations must be an immutable tuple")
    if any(not item.is_event for item in observations):
        raise DataError("overlap purging accepts event observations only")
    ids = [item.observation_id for item in observations]
    if len(ids) != len(set(ids)):
        raise DataError("event-study observation IDs must be unique")
    ordered = sorted(
        observations,
        key=lambda item: (
            _utc(item.event_available_at),
            _utc(item.outcome_start_at),
            item.observation_id,
        ),
    )
    kept: list[EventStudyObservation] = []
    dropped: list[str] = []
    for observation in ordered:
        if any(_overlaps(prior, observation) for prior in kept):
            dropped.append(observation.observation_id)
            continue
        kept.append(observation)
    return PurgedEventStudy(
        observations=tuple(kept),
        dropped_observation_ids=tuple(dropped),
        effective_event_count=len({item.cluster_id for item in kept}),
    )


@dataclass(frozen=True, slots=True)
class MatchedEventControlPair:
    event: EventStudyObservation
    control: EventStudyObservation
    covariate_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.event.is_event or self.control.is_event:
            raise DataError("a matched pair requires one event and one non-event control")
        if self.event.covariate_key(self.covariate_names) != self.control.covariate_key(
            self.covariate_names
        ):
            raise DataError("matched event and control covariates must agree exactly")
        if _overlaps(self.event, self.control):
            raise DataError("matched event and control outcome windows cannot overlap")

    @property
    def difference(self) -> float:
        return self.event.outcome - self.control.outcome


@dataclass(frozen=True, slots=True)
class MatchedEventStudy:
    as_of: datetime
    covariate_names: tuple[str, ...]
    pairs: tuple[MatchedEventControlPair, ...]
    unmatched_event_ids: tuple[str, ...]
    dropped_overlap_event_ids: tuple[str, ...]
    not_yet_available_count: int

    @property
    def effective_event_count(self) -> int:
        return len({pair.event.cluster_id for pair in self.pairs})


def _validate_as_of(as_of: datetime) -> None:
    _aware("event-study as_of", as_of)


def _known_as_of(
    observations: tuple[EventStudyObservation, ...], as_of: datetime
) -> tuple[EventStudyObservation, ...]:
    cutoff = _utc(as_of)
    return tuple(
        item
        for item in observations
        if _utc(item.event_available_at) <= cutoff and _utc(item.outcome_available_at) <= cutoff
    )


def _validate_covariate_names(names: tuple[str, ...]) -> None:
    if not isinstance(names, tuple) or not names:
        raise DataError("matched controls require a non-empty frozen covariate tuple")
    for name in names:
        _nonempty("declared covariate name", name)
    if len(names) != len(set(names)):
        raise DataError("declared covariate names must be unique")


def match_event_controls(
    observations: tuple[EventStudyObservation, ...],
    *,
    covariate_names: tuple[str, ...],
    as_of: datetime,
) -> MatchedEventStudy:
    """Exactly match controls on frozen pre-event covariates without replacement.

    Among exact matches, the nearest event timestamp wins and ``observation_id`` breaks ties. This
    is deliberately not propensity-score matching and does not support post-event covariates.
    """
    if not isinstance(observations, tuple) or not observations:
        raise DataError("matching requires a non-empty immutable observation tuple")
    _validate_as_of(as_of)
    _validate_covariate_names(covariate_names)
    ids = [item.observation_id for item in observations]
    if len(ids) != len(set(ids)):
        raise DataError("event-study observation IDs must be unique")
    known = _known_as_of(observations, as_of)
    for item in known:
        item.covariate_key(covariate_names)
    events = tuple(item for item in known if item.is_event)
    controls = tuple(item for item in known if not item.is_event)
    if not events:
        raise DataError("matching requires at least one outcome-available event")
    if not controls:
        raise DataError("matching requires at least one outcome-available control")
    purged = purge_overlapping_outcomes(events)
    remaining = {item.observation_id: item for item in controls}
    selected_controls: list[EventStudyObservation] = []
    pairs: list[MatchedEventControlPair] = []
    unmatched: list[str] = []
    for event in purged.observations:
        event_key = event.covariate_key(covariate_names)
        candidates = [
            control
            for control in remaining.values()
            if control.covariate_key(covariate_names) == event_key
            and not any(_overlaps(control, registered) for registered in purged.observations)
            and not any(_overlaps(control, selected) for selected in selected_controls)
        ]
        if not candidates:
            unmatched.append(event.observation_id)
            continue
        control = min(
            candidates,
            key=lambda item: (
                abs((_utc(item.event_at) - _utc(event.event_at)).total_seconds()),
                item.observation_id,
            ),
        )
        remaining.pop(control.observation_id)
        selected_controls.append(control)
        pairs.append(MatchedEventControlPair(event, control, covariate_names))
    return MatchedEventStudy(
        as_of=_utc(as_of),
        covariate_names=covariate_names,
        pairs=tuple(pairs),
        unmatched_event_ids=tuple(unmatched),
        dropped_overlap_event_ids=purged.dropped_observation_ids,
        not_yet_available_count=len(observations) - len(known),
    )


@dataclass(frozen=True, slots=True)
class PredictiveAssociationEstimate:
    """Percentile cluster-bootstrap interval plus a centered-bootstrap two-sided p-value."""

    as_of: datetime
    estimate: float
    standard_error: float
    ci_lower: float
    ci_upper: float
    p_value: float
    confidence: float
    sample_size: int
    effective_event_count: int
    dropped_overlap_count: int
    not_yet_available_count: int
    n_resamples: int
    seed: int
    method: str = "cluster_bootstrap_predictive_mean"
    caveat: str = _PREDICTIVE_CAVEAT


def _cluster_bootstrap_predictive_mean(
    values: tuple[float, ...],
    cluster_ids: tuple[str, ...],
    *,
    confidence: float,
    n_resamples: int,
    seed: int,
) -> tuple[float, float, float, float, float, int]:
    if len(values) != len(cluster_ids) or not values:
        raise DataError("cluster bootstrap requires aligned non-empty values and cluster IDs")
    if any(not math.isfinite(value) for value in values):
        raise DataError("cluster-bootstrap values must be finite")
    if not math.isfinite(confidence) or not 0.5 < confidence < 1.0:
        raise DataError("cluster-bootstrap confidence must be finite in (0.5, 1)")
    if isinstance(n_resamples, bool) or not isinstance(n_resamples, int) or n_resamples < 100:
        raise DataError("cluster-bootstrap n_resamples must be an integer >= 100")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise DataError("cluster-bootstrap seed must be a non-negative integer")
    ordered_clusters = sorted(set(cluster_ids))
    if len(ordered_clusters) < 2:
        raise DataError("cluster bootstrap requires at least two effective event clusters")
    arrays = [
        np.asarray(
            [
                value
                for value, cluster_id in zip(values, cluster_ids, strict=True)
                if cluster_id == key
            ],
            dtype=np.float64,
        )
        for key in ordered_clusters
    ]
    sums = np.asarray([float(array.sum()) for array in arrays], dtype=np.float64)
    sizes = np.asarray([array.size for array in arrays], dtype=np.int64)
    estimate = float(np.mean(np.asarray(values, dtype=np.float64)))
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(arrays), size=(n_resamples, len(arrays)))
    bootstrap_means = sums[draws].sum(axis=1) / sizes[draws].sum(axis=1)
    alpha_tail = (1.0 - confidence) / 2.0
    ci_lower, ci_upper = np.quantile(
        bootstrap_means,
        (alpha_tail, 1.0 - alpha_tail),
        method="linear",
    )
    centered_sums = sums - estimate * sizes
    null_means = centered_sums[draws].sum(axis=1) / sizes[draws].sum(axis=1)
    p_value = (float(np.count_nonzero(np.abs(null_means) >= abs(estimate))) + 1.0) / (
        n_resamples + 1.0
    )
    standard_error = float(np.std(bootstrap_means, ddof=1))
    return (
        estimate,
        standard_error,
        float(ci_lower),
        float(ci_upper),
        p_value,
        len(ordered_clusters),
    )


def evaluate_event_association(
    observations: tuple[EventStudyObservation, ...],
    *,
    as_of: datetime,
    confidence: float = 0.95,
    n_resamples: int = 2_000,
    seed: int = 7,
) -> PredictiveAssociationEstimate:
    """Estimate the event-outcome mean using only outcomes known at ``as_of``."""
    if not isinstance(observations, tuple) or not observations:
        raise DataError("event association requires a non-empty immutable observation tuple")
    if any(not item.is_event for item in observations):
        raise DataError("unadjusted event association accepts event observations only")
    _validate_as_of(as_of)
    known = _known_as_of(observations, as_of)
    purged = purge_overlapping_outcomes(known)
    values = tuple(item.outcome for item in purged.observations)
    clusters = tuple(item.cluster_id for item in purged.observations)
    estimate, standard_error, lower, upper, p_value, effective = _cluster_bootstrap_predictive_mean(
        values,
        clusters,
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
    )
    return PredictiveAssociationEstimate(
        as_of=_utc(as_of),
        estimate=estimate,
        standard_error=standard_error,
        ci_lower=lower,
        ci_upper=upper,
        p_value=p_value,
        confidence=confidence,
        sample_size=len(values),
        effective_event_count=effective,
        dropped_overlap_count=len(purged.dropped_observation_ids),
        not_yet_available_count=len(observations) - len(known),
        n_resamples=n_resamples,
        seed=seed,
    )


def evaluate_matched_association(
    matched: MatchedEventStudy,
    *,
    confidence: float = 0.95,
    n_resamples: int = 2_000,
    seed: int = 7,
) -> PredictiveAssociationEstimate:
    """Estimate paired event-minus-control outcomes with event-cluster resampling."""
    if not matched.pairs:
        raise DataError("matched association requires at least one matched pair")
    values = tuple(pair.difference for pair in matched.pairs)
    clusters = tuple(pair.event.cluster_id for pair in matched.pairs)
    estimate, standard_error, lower, upper, p_value, effective = _cluster_bootstrap_predictive_mean(
        values,
        clusters,
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
    )
    return PredictiveAssociationEstimate(
        as_of=matched.as_of,
        estimate=estimate,
        standard_error=standard_error,
        ci_lower=lower,
        ci_upper=upper,
        p_value=p_value,
        confidence=confidence,
        sample_size=len(values),
        effective_event_count=effective,
        dropped_overlap_count=len(matched.dropped_overlap_event_ids),
        not_yet_available_count=matched.not_yet_available_count,
        n_resamples=n_resamples,
        seed=seed,
    )
