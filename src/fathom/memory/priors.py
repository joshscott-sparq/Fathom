"""Pattern-prior calibration (spec §4.4, the moat).

The write side of memory. Past estimates and, when available, delivery actuals
refine a pattern's parametric base effort via reference-class forecasting with
shrinkage: with few samples the library value dominates; as engagements
accumulate, the observed reference class takes over. This is the real
implementation of the PatternPrior extension point (DECISIONS.md D9).

Actuals ingestion (`ActualOutcome`) is the interface for the Phase 4 calibration
loop (Salesforce closed-won + delivery burn); recording an outcome makes it the
preferred signal over the estimate's own bottom-up number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.pattern import ParametricCost
from ..persistence.store import StoredEstimate

# Shrinkage weight: equivalent number of "library" observations. Higher = trust
# the seeded value longer before the observed reference class dominates.
PRIOR_STRENGTH = 3.0


@dataclass
class ActualOutcome:
    """Delivered results for a completed engagement (§4.4 actuals ingestion)."""

    estimate_id: str
    delivered_points: float | None = None
    delivered_cost: float | None = None
    delivered_sprints: float | None = None
    notes: str = ""


@dataclass
class TunedPrior:
    pattern_id: str
    library_base: float
    observed_base: float | None
    tuned_base: float
    sample_count: int
    used_actuals: int
    contributing_estimate_ids: list[str] = field(default_factory=list)

    def as_parametric(self, library: ParametricCost) -> ParametricCost:
        """Return a ParametricCost with the tuned base, keeping library drivers."""
        return ParametricCost(
            base_effort_points=round(self.tuned_base, 2),
            scaling_drivers=dict(library.scaling_drivers),
            risk_factor_families=list(library.risk_factor_families),
        )


def _observed_base(
    pattern_id: str,
    past: list[StoredEstimate],
    actuals: dict[str, ActualOutcome],
) -> tuple[float | None, int, int, list[str]]:
    """Mean realized base for a pattern. Prefers actuals; falls back to bottom-up."""
    values: list[float] = []
    used_actuals = 0
    contributors: list[str] = []
    for stored in past:
        if pattern_id not in stored.graph.matched_pattern_ids:
            continue
        outcome = actuals.get(stored.estimate_id)
        if outcome and outcome.delivered_points is not None:
            values.append(outcome.delivered_points)
            used_actuals += 1
            contributors.append(stored.estimate_id)
        elif stored.graph.deterministic is not None:
            values.append(stored.graph.deterministic.total_points)
            contributors.append(stored.estimate_id)
    if not values:
        return None, 0, 0, []
    return sum(values) / len(values), len(values), used_actuals, contributors


def tune_pattern_prior(
    pattern_id: str,
    library: ParametricCost,
    past: list[StoredEstimate],
    actuals: dict[str, ActualOutcome] | None = None,
    prior_strength: float = PRIOR_STRENGTH,
) -> TunedPrior:
    """Shrinkage blend of the library base and the observed reference class.

    tuned = (strength * library + n * observed) / (strength + n)
    """
    actuals = actuals or {}
    observed, n, used_actuals, contributors = _observed_base(pattern_id, past, actuals)

    if observed is None:
        tuned = library.base_effort_points
    else:
        tuned = (prior_strength * library.base_effort_points + n * observed) / (prior_strength + n)

    return TunedPrior(
        pattern_id=pattern_id,
        library_base=library.base_effort_points,
        observed_base=observed,
        tuned_base=tuned,
        sample_count=n,
        used_actuals=used_actuals,
        contributing_estimate_ids=contributors,
    )
