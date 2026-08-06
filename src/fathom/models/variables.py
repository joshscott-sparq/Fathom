"""Variables model (spec §2.1, §2.3, §2.5).

Holds the tunable constants that the contextualize step may override (§3.4).
Defaults are loaded from `variables.yaml`; overrides are applied per estimate.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Variables(BaseModel):
    """Workbook VariablesTable + Phases-tab constants."""

    # PERT weights (§2.1)
    real_weight: float = Field(default=1.0)
    opt_weight: float = Field(default=0.95)
    pes_weight: float = Field(default=1.2)

    # Hierarchy multipliers (§2.1)
    epic_multiplier: float = Field(default=10.0)
    feature_multiplier: float = Field(default=2.5)

    # Velocity (§2.3)
    avg_story_pts: float = Field(default=9.0)
    ai_boost_min: float = Field(default=0.10)
    ai_boost_max: float = Field(default=0.50)

    # Capacity ratios (§2.5)
    ba_ratio: float = Field(default=0.1)
    designer_ratio: float = Field(default=0.2)
    devops_ratio: float = Field(default=0.4)
    qa_ratio: float = Field(default=0.4)

    # Time constants (§2.5, §2.6)
    hours_per_sprint: float = Field(default=80.0)
    weeks_in_sprint: int = Field(default=2)
    working_month_days: int = Field(default=21)
    hours_per_day: float = Field(default=8.0)

    # Risk impacts (§2.4)
    risk_impact_low: float = Field(default=-0.25)
    risk_impact_moderate: float = Field(default=-0.5)
    risk_impact_high: float = Field(default=-0.75)
    risk_impact_extreme: float = Field(default=-1.0)
