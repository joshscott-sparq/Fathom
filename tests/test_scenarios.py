"""Contract: scenario computation and the optimization advisor."""

from fathom.core import advisor, estimation
from fathom.core.rates import RateCard
from fathom.core.scenarios import compute_scenario, default_scenarios
from fathom.data_loader import load_dev_models
from fathom.models.enums import Location
from fathom.models.results import ClientContext
from fathom.models.scenario import Scenario
from fathom.models.team import RateRow

RAG_PRD = "- grounded llm answers over the knowledge base on databricks\n- vector store retrieval\n- evaluation harness"

RATES = [
    RateRow(discipline="AI & ML", tier="Senior", location=Location.US, day_rate=2000),
    RateRow(discipline="AI & ML", tier="Senior", location=Location.NS, day_rate=1100),
    RateRow(discipline="Data Engineering", tier="Senior", location=Location.US, day_rate=1800),
    RateRow(discipline="Data Engineering", tier="Senior", location=Location.NS, day_rate=1000),
    RateRow(discipline="Web", tier="Senior", location=Location.US, day_rate=1600),
    RateRow(discipline="Web", tier="Senior", location=Location.NS, day_rate=900),
    RateRow(discipline="Project & Program Management", tier="Senior Lead", location=Location.US, day_rate=2000),
    RateRow(discipline="Project & Program Management", tier="Senior Lead", location=Location.NS, day_rate=1200),
]


def _graph():
    return estimation.build_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), rates=RATES, use_llm=False)


def test_blended_rate_weights_locations():
    card = RateCard(RATES)
    us = card.rate_for("AI & ML", "Senior", Location.US)
    ns = card.rate_for("AI & ML", "Senior", Location.NS)
    blended = card.blended_rate("AI & ML", "Senior", {"US": 0.5, "NS": 0.5})
    assert abs(blended - (us + ns) / 2) < 1e-6


def test_higher_tier_faster_than_tier_one():
    graph = _graph()
    dev_models, _ = load_dev_models()
    card = RateCard(RATES)
    tier1 = compute_scenario(graph, Scenario(id="t1", name="Tier 1", dev_model="tier-1"), card, dev_models)
    tier5 = compute_scenario(graph, Scenario(id="t5", name="Tier 5", dev_model="tier-5"), card, dev_models)
    # Higher AI-tier lifts velocity and automates some scope -> shorter duration.
    assert tier5.duration_sprints.p50 < tier1.duration_sprints.p50
    assert tier5.effort_points.p50 < tier1.effort_points.p50  # effort_multiplier < 1


def test_nearshore_cheaper_than_onshore():
    graph = _graph()
    dev_models, _ = load_dev_models()
    card = RateCard(RATES)
    us = compute_scenario(graph, Scenario(id="us", name="US", dev_model="tier-1", location_mix={"US": 1.0}), card, dev_models)
    ns = compute_scenario(graph, Scenario(id="ns", name="NS", dev_model="tier-1", location_mix={"NS": 1.0}), card, dev_models)
    assert ns.total_cost < us.total_cost


def test_default_scenarios_span_models():
    graph = _graph()
    dev_models, _ = load_dev_models()
    card = RateCard(RATES)
    results = [compute_scenario(graph, s, card, dev_models) for s in default_scenarios()]
    # 5 tiers · US, plus Nearshore and 50/50-blend variants of the top tier.
    assert len(results) == 7
    assert all(r.total_cost >= 0 for r in results)


def test_advisor_suggests_cheaper_and_faster():
    graph = _graph()
    dev_models, _ = load_dev_models()
    suggestions = advisor.suggest_team_models(graph, RateCard(RATES), dev_models, past=[], use_llm=False)
    goals = {s.goal for s in suggestions}
    assert {"cheaper", "faster"} <= goals
    # Each suggestion carries a computed result.
    assert all(s.result is not None for s in suggestions)
    cheaper = next(s for s in suggestions if s.goal == "cheaper")
    assert cheaper.result.total_cost < graph.deterministic.total_cost


def test_advisor_suggests_deferrals():
    graph = _graph()
    deferrals = advisor.suggest_deferrals(graph, use_llm=False)
    assert deferrals
    assert all(d.est_sprint_saving > 0 for d in deferrals)
    assert all(d.work_item_id for d in deferrals)
