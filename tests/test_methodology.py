"""Contract: the estimation-methodology improvements."""

import numpy as np

from fathom.core import estimation, montecarlo
from fathom.core.estimation import _three_point
from fathom.core.factors import complexity_impact, risk_sigma
from fathom.models.enums import WorkLevel
from fathom.models.results import ClientContext
from fathom.models.work_item import ThreePoint

RAG_PRD = "- retrieval augmented generation over the knowledge base on databricks\n- vector store, embeddings, evaluation harness"


def test_confidence_widens_spread():
    tight = _three_point(100, confidence=0.9)
    loose = _three_point(100, confidence=0.2)
    assert tight.realistic == loose.realistic == 100
    # Lower confidence -> wider band on both sides, pessimistic widens more.
    assert loose.optimistic < tight.optimistic
    assert loose.pessimistic > tight.pessimistic
    assert (loose.pessimistic - loose.optimistic) > (tight.pessimistic - tight.optimistic)


def test_systemic_risk_widens_monte_carlo():
    tps = [ThreePoint(realistic=5, optimistic=3, pessimistic=10) for _ in range(20)]
    _, tight = montecarlo.simulate_points(tps, iterations=8000, systemic_sigma=0.0)
    _, wide = montecarlo.simulate_points(tps, iterations=8000, systemic_sigma=0.3)
    # Correlated systemic risk widens the P10-P90 spread; medians stay comparable.
    assert (wide.p90 - wide.p10) > (tight.p90 - tight.p10)
    assert abs(wide.p50 - tight.p50) / tight.p50 < 0.1


def test_factors_reduce_velocity_and_raise_cost():
    light = estimation.build_estimate("Light", RAG_PRD, ClientContext(tech_stack=["Databricks"], team_skills=["Databricks", "Spark", "LLMs"]), use_llm=False)
    heavy = estimation.build_estimate("Heavy", RAG_PRD, ClientContext(tech_stack=["Rust", "Haskell"], compliance_posture=["HIPAA", "FedRAMP"], team_skills=[]), use_llm=False)

    # Heavy context derives more/severe factors -> lower velocity.
    assert len(heavy.complexity_factors) >= len(light.complexity_factors)
    assert heavy.deterministic.per_phase_velocity["single-phase"] < light.deterministic.per_phase_velocity["single-phase"]
    # A named compliance regime shows up as a Sec & Compliance factor.
    assert any(f.family == "Sec & Compliance Risks" for f in heavy.complexity_factors)


def test_complexity_impact_is_floored():
    # Even with huge nominal impact, velocity erosion is capped (>-70% of AvgStoryPts).
    from fathom.models.complexity import LinkedFactor
    from fathom.models.enums import FactorScope, RiskSeverity

    huge = [LinkedFactor(family=f"F{i}", severity=RiskSeverity.EXTREME, scope=FactorScope.PROJECT, impact=-1.0) for i in range(20)]
    assert complexity_impact(huge, 9.0) == -0.7 * 9.0


def test_blend_between_top_down_and_bottom_up():
    g = estimation.build_estimate("Blend", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False)
    rec = g.reconciliation
    lo, hi = sorted([rec.top_down_points, rec.bottom_up_points])
    assert lo <= rec.blended_points <= hi


def test_large_features_decompose_into_stories():
    g = estimation.build_estimate("Decomp", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False)
    # RAG has pipeline components (feature-L) that split into story-level children.
    assert any(wi.level is WorkLevel.STORY for wi in g.work_items)
    # Decomposed features have children (are not leaves).
    parents = {wi.parent_id for wi in g.work_items if wi.parent_id}
    assert parents


def test_risk_sigma_grows_with_factors_and_divergence():
    from fathom.models.complexity import LinkedFactor
    from fathom.models.enums import FactorScope, RiskSeverity

    few = [LinkedFactor(family="A", severity=RiskSeverity.LOW, scope=FactorScope.PROJECT, impact=-0.25)]
    many = few + [LinkedFactor(family=f"B{i}", severity=RiskSeverity.HIGH, scope=FactorScope.PROJECT, impact=-0.75) for i in range(4)]
    assert risk_sigma(many, 0.4) > risk_sigma(few, 0.0)
    assert risk_sigma(many, 0.4) <= 0.40  # capped
