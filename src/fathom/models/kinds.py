"""Semantic kind taxonomy (data/estimate_kinds.yaml) for classifying a piece of
extracted text as a kind of estimate element — work item (epic/feature/story),
measure (story_point), register item (risk/assumption), modifier (accelerator),
or timeline container (phase). Used by core/llm.py's classify_kind."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KindDisambiguation(BaseModel):
    """One pairwise distinction called out for a kind (e.g. epic vs feature)."""

    against: str
    distinction: str


class KindDefinition(BaseModel):
    """One entry in the taxonomy — everything needed to explain and detect it."""

    name: str
    role: str = Field(description="work_item | measure | register_item | modifier | timeline_container")
    definition: str
    parent: str | None = None
    children: list[str] = Field(default_factory=list)
    carries: list[str] = Field(default_factory=list)
    attribute_of: list[str] = Field(default_factory=list)
    modifies: list[str] = Field(default_factory=list)
    disambiguation: list[KindDisambiguation] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    placement: str = ""


class KindTaxonomy(BaseModel):
    """The full taxonomy loaded from data/estimate_kinds.yaml."""

    kinds: list[KindDefinition]

    def get(self, name: str) -> KindDefinition | None:
        return next((k for k in self.kinds if k.name == name), None)

    def names(self) -> list[str]:
        return [k.name for k in self.kinds]
