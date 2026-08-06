"""Scenario computation: evaluate staffing/development models (spec §5.5).

Applies a scenario's assumptions (development model -> AI boost + scope
automation; location mix -> blended rates; team size) to the estimate's fixed
work breakdown, producing effort, duration, and cost so alternatives compare
side by side. The work breakdown is invariant across scenarios; only the levers
move.
"""

from __future__ import annotations

import numpy as np

from ..models.scenario import Scenario, ScenarioResult
from ..models.solution_graph import SolutionGraph
from ..models.variables import Variables
from ..models.work_item import ThreePoint
from . import montecarlo
from .rates import RateCard
from .velocity import team_velocity

_PM = "Project & Program Management"
_WEEKS_PER_MONTH = 4.345


def _scaled(tp: ThreePoint, mult: float) -> ThreePoint:
    return ThreePoint(
        realistic=tp.realistic * mult,
        optimistic=None if tp.optimistic is None else tp.optimistic * mult,
        pessimistic=None if tp.pessimistic is None else tp.pessimistic * mult,
    )


def default_scenarios() -> list[Scenario]:
    """Preset scenarios spanning the AI Tier ladder and location (§5.5 examples).

    Data-driven from the AI Tiers library (add/reorder a tier without a code
    change): one US scenario per tier, plus Nearshore and 50/50-blend variants
    of the top tier so location tradeoffs stay visible at the highest leverage.
    """
    from .. import data_loader

    models, _ = data_loader.load_dev_models()
    tiers = sorted(models.items(), key=lambda kv: kv[1].get("tier", 0))
    if not tiers:
        return []

    scenarios = [
        Scenario(id=f"{key}-us", name=f"{m['name']} · US", dev_model=key, location_mix={"US": 1.0})
        for key, m in tiers
    ]
    top_key, top_m = tiers[-1]
    scenarios.append(Scenario(id=f"{top_key}-ns", name=f"{top_m['name']} · Nearshore", dev_model=top_key, location_mix={"NS": 1.0}))
    scenarios.append(Scenario(id=f"{top_key}-blend", name=f"{top_m['name']} · 50/50 blend", dev_model=top_key, location_mix={"US": 0.5, "NS": 0.5}))
    return scenarios


def compute_scenario(
    graph: SolutionGraph,
    scenario: Scenario,
    card: RateCard,
    dev_models: dict[str, dict],
    variables: Variables | None = None,
    iterations: int = 10_000,
) -> ScenarioResult:
    variables = variables or graph.variables
    dm = dev_models.get(scenario.dev_model) or dev_models.get("tier-1", {})
    ai_boost = float(dm.get("ai_boost", 0.0))
    effort_mult = float(dm.get("effort_multiplier", 1.0))

    from .factors import complexity_impact, risk_sigma

    parents = {wi.parent_id for wi in graph.work_items if wi.parent_id}
    leaves = [wi for wi in graph.work_items if wi.id not in parents]
    scaled = [_scaled(wi.points, effort_mult) for wi in leaves]
    bottom_up = sum(montecarlo.deterministic_pert(tp, variables) for tp in scaled)

    roles = graph.team_plan.roles
    eng_roles = [r for r in roles if r.discipline != _PM]
    base_eng = sum(r.allocated for r in eng_roles) or float(len(eng_roles)) or 1.0
    engineers = float(scenario.engineers) if scenario.engineers else base_eng
    factor = engineers / base_eng if base_eng else 1.0

    cx_impact = complexity_impact(graph.complexity_factors, variables.avg_story_pts)
    velocity = team_velocity(variables.avg_story_pts, engineers, ai_boost, cx_impact)
    duration_sprints = bottom_up / velocity if velocity else 0.0
    duration_months = duration_sprints * variables.weeks_in_sprint / _WEEKS_PER_MONTH

    monthly = 0.0
    for role in roles:
        alloc = role.allocated * (factor if role.discipline != _PM else 1.0)
        rate = card.blended_rate(role.discipline, role.tier, scenario.location_mix)
        monthly += rate * alloc * variables.working_month_days
    total_cost = round(monthly * duration_months, 2)

    sigma = risk_sigma(graph.complexity_factors, graph.reconciliation.delta_pct if graph.reconciliation else 0.0)
    samples, effort_pct = montecarlo.simulate_points(scaled, iterations, systemic_sigma=sigma)
    duration_samples = samples / velocity if velocity else np.zeros_like(samples)
    cost_per_point = (total_cost / bottom_up) if bottom_up else 0.0
    cost_samples = samples * cost_per_point

    mix_label = ", ".join(f"{k} {round(v * 100)}%" for k, v in scenario.location_mix.items())
    assumptions = list(dm.get("assumptions", [])) + [
        f"Location mix: {mix_label}.",
        f"Team: {round(engineers)} engineers (sub-linear velocity).",
    ]

    return ScenarioResult(
        scenario=scenario,
        assumptions=assumptions,
        effort_points=effort_pct,
        duration_sprints=montecarlo.derive_percentiles(duration_samples),
        cost=montecarlo.derive_percentiles(cost_samples),
        monthly_cost=round(monthly, 2),
        total_cost=total_cost,
    )


def compute_scenarios(
    graph: SolutionGraph,
    scenarios: list[Scenario],
    card: RateCard,
    dev_models: dict[str, dict],
    iterations: int = 10_000,
) -> list[ScenarioResult]:
    return [compute_scenario(graph, s, card, dev_models, iterations=iterations) for s in scenarios]
