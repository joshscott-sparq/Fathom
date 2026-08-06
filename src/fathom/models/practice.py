"""Practice and discipline models (spec §2.7)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DisciplineConstraint(BaseModel):
    """Constraint on how a discipline may be staffed (§2.7)."""

    discipline: str
    min_tier: str | None = Field(
        default=None, description="Minimum tier, e.g. Solutions Architect >= Senior Lead."
    )
    note: str = ""


class Practice(BaseModel):
    """A practice and the disciplines it contains (§2.7)."""

    name: str
    disciplines: list[str]


class PracticeLibrary(BaseModel):
    """The full practice/discipline taxonomy loaded from practices.yaml."""

    practices: list[Practice]
    constraints: list[DisciplineConstraint] = Field(default_factory=list)

    def practice_of(self, discipline: str) -> str | None:
        """Return the practice a discipline belongs to, or None."""
        for practice in self.practices:
            if discipline in practice.disciplines:
                return practice.name
        return None
