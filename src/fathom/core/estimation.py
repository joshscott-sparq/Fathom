"""Estimation core: build a Solution Graph and estimate it (spec §4.1-4.2, §2 calibration).

Skeleton depth (DECISIONS.md D9 build sequence): the graph is assembled from a
matched pattern with deterministic sizing, so the full vertical slice runs offline.
Requirement/capability derivation and per-item sizing are marked skeleton-level and
get replaced by LLM reasoning as the engine deepens. The estimation math
(PERT, PERT-beta Monte Carlo, top-down vs bottom-up reconciliation, cost) is real.
"""

from __future__ import annotations

import re

import numpy as np

from .. import data_loader
from ..models.graph import (
    Capability,
    Component,
    ComponentType,
    Edge,
    EdgeKind,
    Provenance,
    Requirement,
    RequirementKind,
)
from ..models.pattern import ParametricCost, Pattern
from ..models.context import ContextPanel as _ContextPanel
from ..models.results import (
    ClientContext,
    DataVersions,
    DeterministicResult,
    MonteCarloResult,
    ReconciliationResult,
)
from ..models.solution_graph import SolutionGraph
from ..models.team import Location, RateRow, Role, TeamPlan
from ..models.variables import Variables
from ..models.work_item import CureAssessment, ThreePoint, WorkItem, WorkLevel
from . import montecarlo
from .factors import complexity_impact, derive_factors, risk_sigma
from .matcher import PatternMatch, score_patterns
from .velocity import team_velocity

SIZE_ORDER = ["XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]

# Skeleton default feature-scale size per component type (deterministic sizing).
_TYPE_SIZE = {
    ComponentType.DATASTORE: "S",
    ComponentType.SERVICE: "M",
    ComponentType.PIPELINE: "L",
    ComponentType.ML_MODEL: "L",
    ComponentType.UI: "M",
    ComponentType.GATEWAY: "M",
    ComponentType.QUEUE: "S",
    ComponentType.INTEGRATION: "M",
    ComponentType.EXTERNAL_SYSTEM: "XS",
}

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def extract_requirements(prd_text: str, max_items: int = 60) -> list[Requirement]:
    """Skeleton extraction: bullet/sentence lines become requirements (§3.1).

    Confidence is fixed-low to reflect naive extraction; the LLM ingest step
    replaces this and sets real per-item confidence.
    """
    requirements: list[Requirement] = []
    for line in prd_text.splitlines():
        stripped = _BULLET.sub("", line).strip()
        if len(stripped) < 10:
            continue
        requirements.append(
            Requirement(
                id=f"req-{len(requirements) + 1}",
                text=stripped[:300],
                kind=RequirementKind.FUNCTIONAL,
                extraction_confidence=0.5,
            )
        )
        if len(requirements) >= max_items:
            break
    return requirements


def _three_point(realistic: float, confidence: float) -> ThreePoint:
    """Confidence-driven 3-point estimate (§3.2).

    Low confidence widens the optimistic/pessimistic bands; the pessimistic side
    widens faster (estimates skew optimistic). At full confidence the bands are
    tight (~0.85x / 1.25x); at zero confidence they are wide (~0.5x / 2.1x).
    """
    u = 1.0 - max(0.0, min(1.0, confidence))
    optimistic = realistic * (1.0 - (0.15 + 0.35 * u))
    pessimistic = realistic * (1.0 + (0.25 + 0.85 * u))
    return ThreePoint(realistic=realistic, optimistic=round(optimistic, 2), pessimistic=round(pessimistic, 2))


def _leaf_work_items(work_items: list[WorkItem]) -> list[WorkItem]:
    """Work items with no children — the ones effort rolls up from."""
    parents = {wi.parent_id for wi in work_items if wi.parent_id}
    return [wi for wi in work_items if wi.id not in parents]


def _decompose(work_items: list[WorkItem], edges: list[Edge], variables: Variables,
               threshold: float = 20.0) -> None:
    """Split large feature work items into stories (decompose gate, §3.3).

    Any feature whose realistic size is at/above the L feature-scale threshold is
    broken into evenly-sized story children (parent kept for the Gantt hierarchy).
    Effort then rolls up from the finer stories. Mutates work_items/edges in place.
    """
    import math

    comp_by_wi = {e.target_id: e.source_id for e in edges if e.kind is EdgeKind.IMPLEMENTED_BY}
    new_items: list[WorkItem] = []
    new_edges: list[Edge] = []
    for wi in list(work_items):
        if wi.level is not WorkLevel.FEATURE or wi.points.realistic < threshold:
            continue
        k = max(2, math.ceil(wi.points.realistic / 12.5))  # ~ one feature-M per story
        share = 1.0 / k
        for s in range(1, k + 1):
            story = WorkItem(
                id=f"{wi.id}-s{s}", level=WorkLevel.STORY, epic=wi.epic, feature=wi.feature,
                story=f"{wi.feature} — part {s}", parent_id=wi.id,
                points=ThreePoint(
                    realistic=round(wi.points.realistic * share, 2),
                    optimistic=round(wi.points.effective_optimistic * share, 2),
                    pessimistic=round(wi.points.effective_pessimistic * share, 2),
                ),
                cure=wi.cure, discipline=wi.discipline, extraction_confidence=wi.extraction_confidence,
            )
            new_items.append(story)
            comp = comp_by_wi.get(wi.id)
            if comp:
                new_edges.append(Edge(source_id=comp, target_id=story.id, kind=EdgeKind.IMPLEMENTED_BY, confidence=0.5))
    work_items.extend(new_items)
    edges.extend(new_edges)


def _driver_quantities(components: list[Component], edges: list[Edge], context: ClientContext) -> dict[str, float]:
    """Derive parametric driver quantities from the graph and context (§4.2)."""
    integration_count = sum(
        1 for e in edges if e.kind in {EdgeKind.INTEGRATES_WITH, EdgeKind.DATA_FLOW}
    )
    return {
        "integration": float(integration_count),
        "data_source": float(max(1, len(context.tech_stack))),
        "environment": 2.0,  # skeleton default: staging + prod
        "extracted_service": float(sum(1 for c in components if c.component_type is ComponentType.SERVICE)),
        "tool_server": float(sum(1 for c in components if c.component_type is ComponentType.INTEGRATION)),
        "data_entity": float(sum(1 for c in components if c.component_type is ComponentType.DATASTORE)),
    }


def _instantiate_pattern(pattern: Pattern, feature_points: dict[str, dict]) -> tuple[
    list[Component], list[WorkItem], list[Edge]
]:
    """Seed components, work items, and component edges from a matched pattern.

    Capabilities are derived separately (LLM or heuristic) so they can be real
    higher-level capabilities rather than 1:1 with components.
    """
    components: list[Component] = []
    work_items: list[WorkItem] = []
    edges: list[Edge] = []
    name_to_component_id: dict[str, str] = {}

    for i, spec in enumerate(pattern.components, start=1):
        comp_id = f"cmp-{i}"
        name_to_component_id[spec.name] = comp_id
        components.append(
            Component(
                id=comp_id,
                name=spec.name,
                component_type=spec.component_type,
                technology=spec.technology,
                description=spec.description,
                provenance=Provenance.PATTERN,
                pattern_id=pattern.id,
                discipline=spec.discipline,
            )
        )

        # One feature-level work item per component, sized by type with
        # confidence-driven optimistic/pessimistic bands (§3.2).
        size = _TYPE_SIZE.get(spec.component_type, "M")
        confidence = 0.5
        realistic = feature_points[size]["feature"]
        work_items.append(
            WorkItem(
                id=f"wi-{i}",
                level=WorkLevel.FEATURE,
                epic=pattern.name,
                feature=spec.name,
                points=_three_point(realistic, confidence),
                cure=CureAssessment(
                    complexity=3, unknowns=3, risks=2, effort=3,
                    rationale=f"Sizing: {spec.component_type.value} default {size}.",
                    confidence=confidence,
                ),
                practice=None,
                discipline=spec.discipline,
                extraction_confidence=0.5,
            )
        )
        edges.append(Edge(source_id=comp_id, target_id=f"wi-{i}", kind=EdgeKind.IMPLEMENTED_BY, confidence=0.6))

    for spec in pattern.integrations:
        src = name_to_component_id.get(spec.source)
        dst = name_to_component_id.get(spec.target)
        if src and dst:
            edges.append(Edge(source_id=src, target_id=dst, kind=spec.kind, label=spec.label))

    return components, work_items, edges


def _capabilities_heuristic(
    components: list[Component], requirements: list[Requirement]
) -> tuple[list[Capability], list[Edge]]:
    """Fallback: one capability per component + token-overlap requirement links."""
    capabilities: list[Capability] = []
    edges: list[Edge] = []
    for i, comp in enumerate(components, start=1):
        cap = Capability(id=f"cap-{i}", name=comp.name, description=comp.description, provenance=Provenance.PATTERN)
        capabilities.append(cap)
        edges.append(Edge(source_id=cap.id, target_id=comp.id, kind=EdgeKind.REALIZED_BY, confidence=0.6))
    edges += _link_requirements(requirements, capabilities)
    return capabilities, edges


def _capabilities_llm(
    prd_text: str,
    requirements: list[Requirement],
    components: list[Component],
    client=None,
) -> tuple[list[Capability], list[Edge]]:
    """LLM-derived capabilities with requirement and component links."""
    from . import llm

    derived = llm.derive_capabilities(
        prd_text, [r.text for r in requirements], [c.name for c in components], client=client
    )
    capabilities = [
        Capability(id=f"cap-{i}", name=c["name"], description=c["description"], provenance=Provenance.INFERRED)
        for i, c in enumerate(derived["capabilities"], start=1)
    ]

    def cap_id(index) -> str | None:
        if isinstance(index, int) and 0 <= index < len(capabilities):
            return capabilities[index].id
        return None

    edges: list[Edge] = []
    req_links = derived.get("requirement_links", [])
    for req, idx in zip(requirements, req_links):
        cid = cap_id(idx)
        if cid:
            edges.append(Edge(source_id=req.id, target_id=cid, kind=EdgeKind.SATISFIED_BY, confidence=0.75))

    name_to_comp = {c.name: c for c in components}
    for comp_name, idx in derived.get("component_links", {}).items():
        comp = name_to_comp.get(comp_name)
        cid = cap_id(idx)
        if comp and cid:
            edges.append(Edge(source_id=cid, target_id=comp.id, kind=EdgeKind.REALIZED_BY, confidence=0.75))

    # Guarantee every component is realized by some capability (graph completeness).
    realized = {e.target_id for e in edges if e.kind is EdgeKind.REALIZED_BY}
    for comp in components:
        if comp.id not in realized and capabilities:
            edges.append(Edge(source_id=capabilities[0].id, target_id=comp.id, kind=EdgeKind.REALIZED_BY, confidence=0.4))
    return capabilities, edges


def _link_requirements(requirements: list[Requirement], capabilities: list[Capability]) -> list[Edge]:
    """Skeleton: link each requirement to the best token-overlap capability."""
    edges: list[Edge] = []
    cap_tokens = [(c, _tokens(c.name)) for c in capabilities]
    for req in requirements:
        rt = _tokens(req.text)
        best, best_overlap = None, 0
        for cap, ct in cap_tokens:
            overlap = len(rt & ct)
            if overlap > best_overlap:
                best, best_overlap = cap, overlap
        if best is None and capabilities:
            best = capabilities[0]
        if best is not None:
            edges.append(
                Edge(
                    source_id=req.id, target_id=best.id, kind=EdgeKind.SATISFIED_BY,
                    confidence=0.4 if best_overlap == 0 else 0.6,
                )
            )
    return edges


def _extract_requirements(prd_text: str, use_llm: bool, client) -> tuple[list[Requirement], str]:
    """LLM extraction with heuristic fallback (§3.1)."""
    if use_llm:
        try:
            from . import llm

            items = llm.extract_requirements(prd_text, client=client)
            reqs = [
                Requirement(
                    id=f"req-{i}", text=it["text"], kind=RequirementKind(it["kind"]),
                    extraction_confidence=it["confidence"],
                )
                for i, it in enumerate(items, start=1)
            ]
            if reqs:
                return reqs, "LLM"
        except Exception:
            pass
    return extract_requirements(prd_text), "heuristic"


def _rank_patterns(prd_text: str, context: ClientContext, patterns, use_llm: bool, client):
    """LLM pattern ranking with deterministic signal-overlap fallback (§3.3)."""
    if use_llm:
        try:
            from . import llm

            catalog = [{"id": p.id, "name": p.name, "when_to_use": p.when_to_use} for p in patterns.values()]
            matches = llm.rank_patterns(prd_text, context.tech_stack, catalog, client=client)
            ranked = [PatternMatch(m["pattern_id"], m["score"], m["rationale"]) for m in matches]
            if ranked:
                return ranked, "LLM"
        except Exception:
            pass
    return score_patterns(prd_text, context, patterns), "deterministic"


def _derive_capabilities(prd_text, requirements, components, use_llm, client):
    """LLM capability derivation with 1:1 heuristic fallback (§4.3)."""
    if use_llm:
        try:
            caps, edges = _capabilities_llm(prd_text, requirements, components, client)
            if caps:
                return caps, edges, "LLM"
        except Exception:
            pass
    caps, edges = _capabilities_heuristic(components, requirements)
    return caps, edges, "heuristic"


def _build_team(
    components: list[Component],
    rates: list[RateRow],
    context: ClientContext,
    variables: Variables,
) -> TeamPlan:
    """Skeleton team: one role per distinct discipline + PM, default Senior tier."""
    location = Location.US
    if context.us_ns_mix.get("NS", 0) > context.us_ns_mix.get("US", 0):
        location = Location.NS

    rate_index = {(r.discipline, r.tier, r.location): r.day_rate for r in rates}

    disciplines = {c.discipline for c in components if c.discipline}
    disciplines.add("Project & Program Management")

    roles: list[Role] = []
    for discipline in sorted(disciplines):
        tier = "Senior Lead" if discipline in {"Solutions Architect", "Project & Program Management"} else "Senior"
        day_rate = (
            rate_index.get((discipline, tier, location))
            or rate_index.get((discipline, tier, Location.US))
            or 0.0
        )
        roles.append(
            Role(
                discipline=discipline, tier=tier, location=location,
                suggested=1.0, allocated=1.0, day_rate=day_rate,
            )
        )

    monthly = sum(r.day_rate * variables.working_month_days for r in roles)
    plan = TeamPlan(roles=roles, monthly_cost=round(monthly, 2))
    return plan


def build_estimate(
    project_name: str,
    prd_text: str,
    context: ClientContext | None = None,
    iterations: int = 10_000,
    match_override: str | None = None,
    parametric_override: "ParametricCost | None" = None,
    rates: "list[RateRow] | None" = None,
    use_llm: bool | None = None,
    llm_client=None,
    context_panel=None,
) -> SolutionGraph:
    """Build and estimate a Solution Graph from a PRD + client context.

    When the LLM is available (API key set), requirement extraction, pattern
    matching, and capability derivation use Claude; each step falls back to a
    deterministic heuristic on absence or error, so the engine always runs.
    `use_llm` forces the choice; None auto-detects. `llm_client` is injectable
    for testing.
    """
    context = context or ClientContext()
    from . import llm

    use_llm = llm.available() if use_llm is None else use_llm

    feature_points, tshirt_v = data_loader.load_tshirt_scale()
    variables, vars_v = data_loader.load_variables()
    patterns, patterns_v = data_loader.load_patterns()
    if rates is None:
        rates, pricing_v, _ = data_loader.load_pricing()
    else:
        pricing_v = "custom-upload"
    _, complexity_v = data_loader.load_complexity_factors()
    _, practices_v = data_loader.load_practices()
    _, _, _, tiers_v = data_loader.load_tiers()

    assumptions: list[str] = []

    # --- Ingest: requirements (LLM with heuristic fallback, §3.1) ---
    requirements, ingest_mode = _extract_requirements(prd_text, use_llm, llm_client)

    # --- Match: rank patterns (LLM with deterministic fallback, §3.3) ---
    ranked, match_mode = _rank_patterns(prd_text, context, patterns, use_llm, llm_client)
    chosen_id = match_override or (ranked[0].pattern_id if ranked else None)
    pattern = patterns.get(chosen_id) if chosen_id else None
    if pattern is None:
        raise ValueError("No patterns available to match against.")
    top_match = next((m for m in ranked if m.pattern_id == chosen_id), ranked[0])
    assumptions.append(f"Matched pattern '{pattern.name}' ({top_match.rationale}) [{match_mode}].")
    assumptions.append(f"Requirements extracted via {ingest_mode}.")

    components, work_items, edges = _instantiate_pattern(pattern, feature_points)

    # --- Capabilities (LLM-derived with 1:1 heuristic fallback, §4.3) ---
    capabilities, cap_edges, cap_mode = _derive_capabilities(prd_text, requirements, components, use_llm, llm_client)
    edges += cap_edges
    assumptions.append(f"Capabilities derived via {cap_mode}.")

    # --- Decompose large features into stories for finer bottom-up (§3.3) ---
    _decompose(work_items, edges, variables)
    leaves = _leaf_work_items(work_items)

    # --- Complexity/risk factors -> velocity impact (§2.3-2.4) ---
    factors = derive_factors(components, edges, context, pattern, prd_text)
    accel_boost = 0.0
    if context_panel is not None:
        from ..models.context import SCOPE_ESTIMATE
        from ..models.complexity import LinkedFactor
        from ..models.enums import FactorScope, RiskSeverity

        for e in context_panel.risks:
            if e.content.strip():
                factors.append(LinkedFactor(
                    family=f"Risk: {e.content.strip()[:48]}", severity=RiskSeverity.MODERATE,
                    scope=FactorScope.PROJECT, impact=-0.3, is_risk=True))
        for e in context_panel.assumptions:
            if e.content.strip():
                assumptions.append(f"Assumption: {e.content.strip()[:160]}")
        accel_boost = 0.25 * sum(1 for e in context_panel.accelerators if e.content.strip())

    cx_impact = complexity_impact(factors, variables.avg_story_pts)
    # Accelerators offset the complexity penalty (capped so velocity stays sane).
    cx_impact = min(cx_impact + accel_boost, 0.3 * variables.avg_story_pts)
    if factors:
        assumptions.append(
            f"Applied {len(factors)} complexity/risk factor(s) "
            f"({', '.join(f.family for f in factors)}); velocity impact {cx_impact:+.2f} pts/eng-sprint."
        )

    # --- Bottom-up (leaf rollup, deterministic PERT) ---
    bottom_up = sum(montecarlo.deterministic_pert(wi.points, variables) for wi in leaves)

    # --- Top-down (pattern parametric; tuned prior from memory when provided) ---
    parametric = parametric_override or pattern.parametric_cost
    if parametric_override is not None:
        assumptions.append(
            f"Top-down base tuned by memory: {pattern.parametric_cost.base_effort_points:.0f} "
            f"-> {parametric_override.base_effort_points:.0f} points (reference class)."
        )
    drivers = _driver_quantities(components, edges, context)
    top_down = parametric.estimate_points(drivers)

    # Confidence-weighted blend of top-down and bottom-up. Bottom-up is weighted by
    # the breakdown's average confidence; the rest goes to the pattern's top-down.
    avg_conf = sum(wi.cure.confidence for wi in leaves) / len(leaves) if leaves else 0.5
    w_bottom = 0.4 + 0.4 * avg_conf  # 0.4-0.8
    blended = w_bottom * bottom_up + (1 - w_bottom) * top_down
    reconciliation = ReconciliationResult(
        top_down_points=round(top_down, 2),
        bottom_up_points=round(bottom_up, 2),
        blended_points=round(blended, 2),
    )
    if reconciliation.is_divergent():
        assumptions.append(
            f"Top-down ({top_down:.0f}) and bottom-up ({bottom_up:.0f}) diverge "
            f"{reconciliation.delta_pct * 100:.0f}%; blended to {blended:.0f} and widened the range."
        )

    # --- Team + cost (velocity carries the complexity impact) ---
    team = _build_team(components, rates, context, variables)
    engineers = max(1, sum(1 for r in team.roles if r.discipline != "Project & Program Management"))
    velocity = team_velocity(variables.avg_story_pts, engineers, complexity_impact=cx_impact)
    duration_sprints = blended / velocity if velocity else 0.0
    duration_months = duration_sprints * variables.weeks_in_sprint / 4.345
    total_cost = round((team.monthly_cost or 0.0) * duration_months, 2)
    team.total_cost = total_cost

    # --- Monte Carlo with correlated systemic risk (§4.1) ---
    # Center the uncertainty distribution on the blended working number (the
    # bottom-up rollup provides the *shape*; the blend provides the *level*).
    sigma = risk_sigma(factors, reconciliation.delta_pct)
    point_samples, _ = montecarlo.simulate_points([wi.points for wi in leaves], iterations, systemic_sigma=sigma)
    if bottom_up:
        point_samples = point_samples * (blended / bottom_up)
    effort_pct = montecarlo.derive_percentiles(point_samples)
    duration_samples = point_samples / velocity if velocity else np.zeros_like(point_samples)
    cost_per_point = (total_cost / blended) if blended else 0.0
    cost_samples = point_samples * cost_per_point
    monte_carlo = MonteCarloResult(
        iterations=iterations,
        effort_points=effort_pct,
        duration_sprints=montecarlo.derive_percentiles(duration_samples),
        cost=montecarlo.derive_percentiles(cost_samples),
    )

    deterministic = DeterministicResult(
        total_points=round(blended, 2),
        total_cost=total_cost,
        per_phase_velocity={"single-phase": velocity},
    )

    return SolutionGraph(
        project_name=project_name,
        client_context=context,
        requirements=requirements,
        capabilities=capabilities,
        components=components,
        work_items=work_items,
        edges=edges,
        variables=variables,
        team_plan=team,
        matched_pattern_ids=[pattern.id],
        deterministic=deterministic,
        monte_carlo=monte_carlo,
        reconciliation=reconciliation,
        complexity_factors=factors,
        context_panel=context_panel or _ContextPanel(),
        data_versions=DataVersions(
            tshirt_scale=tshirt_v,
            variables=vars_v,
            complexity_factors=complexity_v,
            practices=practices_v,
            tiers=tiers_v,
            pricing=pricing_v,
            patterns=patterns_v,
        ),
        assumptions=assumptions,
        ranked_matches=[{"pattern_id": m.pattern_id, "score": m.score, "rationale": m.rationale} for m in ranked],
    )
