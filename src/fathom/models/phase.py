"""Phase model (spec §2.3, §2.5).

A Phase groups work items and carries the velocity/capacity inputs the workbook
computes on the Phases tab. Computed outputs (velocity, capacity, hours) are
attached by the core engine, not set at construction.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .complexity import LinkedFactor


class Phase(BaseModel):
    """One delivery phase."""

    id: str
    name: str
    order: int = Field(ge=0, description="Sequence position; discovery phases first.")
    sprints: int = Field(ge=1, description="Number of sprints in the phase.")

    is_discovery: bool = Field(
        default=False,
        description="Discovery phases gain quality, not velocity, from AI boost (§2.3).",
    )

    ai_boost: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="AI tooling velocity boost for this phase (§2.3, 0.10-0.50).",
    )
    velocity_offset: float = Field(
        default=0.0,
        description="Manual velocity adjustment, typically positive later (§2.3).",
    )

    work_item_ids: list[str] = Field(
        default_factory=list, description="Ids of work items assigned to this phase."
    )
    phase_factors: list[LinkedFactor] = Field(
        default_factory=list,
        description="Phase-scoped complexity/risk factors feeding ComplexityImpact (§2.3).",
    )
