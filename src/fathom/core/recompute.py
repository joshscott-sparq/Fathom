"""Interactive recompute (spec §5.5 deal-shaping).

Given an existing Solution Graph and a set of knob overrides (AI boost, team
allocation, velocity, location mix), recompute velocity, duration, cost, and the
Monte Carlo distribution without re-matching or re-sizing. This powers the
UI sliders: work breakdown is held fixed, the levers move the numbers.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from ..models.results import DeterministicResult, MonteCarloResult
from ..models.solution_graph import SolutionGraph
from . import montecarlo
from .velocity import team_velocity

_PM = "Project & Program Management"


def _leaves(graph: SolutionGraph):
    parents = {wi.parent_id for wi in graph.work_items if wi.parent_id}
    return [wi for wi in graph.work_items if wi.id not in parents]


class RecomputeOverrides(BaseModel):
    ai_boost: float | None = Field(default=None, ge=0.0, le=1.0)
    avg_story_pts: float | None = Field(default=None, gt=0.0)
    engineer_count: int | None = Field(default=None, ge=1)
    allocations: dict[str, float] | None = Field(
        default=None, description="discipline -> allocated headcount override."
    )


def recompute(graph: SolutionGraph, overrides: RecomputeOverrides, iterations: int = 10_000) -> SolutionGraph:
    """Return the graph with team/cost/results recomputed under the overrides."""
    variables = graph.variables.model_copy()
    if overrides.avg_story_pts is not None:
        variables.avg_story_pts = overrides.avg_story_pts

    # Apply per-discipline allocation overrides first.
    team = graph.team_plan.model_copy(deep=True)
    if overrides.allocations:
        for role in team.roles:
            if role.discipline in overrides.allocations:
                role.allocated = overrides.allocations[role.discipline]

    eng_roles = [r for r in team.roles if r.discipline != _PM]
    base_engineers = sum(r.allocated for r in eng_roles) or float(len(eng_roles)) or 1.0

    # engineer_count scales the engineering headcount so monthly cost grows with
    # team size (not just velocity). PM roles are left unchanged.
    if overrides.engineer_count is not None and base_engineers > 0:
        factor = overrides.engineer_count / base_engineers
        for role in eng_roles:
            role.allocated *= factor
        engineers = float(overrides.engineer_count)
    else:
        engineers = base_engineers

    ai_boost = overrides.ai_boost if overrides.ai_boost is not None else 0.0

    # Velocity carries diminishing returns and the estimate's complexity impact (§2.3).
    from .factors import complexity_impact, risk_sigma

    leaves = _leaves(graph)
    cx_impact = complexity_impact(graph.complexity_factors, variables.avg_story_pts)
    velocity = team_velocity(variables.avg_story_pts, engineers, ai_boost, cx_impact)

    bottom_up = sum(montecarlo.deterministic_pert(wi.points, variables) for wi in leaves)
    effort_base = graph.deterministic.total_points if graph.deterministic else bottom_up
    duration_sprints = effort_base / velocity if velocity else 0.0
    duration_months = duration_sprints * variables.weeks_in_sprint / 4.345

    monthly = sum(r.day_rate * r.allocated * variables.working_month_days for r in team.roles)
    total_cost = round(monthly * duration_months, 2)
    team.monthly_cost = round(monthly, 2)
    team.total_cost = total_cost

    sigma = risk_sigma(graph.complexity_factors, graph.reconciliation.delta_pct if graph.reconciliation else 0.0)
    point_samples, _ = montecarlo.simulate_points([wi.points for wi in leaves], iterations, systemic_sigma=sigma)
    if bottom_up and effort_base:
        point_samples = point_samples * (effort_base / bottom_up)  # center on the working number
    effort_pct = montecarlo.derive_percentiles(point_samples)
    duration_samples = point_samples / velocity if velocity else np.zeros_like(point_samples)
    cost_per_point = (total_cost / effort_base) if effort_base else 0.0
    cost_samples = point_samples * cost_per_point

    updated = graph.model_copy(deep=True)
    updated.variables = variables
    updated.team_plan = team
    updated.deterministic = DeterministicResult(
        total_points=round(effort_base, 2),
        total_cost=total_cost,
        per_phase_velocity={"single-phase": velocity},
    )
    updated.monte_carlo = MonteCarloResult(
        iterations=iterations,
        effort_points=effort_pct,
        duration_sprints=montecarlo.derive_percentiles(duration_samples),
        cost=montecarlo.derive_percentiles(cost_samples),
    )
    return updated
