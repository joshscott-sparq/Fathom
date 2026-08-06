"""Contract: engineer-count cost model — more engineers shorten the timeline
but raise total cost (DECISIONS.md D11 fix)."""

from fathom.core import estimation
from fathom.core.recompute import RecomputeOverrides, recompute
from fathom.core.velocity import team_velocity
from fathom.models.enums import Location
from fathom.models.results import ClientContext
from fathom.models.team import RateRow

RAG_PRD = "- grounded llm answers over the knowledge base on databricks\n- vector store retrieval"

# Rates covering the RAG team disciplines so cost is non-zero.
RATES = [
    RateRow(discipline="AI & ML", tier="Senior", location=Location.US, day_rate=2000),
    RateRow(discipline="Data Engineering", tier="Senior", location=Location.US, day_rate=1800),
    RateRow(discipline="Web", tier="Senior", location=Location.US, day_rate=1600),
    RateRow(discipline="Project & Program Management", tier="Senior Lead", location=Location.US, day_rate=2000),
]


def test_velocity_is_sublinear():
    v1 = team_velocity(9, 2)
    v2 = team_velocity(9, 8)
    # 4x the engineers gives less than 4x velocity (diminishing returns).
    assert v2 > v1
    assert v2 < v1 * 4


def test_more_engineers_faster_but_costlier():
    graph = estimation.build_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), rates=RATES, use_llm=False)

    small = recompute(graph, RecomputeOverrides(engineer_count=2))
    large = recompute(graph, RecomputeOverrides(engineer_count=8))

    # More engineers -> shorter duration.
    assert large.monte_carlo.duration_sprints.p50 < small.monte_carlo.duration_sprints.p50
    # ... higher monthly burn (headcount now scales cost — the old bug is fixed).
    assert large.team_plan.monthly_cost > small.team_plan.monthly_cost
    # ... and total cost is NOT dramatically cheaper (old bug made 8 eng ~1/4 the
    # cost of 2). With headcount scaling it stays flat-to-higher.
    assert large.deterministic.total_cost >= small.deterministic.total_cost * 0.9
    # Effort is unchanged by team size.
    assert small.monte_carlo.effort_points.p50 == large.monte_carlo.effort_points.p50
