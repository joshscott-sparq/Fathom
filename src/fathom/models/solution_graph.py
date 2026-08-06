"""The Solution Graph: the single central object (spec §4.3).

Every artifact (reference architecture, effort estimate, cost model, SOW scope,
resourcing note) is a projection of this graph. Change one node and all
projections stay coherent. This replaces the flat EstimateModel from the original
Step 1 (DECISIONS.md D8).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .complexity import LinkedFactor
from .context import ContextPanel
from .graph import Capability, Component, Edge, EdgeKind, Requirement
from .phase import Phase
from .results import (
    ClientContext,
    DataVersions,
    DeterministicResult,
    MonteCarloResult,
    ReconciliationResult,
)
from .scenario import ScenarioResult
from .team import TeamPlan
from .variables import Variables
from .work_item import WorkItem


class SolutionGraph(BaseModel):
    """Requirements -> capabilities -> components -> work items -> effort -> team -> cost."""

    project_name: str
    client_context: ClientContext = Field(default_factory=ClientContext)
    context_panel: ContextPanel = Field(default_factory=ContextPanel)

    # Nodes
    requirements: list[Requirement] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    work_items: list[WorkItem] = Field(default_factory=list)

    # Edges
    edges: list[Edge] = Field(default_factory=list)

    # Estimation inputs / plan
    phases: list[Phase] = Field(default_factory=list)
    variables: Variables = Field(default_factory=Variables)
    team_plan: TeamPlan = Field(default_factory=TeamPlan)

    # Pattern linkage (§4.2)
    matched_pattern_ids: list[str] = Field(default_factory=list)
    ranked_matches: list[dict] = Field(
        default_factory=list,
        description="All pattern matches with scores/rationale, for the UI to show why (§4.2).",
    )

    # Results
    deterministic: DeterministicResult | None = None
    monte_carlo: MonteCarloResult | None = None
    reconciliation: ReconciliationResult | None = None

    # Applied complexity/risk factors that reduce velocity (spec §2.3-2.4).
    complexity_factors: list[LinkedFactor] = Field(default_factory=list)

    # Staffing/development-model scenarios (spec §5.5).
    scenarios: list[ScenarioResult] = Field(default_factory=list)

    # Provenance
    data_versions: DataVersions | None = None
    assumptions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, description="User metadata tags for filtering/organizing.")

    # --- Projection helpers ---

    def _node_ids(self) -> set[str]:
        ids = set()
        for collection in (self.requirements, self.capabilities, self.components, self.work_items):
            ids.update(node.id for node in collection)
        return ids

    def edges_of_kind(self, kind: EdgeKind) -> list[Edge]:
        return [e for e in self.edges if e.kind is kind]

    def architecture_edges(self) -> list[Edge]:
        """Component-to-component edges for the reference architecture diagram (§4.4c)."""
        arch = {EdgeKind.DATA_FLOW, EdgeKind.INTEGRATES_WITH}
        return [e for e in self.edges if e.kind in arch]

    def work_items_for_component(self, component_id: str) -> list[WorkItem]:
        """Work items implementing a component (IMPLEMENTED_BY edges)."""
        wi_ids = {
            e.target_id
            for e in self.edges
            if e.kind is EdgeKind.IMPLEMENTED_BY and e.source_id == component_id
        }
        return [wi for wi in self.work_items if wi.id in wi_ids]

    def components_for_capability(self, capability_id: str) -> list[Component]:
        """Components realizing a capability (REALIZED_BY edges)."""
        comp_ids = {
            e.target_id
            for e in self.edges
            if e.kind is EdgeKind.REALIZED_BY and e.source_id == capability_id
        }
        return [c for c in self.components if c.id in comp_ids]

    @model_validator(mode="after")
    def _check_edge_endpoints(self) -> "SolutionGraph":
        """Every edge must connect nodes that exist in the graph."""
        ids = self._node_ids()
        for edge in self.edges:
            missing = {edge.source_id, edge.target_id} - ids
            if missing:
                raise ValueError(
                    f"edge {edge.kind.value} references unknown node(s): {sorted(missing)}"
                )
        return self
