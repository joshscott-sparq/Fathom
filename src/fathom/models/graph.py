"""Solution Graph node and edge models (spec §4.3).

The graph carries requirements, capabilities, and architecture components as typed
nodes, linked by typed edges. WorkItems (models/work_item.py) and Roles
(models/team.py) are the remaining node kinds; they keep their own richer models
and are referenced from the graph by id. Every emitted artifact is a projection
of this graph, so an architecture diagram, an effort estimate, and a cost model
all stay coherent when a node changes.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RequirementKind(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    CONSTRAINT = "constraint"


class ComponentType(str, Enum):
    """Architecture component kinds, used to render the reference architecture."""

    SERVICE = "service"
    UI = "ui"
    DATASTORE = "datastore"
    PIPELINE = "pipeline"
    ML_MODEL = "ml_model"
    GATEWAY = "gateway"
    QUEUE = "queue"
    INTEGRATION = "integration"
    EXTERNAL_SYSTEM = "external_system"


class Provenance(str, Enum):
    """Where a node came from, for defensibility (§4.2 guardrail)."""

    PATTERN = "pattern"
    INFERRED = "inferred"
    USER = "user"


class EdgeKind(str, Enum):
    """Typed relationships in the graph (§4.3)."""

    SATISFIED_BY = "satisfied_by"      # requirement -> capability
    REALIZED_BY = "realized_by"        # capability  -> component
    IMPLEMENTED_BY = "implemented_by"  # component   -> work_item
    DATA_FLOW = "data_flow"            # component   -> component
    INTEGRATES_WITH = "integrates_with"  # component -> component/external
    STAFFED_BY = "staffed_by"          # component/phase -> role


class Requirement(BaseModel):
    """A requirement extracted from the PRD (§3.1)."""

    id: str
    text: str
    kind: RequirementKind = RequirementKind.FUNCTIONAL
    source_ref: str | None = Field(
        default=None, description="Where in the PRD, e.g. section or line."
    )
    extraction_confidence: float = Field(ge=0.0, le=1.0)


class Capability(BaseModel):
    """A capability the system must provide, derived from requirements (§4.3)."""

    id: str
    name: str
    description: str = ""
    provenance: Provenance = Provenance.INFERRED


class Component(BaseModel):
    """An architecture component (§4.3). Rendered in the reference architecture."""

    id: str
    name: str
    component_type: ComponentType
    technology: str | None = Field(
        default=None, description="Concrete tech, aligned to client tech stack (§3.4)."
    )
    description: str = ""
    provenance: Provenance = Provenance.INFERRED
    pattern_id: str | None = Field(
        default=None, description="Source pattern if instantiated from the library."
    )
    discipline: str | None = Field(
        default=None, description="Primary discipline that builds this (§2.7)."
    )


class Edge(BaseModel):
    """A typed directed edge between two nodes, referenced by id (§4.3)."""

    source_id: str
    target_id: str
    kind: EdgeKind
    label: str = Field(default="", description="e.g. data-flow payload or integration name.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
