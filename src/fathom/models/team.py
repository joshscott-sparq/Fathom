"""Team plan, roles, tiers, and pricing models (spec §2.6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import Location


class Tier(BaseModel):
    """Seniority tier with sort weight (§2.6)."""

    name: str
    weight: int = Field(ge=1, description="Sort weight; higher = more senior.")


class RateRow(BaseModel):
    """One PriceListTable row: day rate by discipline + tier + location (§2.6)."""

    discipline: str
    tier: str
    location: Location
    day_rate: float = Field(ge=0.0, description="Per working-day rate.")


class Role(BaseModel):
    """A staffed role on the team plan (§2.6).

    Seeded from Params (discipline + tier). `allocated` vs `suggested` drives the
    green/orange/red allocation check (§2.6).
    """

    discipline: str
    tier: str
    practice: str | None = None
    location: Location = Location.US
    suggested: float = Field(
        default=0.0, ge=0.0, description="Suggested headcount from capacity math."
    )
    allocated: float = Field(
        default=0.0, ge=0.0, description="Actual allocated headcount."
    )
    day_rate: float = Field(
        default=0.0, ge=0.0, description="Resolved day rate for this role (§2.6)."
    )

    def allocation_status(self) -> str:
        """green / orange / red per §2.6 allocation check."""
        if self.allocated + 0.01 < self.suggested:
            return "red"  # under
        if self.allocated > self.suggested + 1:
            return "orange"  # over
        return "green"


class TeamPlan(BaseModel):
    """The assembled team across phases (§2.6).

    Roles are sorted by tier weight descending with Project & Program Management
    floated first; the core roles engine builds this, the model only holds it.
    """

    roles: list[Role] = Field(default_factory=list)
    monthly_cost: float | None = Field(
        default=None, description="Total monthly cost; set by the pricing engine."
    )
    total_cost: float | None = Field(
        default=None, description="Total engagement cost; set by the pricing engine."
    )
