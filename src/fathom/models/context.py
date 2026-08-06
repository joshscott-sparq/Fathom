"""Context Panel models (context-panel-spec.md).

The Context Panel holds every input that drives an estimate, organized into tabs.
Each tab is a list of discrete entries; each entry originates from manual text, a
dropped file, or a URL. Risks/Accelerators/Assumptions carry a Scope. Phases and
External Sources are their own structured lists. The whole ContextPanel is stored
on the SolutionGraph and fed to the background model on recalculation.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .work_item import WorkItem


class ContextTab(str, Enum):
    REQUIREMENTS = "requirements"
    RISKS = "risks"
    ACCELERATORS = "accelerators"
    ASSUMPTIONS = "assumptions"


class SourceType(str, Enum):
    MANUAL = "manual"
    FILE = "file"
    URL = "url"


class IngestStatus(str, Enum):
    INGESTED = "ingested"
    PROCESSING = "processing"
    ERROR = "error"


# Scope sentinel for "entire estimate"; anything else is a phase id.
SCOPE_ESTIMATE = "estimate"


class ContextEntry(BaseModel):
    id: str
    tab: ContextTab
    source_type: SourceType = SourceType.MANUAL
    content: str = Field(default="", description="Text, extracted file text, or fetched URL text.")
    reference: str | None = Field(default=None, description="Filename or URL for file/URL entries.")
    scope: str = Field(default=SCOPE_ESTIMATE, description="'estimate' or a phase id.")
    status: IngestStatus = IngestStatus.INGESTED
    created_at: str = ""
    duplicate_of: str | None = Field(
        default=None,
        description="Id of an existing entry this substantially restates; grouped with it in the UI.",
    )


class PhaseMethod(str, Enum):
    DATES = "dates"
    DURATION = "duration"
    RELATIVE = "relative"


class ContextPhase(BaseModel):
    id: str
    name: str
    method: PhaseMethod = PhaseMethod.RELATIVE
    start_date: str | None = None
    end_date: str | None = None
    duration_weeks: float | None = None
    description: str = ""


class ExternalSourceType(str, Enum):
    SPARQOS = "sparqos"
    SPECKIT = "speckit"
    GITHUB = "github"
    SALESFORCE = "salesforce"
    NOTION = "notion"
    SLACK = "slack"
    OTHER = "other"


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    NEEDS_AUTH = "needs_authentication"
    ERROR = "error"


class AccessMode(str, Enum):
    READ = "read-only"
    READ_WRITE = "read-write"


class ExternalSource(BaseModel):
    id: str
    type: ExternalSourceType
    display_name: str
    status: ConnectionStatus = ConnectionStatus.NEEDS_AUTH
    access_mode: AccessMode = AccessMode.READ
    # Type-specific references (repo/branch, account/opportunity, pages, channel, url).
    config: dict[str, str] = Field(default_factory=dict)
    created_at: str = ""


class ContextPanel(BaseModel):
    """All Context Panel input for one estimate."""

    requirements: list[ContextEntry] = Field(default_factory=list)
    risks: list[ContextEntry] = Field(default_factory=list)
    accelerators: list[ContextEntry] = Field(default_factory=list)
    assumptions: list[ContextEntry] = Field(default_factory=list)
    phases: list[ContextPhase] = Field(default_factory=list)
    external_sources: list[ExternalSource] = Field(default_factory=list)
    pinned_work_items: list[WorkItem] = Field(
        default_factory=list,
        description="Work items (D25: classified epic/feature/story from a dropped document) "
        "that the auto-recalc rebuild can't derive from the PRD text on its own. Persisted here "
        "(not just appended once) so every subsequent recalc — which always rebuilds work_items "
        "from scratch — re-applies them instead of silently discarding them.",
    )

    def entries_for(self, tab: ContextTab) -> list[ContextEntry]:
        return getattr(self, tab.value)
