"""WorkItem and its supporting models (spec §2.1, §2.2, §3.1-3.2).

A WorkItem is one row of the Estimates grid. The hierarchy follows the blank-cell
convention (§2.1): epic-only row = epic level; epic+feature = feature level;
epic+feature+story = story level. Rows are stored flat with `parent_id` to keep
the Gantt logic intact (§2.6, §3.3).

Points are stored in the item's native per-level t-shirt scale (§2.2). Story-point
normalization is done in core, not here (DECISIONS.md D2).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .complexity import LinkedFactor
from .enums import TShirtSize, WorkLevel


class ThreePoint(BaseModel):
    """Three-point estimate (§2.1). Optimistic/Pessimistic fall back to Realistic
    when blank."""

    realistic: float = Field(ge=0.0)
    optimistic: float | None = Field(default=None, ge=0.0)
    pessimistic: float | None = Field(default=None, ge=0.0)

    @property
    def effective_optimistic(self) -> float:
        """Optimistic value, substituting Realistic when blank (§2.1)."""
        return self.realistic if self.optimistic is None else self.optimistic

    @property
    def effective_pessimistic(self) -> float:
        """Pessimistic value, substituting Realistic when blank (§2.1)."""
        return self.realistic if self.pessimistic is None else self.pessimistic

    @model_validator(mode="after")
    def _check_order(self) -> "ThreePoint":
        # When provided, optimistic <= realistic <= pessimistic. Blanks are exempt.
        if self.optimistic is not None and self.optimistic > self.realistic:
            raise ValueError("optimistic must be <= realistic")
        if self.pessimistic is not None and self.pessimistic < self.realistic:
            raise ValueError("pessimistic must be >= realistic")
        return self


class CureAssessment(BaseModel):
    """C.U.R.E. framing of an estimate (§2.1, §3.2).

    Each dimension is 1 (trivial) to 5 (extreme). `confidence` is the sizing/
    extraction confidence; low confidence widens the O/P spread automatically
    during sizing (§3.2).
    """

    complexity: int = Field(ge=1, le=5)
    unknowns: int = Field(ge=1, le=5)
    risks: int = Field(ge=1, le=5)
    effort: int = Field(ge=1, le=5)
    rationale: str = Field(description="One-line sizing rationale (§3.2).")
    confidence: float = Field(ge=0.0, le=1.0)


class WorkItem(BaseModel):
    """One row of the Estimates grid (§2.1)."""

    id: str
    level: WorkLevel
    epic: str = Field(description="Epic name; always present.")
    feature: str | None = Field(
        default=None, description="Feature name; required at feature/story level."
    )
    story: str | None = Field(
        default=None, description="Story name; required at story level."
    )
    parent_id: str | None = Field(
        default=None, description="Parent row id (flat hierarchy for Gantt)."
    )
    phase_id: str | None = Field(
        default=None, description="Context Panel phase this item belongs to, if any."
    )

    tshirt: TShirtSize | None = Field(
        default=None, description="Assigned t-shirt size (§2.2)."
    )
    points: ThreePoint = Field(
        description="R/O/P in native per-level scale (§2.2). See DECISIONS.md D2."
    )
    cure: CureAssessment

    practice: str | None = Field(default=None, description="Assigned practice (§2.7).")
    discipline: str | None = Field(
        default=None, description="Assigned discipline (§2.7)."
    )
    notes: str | None = Field(
        default=None, description="Free-text detail/rationale for this row, hidden by default in the UI."
    )
    reference: str | None = Field(
        default=None,
        description="Filename or URL of the source document this row was classified/extracted "
        "from, if any (D25's classify_kind routing). Mirrors ContextEntry.reference so a "
        "classified item keeps a traceable link back to its source artifact whether it's "
        "routed to a Context Panel tab or straight into the work breakdown.",
    )
    linked_factors: list[LinkedFactor] = Field(
        default_factory=list,
        description="Item-scoped complexity/risk factors (§2.1).",
    )

    extraction_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence the item was correctly extracted from the PRD (§3.1).",
    )

    @model_validator(mode="after")
    def _check_hierarchy(self) -> "WorkItem":
        """Enforce the blank-cell hierarchy convention (§2.1)."""
        if self.level is WorkLevel.EPIC:
            if self.feature is not None or self.story is not None:
                raise ValueError("epic-level item must have blank feature and story")
        elif self.level is WorkLevel.FEATURE:
            if self.feature is None:
                raise ValueError("feature-level item requires a feature")
            if self.story is not None:
                raise ValueError("feature-level item must have blank story")
        else:  # STORY
            if self.feature is None or self.story is None:
                raise ValueError("story-level item requires both feature and story")
        return self
