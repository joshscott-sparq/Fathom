"""Optimization advisor (spec §4.4, §5.5).

Suggests alternative team/development models (cheaper or faster) and features to
defer to a later version to cut delivery time. Grounded in historical estimates
(reference class) so the suggestion engine improves as engagements accumulate.

LLM-primary with a deterministic heuristic fallback, so it always returns useful
suggestions offline. Proposed team scenarios are computed with the real scenario
engine, so the cheaper/faster claims are backed by numbers, not assertions.
"""

from __future__ import annotations

from ..models.scenario import DeferralSuggestion, Scenario, TeamSuggestion
from ..models.solution_graph import SolutionGraph
from . import llm
from .rates import RateCard
from .scenarios import compute_scenario
from .velocity import team_velocity


def _history_summary(pattern_ids: list[str], past: list) -> str:
    """One-line-per-engagement summary of same-pattern history for grounding."""
    lines = []
    for stored in past:
        g = stored.graph
        if set(pattern_ids) & set(g.matched_pattern_ids) and g.deterministic:
            cost = g.deterministic.total_cost or 0
            lines.append(f"- {g.project_name}: {g.deterministic.total_points:.0f} pts, ${cost:,.0f}")
    return "\n".join(lines[:5])


def _baseline_engineers(graph: SolutionGraph) -> float:
    eng = [r for r in graph.team_plan.roles if r.discipline != "Project & Program Management"]
    return sum(r.allocated for r in eng) or float(len(eng)) or 1.0


def suggest_team_models(
    graph: SolutionGraph,
    card: RateCard,
    dev_models: dict[str, dict],
    past: list | None = None,
    use_llm: bool | None = None,
    llm_client=None,
) -> list[TeamSuggestion]:
    """Cheaper/faster scenario suggestions, each computed for real numbers."""
    past = past or []
    use_llm = llm.available() if use_llm is None else use_llm
    history = _history_summary(graph.matched_pattern_ids, past)
    base_eng = _baseline_engineers(graph)

    raw: list[dict] = []
    if use_llm:
        try:
            summary = (
                f"Pattern {graph.matched_pattern_ids}; "
                f"{graph.deterministic.total_points:.0f} pts baseline; "
                f"{round(base_eng)} engineers; tech {graph.client_context.tech_stack}."
            )
            raw = llm.suggest_team_models(summary, list(dev_models), history, client=llm_client)
        except Exception:
            raw = []

    # Highest-leverage AI tier (top of the ladder) grounds the heuristic fallback.
    top_tier_key = max(dev_models, key=lambda k: dev_models[k].get("tier", 0), default="tier-5")
    top_tier_name = dev_models.get(top_tier_key, {}).get("name", top_tier_key)

    if not raw:
        # Heuristic: top-tier+nearshore is cheaper; top-tier+larger team is faster.
        raw = [
            {"goal": "cheaper", "name": f"{top_tier_name} · Nearshore", "dev_model": top_tier_key,
             "location_mix": {"NS": 1.0}, "engineers": None,
             "rationale": f"{top_tier_name} automation plus nearshore rates cut cost."},
            {"goal": "faster", "name": f"{top_tier_name} · larger team", "dev_model": top_tier_key,
             "location_mix": {"US": 1.0}, "engineers": int(round(base_eng * 2)) or 2,
             "rationale": f"{top_tier_name} velocity plus a larger team compresses the timeline."},
        ]
        if history:
            for s in raw:
                s["rationale"] += " Grounded in prior same-pattern engagements."

    suggestions: list[TeamSuggestion] = []
    for i, s in enumerate(raw):
        dev_model = s.get("dev_model", top_tier_key)
        if dev_model not in dev_models:
            dev_model = top_tier_key
        scenario = Scenario(
            id=f"suggest-{i+1}",
            name=s.get("name", dev_model),
            dev_model=dev_model,
            location_mix=s.get("location_mix") or {"US": 1.0},
            engineers=s.get("engineers"),
        )
        result = compute_scenario(graph, scenario, card, dev_models)
        suggestions.append(
            TeamSuggestion(goal=s.get("goal", "faster"), scenario=scenario, rationale=s.get("rationale", ""), result=result)
        )
    return suggestions


def suggest_deferrals(
    graph: SolutionGraph,
    use_llm: bool | None = None,
    llm_client=None,
) -> list[DeferralSuggestion]:
    """Features to defer to a later version to cut delivery time."""
    use_llm = llm.available() if use_llm is None else use_llm
    variables = graph.variables
    engineers = _baseline_engineers(graph)
    velocity = team_velocity(variables.avg_story_pts, engineers)

    # Map feature name -> work item for saving computation.
    from . import montecarlo

    by_feature = {}
    for wi in graph.work_items:
        pts = montecarlo.deterministic_pert(wi.points, variables)
        by_feature[wi.feature or wi.id] = (wi, pts)

    chosen: list[tuple] = []  # (feature, wi, pts, rationale)
    if use_llm:
        try:
            listing = "\n".join(f"- {f} ({pts:.0f} pts)" for f, (_, pts) in by_feature.items())
            for d in llm.suggest_deferrals(listing, client=llm_client):
                f = d.get("feature")
                if f in by_feature:
                    wi, pts = by_feature[f]
                    chosen.append((f, wi, pts, d.get("rationale", "")))
        except Exception:
            chosen = []

    if not chosen:
        # Heuristic: largest 2 features (biggest time levers), cross-cutting first.
        ranked = sorted(by_feature.items(), key=lambda kv: kv[1][1], reverse=True)
        for f, (wi, pts) in ranked[:2]:
            chosen.append((f, wi, pts, "Largest single feature; deferring most reduces first-release time."))

    out: list[DeferralSuggestion] = []
    for feature, wi, pts, rationale in chosen:
        out.append(
            DeferralSuggestion(
                work_item_id=wi.id,
                feature=feature,
                points=round(pts, 1),
                rationale=rationale,
                est_sprint_saving=round(pts / velocity, 2) if velocity else 0.0,
            )
        )
    return out
