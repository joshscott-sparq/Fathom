"""Reference-architecture pattern models (spec §4.2).

A Pattern is a curated reference architecture: a component template plus a
parametric cost model. Matching a PRD to a pattern gives the top-down estimate and
seeds the architecture components; the bottom-up work-item rollup is reconciled
against it (§4.2). Patterns are DATA (patterns.yaml); adding one is a data edit.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .graph import ComponentType, EdgeKind


class ComponentSpec(BaseModel):
    """A component the pattern implies, instantiated into the graph on match."""

    name: str
    component_type: ComponentType
    technology: str | None = None
    discipline: str | None = Field(
        default=None, description="Primary discipline that builds it (§2.7)."
    )
    description: str = ""


class IntegrationSpec(BaseModel):
    """A typical edge between two of the pattern's components."""

    source: str = Field(description="Source ComponentSpec name.")
    target: str = Field(description="Target ComponentSpec name.")
    kind: EdgeKind = EdgeKind.DATA_FLOW
    label: str = ""


class ParametricCost(BaseModel):
    """Top-down cost model for a pattern (§4.2).

    total_points = base_effort_points
                   + sum(scaling_drivers[d] * driver_quantity[d])
    Driver quantities (integration count, entity count, ...) come from the PRD or
    the contextualize step. `risk_factor_families` names the complexity families
    this pattern commonly triggers, pre-populating the decompose/critique passes.
    """

    base_effort_points: float = Field(ge=0.0, description="Story points at base scope.")
    scaling_drivers: dict[str, float] = Field(
        default_factory=dict,
        description="driver name -> story points per unit, e.g. {'integration': 8}.",
    )
    risk_factor_families: list[str] = Field(
        default_factory=list,
        description="Complexity families this pattern commonly triggers (§2.4).",
    )

    def estimate_points(self, driver_quantities: dict[str, float]) -> float:
        """Top-down point estimate given driver quantities."""
        total = self.base_effort_points
        for driver, per_unit in self.scaling_drivers.items():
            total += per_unit * driver_quantities.get(driver, 0.0)
        return total


class Pattern(BaseModel):
    """A reference-architecture pattern (§4.2)."""

    id: str
    name: str
    description: str = ""
    when_to_use: str = ""
    match_signals: list[str] = Field(
        default_factory=list,
        description="Keywords/tech/domain signals for matching a PRD to this pattern.",
    )
    components: list[ComponentSpec] = Field(default_factory=list)
    integrations: list[IntegrationSpec] = Field(default_factory=list)
    parametric_cost: ParametricCost
