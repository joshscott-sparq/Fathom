"""Result and context models shared across projections (spec §3.4, §4.1, §4.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClientContext(BaseModel):
    """Client-supplied context a PRD cannot provide (§3.4)."""

    tech_stack: list[str] = Field(default_factory=list)
    compliance_posture: list[str] = Field(
        default_factory=list,
        description="Maps to the Sec & Compliance Risks factor family (§3.4).",
    )
    team_skills: list[str] = Field(
        default_factory=list,
        description="Feeds Familiarity w/ Tech and discipline assignment (§3.4).",
    )
    us_ns_mix: dict[str, float] = Field(
        default_factory=dict, description="Location mix, e.g. {'US': 0.6, 'NS': 0.4}."
    )


class Percentiles(BaseModel):
    """Monte Carlo output percentiles (§4.1)."""

    p10: float
    p50: float
    p80: float
    p90: float


class MonteCarloResult(BaseModel):
    """Distribution outputs across effort, duration, and cost (§4.1)."""

    iterations: int
    effort_points: Percentiles
    duration_sprints: Percentiles
    cost: Percentiles


class DeterministicResult(BaseModel):
    """Point-estimate outputs (calibration mode)."""

    total_points: float
    total_effort_hours: float | None = None
    total_cost: float | None = None
    per_phase_velocity: dict[str, float] = Field(default_factory=dict)


class ReconciliationResult(BaseModel):
    """Top-down (pattern) vs bottom-up (work-item rollup) reconciliation (§4.2).

    Disagreement is the diagnostic: a large delta flags either a missed pattern
    scaling driver or an incomplete work breakdown.
    """

    top_down_points: float = Field(description="Pattern parametric estimate.")
    bottom_up_points: float = Field(description="Work-item rollup.")
    blended_points: float | None = Field(
        default=None, description="Confidence-weighted blend of top-down and bottom-up.")
    per_capability: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="capability_id -> {top_down, bottom_up}.",
    )

    @property
    def delta(self) -> float:
        return self.bottom_up_points - self.top_down_points

    @property
    def delta_pct(self) -> float:
        base = self.top_down_points or 1.0
        return self.delta / base

    def is_divergent(self, threshold: float = 0.25) -> bool:
        """True when the two estimates disagree beyond `threshold` (default 25%)."""
        return abs(self.delta_pct) > threshold


class DataVersions(BaseModel):
    """Versions of the lookup tables used, for reproducibility."""

    tshirt_scale: str
    variables: str
    complexity_factors: str
    practices: str
    tiers: str
    pricing: str
    patterns: str
