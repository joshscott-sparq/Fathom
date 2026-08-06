"""Contract: matcher, PERT, Monte Carlo, and end-to-end estimate build."""

import math

from fathom.core import estimation, montecarlo
from fathom.core.matcher import score_patterns
from fathom.data_loader import load_patterns, load_variables
from fathom.models.results import ClientContext
from fathom.models.work_item import ThreePoint

RAG_PRD = """
- Build a retrieval augmented generation platform over our knowledge base
- Users query unstructured documents and get grounded llm answers
- Runs on databricks with embeddings in a vector store
"""


def test_deterministic_pert_hand_computed():
    """AvgPts = (1.0*5 + 0.95*3 + 1.2*8) / (1.0 + 0.95 + 1.2) (§2.1)."""
    variables, _ = load_variables()
    tp = ThreePoint(realistic=5, optimistic=3, pessimistic=8)
    expected = (1.0 * 5 + 0.95 * 3 + 1.2 * 8) / (1.0 + 0.95 + 1.2)
    assert math.isclose(montecarlo.deterministic_pert(tp, variables), expected)


def test_pert_blank_substitution():
    variables, _ = load_variables()
    tp = ThreePoint(realistic=5)  # O and P blank -> substitute 5
    assert math.isclose(montecarlo.deterministic_pert(tp, variables), 5.0)


def test_monte_carlo_percentiles_ordered_and_bounded():
    tps = [ThreePoint(realistic=5, optimistic=3, pessimistic=10) for _ in range(20)]
    totals, pct = montecarlo.simulate_points(tps, iterations=5000)
    assert pct.p10 < pct.p50 < pct.p80 < pct.p90
    # Every sample and every percentile lies within [sum optimistic, sum pessimistic].
    lo, hi = 20 * 3, 20 * 10
    assert lo <= pct.p10 and pct.p90 <= hi

    # Known divergence (DECISIONS.md D10): the workbook deterministic mean is more
    # pessimism-weighted than a symmetric PERT-beta, so it also lies in-bounds but
    # can sit above the MC P90. They are different methodologies, both retained.
    variables, _ = load_variables()
    det = sum(montecarlo.deterministic_pert(tp, variables) for tp in tps)
    assert lo <= det <= hi


def test_matcher_picks_rag():
    patterns, _ = load_patterns()
    ranked = score_patterns(RAG_PRD, ClientContext(tech_stack=["Databricks"]), patterns)
    assert ranked[0].pattern_id == "rag-databricks"
    assert ranked[0].score > 0


def test_build_estimate_end_to_end():
    graph = estimation.build_estimate("Acme RAG", RAG_PRD, ClientContext(tech_stack=["Databricks", "Python"]))
    assert graph.matched_pattern_ids == ["rag-databricks"]
    # Graph populated across layers.
    assert graph.requirements and graph.capabilities and graph.components and graph.work_items
    # Results present and coherent.
    assert graph.reconciliation is not None
    assert graph.monte_carlo is not None
    assert graph.monte_carlo.effort_points.p10 < graph.monte_carlo.effort_points.p90
    assert graph.deterministic.total_cost >= 0
    # Edge integrity validated by the model; projections resolve.
    assert graph.architecture_edges()
    assert graph.data_versions.patterns == "0.1.0"


def test_build_estimate_is_reproducible():
    g1 = estimation.build_estimate("Acme", RAG_PRD, ClientContext(tech_stack=["Databricks"]))
    g2 = estimation.build_estimate("Acme", RAG_PRD, ClientContext(tech_stack=["Databricks"]))
    assert g1.monte_carlo.cost.p50 == g2.monte_carlo.cost.p50
