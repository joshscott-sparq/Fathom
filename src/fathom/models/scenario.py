"""Scenario models: multiple staffing/development models per estimate (spec §5.5).

A Scenario is a named set of assumptions applied to the same work breakdown —
AI Tier (human-to-AI-agent ratio, tier-1..tier-5), location mix (US / nearshore /
blended), and team size — producing its own effort, duration, and cost so
alternatives can be compared side by side.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .results import Percentiles


class Scenario(BaseModel):
    """A staffing/AI-tier model to evaluate against the work breakdown."""

    id: str
    name: str
    dev_model: str = Field(default="tier-1", description="Key into the AI Tier library.")
    location_mix: dict[str, float] = Field(
        default_factory=lambda: {"US": 1.0},
        description="Location weights, e.g. {'US': 0.5, 'NS': 0.5}.",
    )
    engineers: int | None = Field(default=None, ge=1, description="Team size override.")


class ScenarioResult(BaseModel):
    """Computed outcome for a scenario."""

    scenario: Scenario
    assumptions: list[str] = Field(default_factory=list)
    effort_points: Percentiles
    duration_sprints: Percentiles
    cost: Percentiles
    monthly_cost: float
    total_cost: float


class TeamSuggestion(BaseModel):
    """An advisor-proposed scenario optimized for a goal (spec: cheaper/faster)."""

    goal: str = Field(description="cheaper | faster")
    scenario: Scenario
    rationale: str
    result: ScenarioResult | None = None


class DeferralSuggestion(BaseModel):
    """A feature the advisor suggests deferring to a later version to cut time."""

    work_item_id: str
    feature: str
    points: float
    rationale: str
    est_sprint_saving: float
