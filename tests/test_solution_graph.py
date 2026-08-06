"""Contract: Solution Graph spine and pattern library (spec §4.2, §4.3)."""

import pytest

from fathom.data_loader import load_patterns
from fathom.models import (
    Capability,
    Component,
    ComponentType,
    CureAssessment,
    Edge,
    EdgeKind,
    Provenance,
    ReconciliationResult,
    Requirement,
    SolutionGraph,
    ThreePoint,
    WorkItem,
    WorkLevel,
)


def _cure():
    return CureAssessment(complexity=3, unknowns=2, risks=2, effort=3, rationale="x", confidence=0.8)


def _sample_graph():
    req = Requirement(id="r1", text="Answer questions over the corpus", extraction_confidence=0.9)
    cap = Capability(id="c1", name="Grounded Q&A", provenance=Provenance.INFERRED)
    comp = Component(
        id="cmp1", name="Retrieval Orchestrator", component_type=ComponentType.SERVICE,
        provenance=Provenance.PATTERN, pattern_id="rag-databricks", discipline="AI & ML",
    )
    wi = WorkItem(
        id="w1", level=WorkLevel.STORY, epic="Retrieval", feature="Orchestration",
        story="Assemble context", points=ThreePoint(realistic=5), cure=_cure(),
        extraction_confidence=0.85,
    )
    edges = [
        Edge(source_id="r1", target_id="c1", kind=EdgeKind.SATISFIED_BY),
        Edge(source_id="c1", target_id="cmp1", kind=EdgeKind.REALIZED_BY),
        Edge(source_id="cmp1", target_id="w1", kind=EdgeKind.IMPLEMENTED_BY),
    ]
    return SolutionGraph(
        project_name="Demo", requirements=[req], capabilities=[cap],
        components=[comp], work_items=[wi], edges=edges,
    )


def test_graph_projections():
    g = _sample_graph()
    assert [c.id for c in g.components_for_capability("c1")] == ["cmp1"]
    assert [w.id for w in g.work_items_for_component("cmp1")] == ["w1"]


def test_graph_rejects_dangling_edge():
    with pytest.raises(ValueError):
        SolutionGraph(
            project_name="Bad",
            requirements=[Requirement(id="r1", text="x", extraction_confidence=0.5)],
            edges=[Edge(source_id="r1", target_id="ghost", kind=EdgeKind.SATISFIED_BY)],
        )


def test_architecture_edges_only_component_level():
    g = _sample_graph()
    g.edges.append(Edge(source_id="cmp1", target_id="cmp1", kind=EdgeKind.DATA_FLOW, label="loop"))
    arch = g.architecture_edges()
    assert all(e.kind in {EdgeKind.DATA_FLOW, EdgeKind.INTEGRATES_WITH} for e in arch)
    assert len(arch) == 1


def test_pattern_library_loads():
    patterns, version = load_patterns()
    assert version == "0.1.0"
    assert set(patterns) == {"rag-databricks", "dotnet-modernization", "agentic-mcp"}
    rag = patterns["rag-databricks"]
    assert any(c.component_type is ComponentType.DATASTORE for c in rag.components)
    assert rag.integrations  # has typical edges


def test_parametric_cost_scales_with_drivers():
    """Top-down estimate = base + sum(driver * per-unit) (§4.2)."""
    patterns, _ = load_patterns()
    rag = patterns["rag-databricks"]
    base = rag.parametric_cost.base_effort_points
    # 2 data sources (13 each) + 3 integrations (8 each) = +50
    est = rag.parametric_cost.estimate_points({"data_source": 2, "integration": 3})
    assert est == base + 2 * 13 + 3 * 8


def test_reconciliation_divergence():
    """Top-down vs bottom-up delta flags divergence (§4.2)."""
    rec = ReconciliationResult(top_down_points=200, bottom_up_points=210)
    assert not rec.is_divergent()  # 5% within 25% threshold
    rec2 = ReconciliationResult(top_down_points=200, bottom_up_points=300)
    assert rec2.is_divergent()  # 50% delta
    assert rec2.delta == 100
