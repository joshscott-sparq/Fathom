"""Complexity factor models (spec §2.4).

`ComplexityFactor` is the *definition* of a factor family, loaded from
`complexity_factors.yaml`. `LinkedFactor` is an *instance* of a factor attached to
a work item, phase, or the project, carrying the chosen severity and resolved
impact. The library is data; these models validate structure only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .enums import FactorScope, RiskSeverity


class ComplexityFactor(BaseModel):
    """Definition of one factor family from the library (§2.4)."""

    family: str
    category: str
    baseline: float = Field(
        description="Impact at the lowest severity level. -0.25 for families that "
        "start at -0.25 even at level 1 (integrations, security/compliance, "
        "staffing difficulty). 0.0 otherwise."
    )
    levels: list[RiskSeverity] = Field(
        description="Ordered severity levels available for this family (3-4 per §2.4)."
    )
    level_impacts: dict[RiskSeverity, float] = Field(
        default_factory=dict,
        description="Resolved impact per available level. Populated by the loader "
        "from the severity ladder; baseline overrides the first level.",
    )
    provenance: str = Field(
        default="",
        description="Source tag, e.g. verified cell range or pending-A44:C152.",
    )

    def impact_for(self, severity: RiskSeverity) -> float:
        """Velocity impact (<= 0) for a chosen severity level."""
        if severity not in self.level_impacts:
            raise KeyError(
                f"Severity {severity.value!r} not defined for factor "
                f"{self.family!r}. Available: {[s.value for s in self.levels]}"
            )
        return self.level_impacts[severity]


class LinkedFactor(BaseModel):
    """A factor instance attached to an item/phase/project (§2.1, §2.3).

    `impact` is negative (velocity/points penalty). `reduced_impact` captures the
    offset from added roles/seniority (§2.3 "net of Reduced Impact").
    """

    family: str
    severity: RiskSeverity
    scope: FactorScope
    impact: float = Field(le=0.0, description="Velocity/points impact, <= 0.")
    reduced_impact: float = Field(
        default=0.0,
        ge=0.0,
        description="Positive offset from added roles/seniority (§2.3).",
    )
    is_risk: bool = Field(
        default=False,
        description="True if sourced from the Risks 5x5 matrix rather than a "
        "static complexity level (§2.4).",
    )

    @model_validator(mode="after")
    def _check_reduced(self) -> "LinkedFactor":
        # Reduced impact cannot flip the sign of the net effect beyond zero.
        if self.impact + self.reduced_impact > 0:
            raise ValueError(
                f"reduced_impact {self.reduced_impact} exceeds |impact| "
                f"{abs(self.impact)} for factor {self.family!r}; net must be <= 0."
            )
        return self

    @property
    def net_impact(self) -> float:
        """Impact after role/seniority reduction (§2.3)."""
        return self.impact + self.reduced_impact
