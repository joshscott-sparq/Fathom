"""Versioned Solution Graph store (spec §4.4).

Estimates accumulate so the model improves over time (memory) and every edit is a
new immutable version (interactive editing with an audit trail). SQLite is the
default backend behind the `EstimateRepository` interface; swap in Postgres later
without touching callers (DECISIONS.md D9).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..models.solution_graph import SolutionGraph


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class StoredEstimate:
    estimate_id: str
    version: int
    graph: SolutionGraph
    created_at: str
    opportunity_id: str | None = None


@dataclass
class EstimateSummary:
    estimate_id: str
    project_name: str
    version: int
    pattern_ids: list[str]
    cost_p50: float | None
    effort_p50: float | None
    updated_at: str
    owner_id: str | None = None
    opportunity_id: str | None = None
    tags: list[str] | None = None


class EstimateRepository(ABC):
    """Interface for storing and retrieving versioned estimates."""

    @abstractmethod
    def create(self, graph: SolutionGraph, owner_id: str | None = None, opportunity_id: str | None = None) -> StoredEstimate: ...

    @abstractmethod
    def update(self, estimate_id: str, graph: SolutionGraph) -> StoredEstimate: ...

    @abstractmethod
    def get(self, estimate_id: str, version: int | None = None) -> StoredEstimate | None: ...

    @abstractmethod
    def list_versions(self, estimate_id: str) -> list[int]: ...

    @abstractmethod
    def list_summaries(self) -> list[EstimateSummary]: ...

    @abstractmethod
    def all_latest(self) -> list[StoredEstimate]: ...


class SQLiteEstimateRepository(EstimateRepository):
    """SQLite-backed repository. Graphs stored as JSON documents."""

    def __init__(self, db_path: str | Path = "fathom.db"):
        self.db_path = str(db_path)
        self._init_schema()
        self._migrate()

    def _migrate(self) -> None:
        """Add owner_id / opportunity_id to estimates if an older DB lacks them."""
        with self._connect() as conn:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(estimates)").fetchall()}
            if "owner_id" not in cols:
                conn.execute("ALTER TABLE estimates ADD COLUMN owner_id TEXT")
            if "opportunity_id" not in cols:
                conn.execute("ALTER TABLE estimates ADD COLUMN opportunity_id TEXT")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS estimates (
                    id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS estimate_versions (
                    estimate_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    graph_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (estimate_id, version),
                    FOREIGN KEY (estimate_id) REFERENCES estimates(id)
                );
                """
            )

    def create(self, graph: SolutionGraph, owner_id: str | None = None, opportunity_id: str | None = None) -> StoredEstimate:
        estimate_id = _new_id()
        now = _now()
        payload = graph.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO estimates (id, project_name, current_version, created_at, updated_at, owner_id, opportunity_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (estimate_id, graph.project_name, 1, now, now, owner_id, opportunity_id),
            )
            conn.execute(
                "INSERT INTO estimate_versions (estimate_id, version, graph_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (estimate_id, 1, payload, now),
            )
        return StoredEstimate(estimate_id, 1, graph, now, opportunity_id=opportunity_id)

    def overwrite_latest(self, estimate_id: str, graph: SolutionGraph) -> StoredEstimate:
        """Auto-save: replace the current version's graph in place (no new version).

        Used for live editing of an estimate's inputs; deliberate actions
        (recompute/recost/scenarios) still snapshot new versions via update().
        """
        now = _now()
        with self._connect() as conn:
            row = conn.execute("SELECT current_version FROM estimates WHERE id = ?", (estimate_id,)).fetchone()
            if row is None:
                raise KeyError(f"estimate {estimate_id!r} not found")
            version = row["current_version"]
            conn.execute(
                "UPDATE estimate_versions SET graph_json = ?, created_at = ? WHERE estimate_id = ? AND version = ?",
                (graph.model_dump_json(), now, estimate_id, version),
            )
            conn.execute(
                "UPDATE estimates SET updated_at = ?, project_name = ? WHERE id = ?",
                (now, graph.project_name, estimate_id),
            )
        return StoredEstimate(estimate_id, version, graph, now, opportunity_id=self.owner_and_opportunity(estimate_id)[1])

    def clone(self, estimate_id: str, owner_id: str | None = None) -> StoredEstimate:
        """Copy the latest graph into a brand-new estimate (version 1).

        Keeps the opportunity link but is never the active/official estimate.
        """
        src = self.get(estimate_id)
        if src is None:
            raise KeyError(f"estimate {estimate_id!r} not found")
        _, opportunity_id = self.owner_and_opportunity(estimate_id)
        graph = src.graph.model_copy(deep=True)
        graph.project_name = f"{graph.project_name} (clone)"
        return self.create(graph, owner_id=owner_id, opportunity_id=opportunity_id)

    def update(self, estimate_id: str, graph: SolutionGraph) -> StoredEstimate:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT current_version FROM estimates WHERE id = ?", (estimate_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"estimate {estimate_id!r} not found")
            new_version = row["current_version"] + 1
            conn.execute(
                "INSERT INTO estimate_versions (estimate_id, version, graph_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (estimate_id, new_version, graph.model_dump_json(), now),
            )
            conn.execute(
                "UPDATE estimates SET current_version = ?, updated_at = ? WHERE id = ?",
                (new_version, now, estimate_id),
            )
        return StoredEstimate(estimate_id, new_version, graph, now, opportunity_id=self.owner_and_opportunity(estimate_id)[1])

    def get(self, estimate_id: str, version: int | None = None) -> StoredEstimate | None:
        with self._connect() as conn:
            if version is None:
                row = conn.execute(
                    "SELECT v.version, v.graph_json, v.created_at "
                    "FROM estimate_versions v "
                    "JOIN estimates e ON e.id = v.estimate_id AND e.current_version = v.version "
                    "WHERE v.estimate_id = ?",
                    (estimate_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT version, graph_json, created_at FROM estimate_versions "
                    "WHERE estimate_id = ? AND version = ?",
                    (estimate_id, version),
                ).fetchone()
        if row is None:
            return None
        graph = SolutionGraph.model_validate_json(row["graph_json"])
        return StoredEstimate(estimate_id, row["version"], graph, row["created_at"], opportunity_id=self.owner_and_opportunity(estimate_id)[1])

    def list_versions(self, estimate_id: str) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT version FROM estimate_versions WHERE estimate_id = ? ORDER BY version",
                (estimate_id,),
            ).fetchall()
        return [r["version"] for r in rows]

    def list_summaries(self) -> list[EstimateSummary]:
        summaries: list[EstimateSummary] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, updated_at, owner_id, opportunity_id FROM estimates ORDER BY updated_at DESC"
            ).fetchall()
        for row in rows:
            stored = self.get(row["id"])
            if stored is None:
                continue
            summaries.append(self._summarize(stored, row["updated_at"], row["owner_id"], row["opportunity_id"]))
        return summaries

    def owner_and_opportunity(self, estimate_id: str) -> tuple[str | None, str | None]:
        with self._connect() as conn:
            row = conn.execute("SELECT owner_id, opportunity_id FROM estimates WHERE id = ?", (estimate_id,)).fetchone()
        return (row["owner_id"], row["opportunity_id"]) if row else (None, None)

    def set_opportunity(self, estimate_id: str, opportunity_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE estimates SET opportunity_id = ? WHERE id = ?", (opportunity_id, estimate_id))

    def all_latest(self) -> list[StoredEstimate]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM estimates").fetchall()
        return [s for s in (self.get(r["id"]) for r in rows) if s is not None]

    @staticmethod
    def _summarize(stored: StoredEstimate, updated_at: str, owner_id: str | None = None,
                   opportunity_id: str | None = None) -> EstimateSummary:
        g = stored.graph
        return EstimateSummary(
            estimate_id=stored.estimate_id,
            project_name=g.project_name,
            version=stored.version,
            pattern_ids=g.matched_pattern_ids,
            cost_p50=g.monte_carlo.cost.p50 if g.monte_carlo else None,
            effort_p50=g.monte_carlo.effort_points.p50 if g.monte_carlo else None,
            updated_at=updated_at,
            owner_id=owner_id,
            opportunity_id=opportunity_id,
            tags=list(g.tags),
        )
