"""Contract: quantified Risk/Accelerator severity (D30), two-tier Variables
overrides (D31), MoSCoW priority (D32), and per-estimate RecomputeOverrides.variables."""

from fathom.core import estimation
from fathom.core.recompute import RecomputeOverrides, recompute
from fathom.models.context import ContextEntry, ContextPanel, ContextTab
from fathom.models.enums import RiskSeverity
from fathom.models.results import ClientContext
from fathom.models.variables import Variables
from fathom.persistence.variables import SQLiteVariablesRepository
from fathom.persistence.tshirt_scale import SQLiteTshirtScaleRepository

RAG_PRD = "- grounded llm answers over the knowledge base on databricks\n- vector store retrieval"


def _panel_with_risk(severity: RiskSeverity | None) -> ContextPanel:
    return ContextPanel(risks=[
        ContextEntry(id="r1", tab=ContextTab.RISKS, content="Vendor may slip the API deadline.", severity=severity),
    ])


def test_risk_severity_scales_velocity_impact():
    """A High-severity risk should slow the estimate more than a Low one."""
    low = estimation.build_estimate(
        "RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]),
        use_llm=False, context_panel=_panel_with_risk(RiskSeverity.LOW),
    )
    high = estimation.build_estimate(
        "RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]),
        use_llm=False, context_panel=_panel_with_risk(RiskSeverity.HIGH),
    )
    # Filter to the Context-Panel-derived risk specifically — derive_factors()
    # can independently flag general factors (e.g. "Integrations") as is_risk=True.
    low_risk_factor = next(f for f in low.complexity_factors if f.family.startswith("Risk:"))
    high_risk_factor = next(f for f in high.complexity_factors if f.family.startswith("Risk:"))
    assert high_risk_factor.impact < low_risk_factor.impact  # more negative = bigger penalty


def test_unset_risk_severity_defaults_to_moderate():
    graph = estimation.build_estimate(
        "RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]),
        use_llm=False, context_panel=_panel_with_risk(None),
    )
    risk_factor = next(f for f in graph.complexity_factors if f.family.startswith("Risk:"))
    variables = Variables()
    assert risk_factor.impact == variables.risk_impact_for(RiskSeverity.MODERATE)


def test_accelerator_severity_offsets_by_ladder_value():
    variables = Variables()
    panel_low = ContextPanel(accelerators=[
        ContextEntry(id="a1", tab=ContextTab.ACCELERATORS, content="Reusable codegen framework.", severity=RiskSeverity.LOW),
    ])
    panel_extreme = ContextPanel(accelerators=[
        ContextEntry(id="a1", tab=ContextTab.ACCELERATORS, content="Reusable codegen framework.", severity=RiskSeverity.EXTREME),
    ])
    low = estimation.build_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False, context_panel=panel_low)
    extreme = estimation.build_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False, context_panel=panel_extreme)
    # More accelerator offset -> less negative (or more positive) complexity impact -> higher velocity.
    assert extreme.deterministic.per_phase_velocity["single-phase"] >= low.deterministic.per_phase_velocity["single-phase"]
    assert variables.accelerator_impact_for(RiskSeverity.EXTREME) > variables.accelerator_impact_for(RiskSeverity.LOW)


def test_variables_repository_merges_overrides(tmp_path):
    repo = SQLiteVariablesRepository(tmp_path / "v.db")
    assert repo.effective_variables().avg_story_pts == 9.0

    repo.set_overrides({"avg_story_pts": 12})
    assert repo.effective_variables().avg_story_pts == 12.0

    # A second, different-field override doesn't drop the first.
    repo.set_overrides({"days_per_story_point": 1.5})
    effective = repo.effective_variables()
    assert effective.avg_story_pts == 12.0
    assert effective.days_per_story_point == 1.5
    assert set(repo.get_overrides()) == {"avg_story_pts", "days_per_story_point"}


def test_build_estimate_uses_variables_override():
    override = Variables(avg_story_pts=99.0)
    graph = estimation.build_estimate(
        "RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False, variables_override=override,
    )
    assert graph.variables.avg_story_pts == 99.0


def test_build_estimate_without_override_uses_yaml_defaults():
    graph = estimation.build_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False)
    assert graph.variables.avg_story_pts == 9.0


def test_recompute_overrides_variables_generic_dict():
    graph = estimation.build_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False)
    updated = recompute(graph, RecomputeOverrides(variables={"days_per_story_point": 2.0, "risk_impact_low": -0.9}))
    assert updated.variables.days_per_story_point == 2.0
    assert updated.variables.risk_impact_low == -0.9
    # Untouched fields keep their prior value.
    assert updated.variables.avg_story_pts == graph.variables.avg_story_pts


def test_recompute_variables_dict_takes_precedence_over_avg_story_pts_field():
    graph = estimation.build_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False)
    updated = recompute(graph, RecomputeOverrides(avg_story_pts=5.0, variables={"avg_story_pts": 20.0}))
    assert updated.variables.avg_story_pts == 20.0


def test_tshirt_scale_repository_merges_within_a_size(tmp_path):
    repo = SQLiteTshirtScaleRepository(tmp_path / "t.db")
    defaults = repo.effective_scale()
    assert defaults["M"]["story"] == 5

    repo.set_overrides({"M": {"epic": 55}})
    effective = repo.effective_scale()
    assert effective["M"]["epic"] == 55
    assert effective["M"]["story"] == 5  # untouched sibling field preserved
    assert effective["M"]["feature"] == 12.5


def test_build_estimate_uses_tshirt_scale_override():
    # build_estimate expects the FULL effective scale (like variables_override
    # expects a full Variables), not a sparse per-size patch — mirrors how
    # service.py threads service.get_tshirt_scale()'s already-merged result in.
    from fathom import data_loader

    defaults, _ = data_loader.load_tshirt_scale()
    custom = {size: dict(levels) for size, levels in defaults.items()}
    custom["M"]["feature"] = 999.0

    baseline = estimation.build_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False)
    overridden = estimation.build_estimate(
        "RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False, tshirt_scale_override=custom,
    )
    # Some component in this pattern sizes at "M" — the override should show up
    # somewhere in the resulting work items' realistic points vs. the baseline.
    baseline_points = sorted(wi.points.realistic for wi in baseline.work_items)
    overridden_points = sorted(wi.points.realistic for wi in overridden.work_items)
    assert baseline_points != overridden_points


def test_work_item_priority_field_roundtrips():
    from fathom.models.work_item import WorkItem
    from fathom.models.enums import WorkLevel
    from fathom.models.work_item import ThreePoint, CureAssessment

    wi = WorkItem(
        id="w1", level=WorkLevel.FEATURE, epic="E", feature="F",
        points=ThreePoint(realistic=5),
        cure=CureAssessment(complexity=2, unknowns=2, risks=2, effort=2, rationale="x", confidence=0.8),
        extraction_confidence=0.8, priority="must",
    )
    assert wi.priority == "must"
