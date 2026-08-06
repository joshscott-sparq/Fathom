"""Persisted Variables overrides (D31 — two-tier variable settings).

Org-wide tier: a single row of admin-set overrides, sparse (only fields an admin
has explicitly changed; everything else falls through to the `variables.yaml`
default). Merged with the YAML defaults fresh on every read, so a change takes
effect immediately for the next estimate built/rebuilt/recalculated — no cache
to invalidate. Per-estimate overrides are a separate mechanism (D31): they live
on the estimate's own `SolutionGraph.variables` via `core/recompute.py`, not here.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .. import data_loader
from ..models.variables import Variables

_ROW_ID = "global"


class SQLiteVariablesRepository:
    """SQLite-backed store for org-wide Variables overrides."""

    def __init__(self, db_path: str | Path = "fathom.db"):
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS variable_overrides (
                    id TEXT PRIMARY KEY,
                    overrides_json TEXT NOT NULL
                );
                """
            )

    def get_overrides(self) -> dict:
        """Raw admin-set overrides (field_name -> value), sparse."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT overrides_json FROM variable_overrides WHERE id = ?", (_ROW_ID,)
            ).fetchone()
        return json.loads(row["overrides_json"]) if row else {}

    def set_overrides(self, overrides: dict) -> dict:
        """Merge `overrides` (field_name -> value) into whatever's already stored —
        a PUT with one field only nudges that field, it doesn't wipe every other
        admin-set override. Returns the full merged set."""
        merged = {**self.get_overrides(), **overrides}
        payload = json.dumps(merged)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO variable_overrides (id, overrides_json) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET overrides_json = excluded.overrides_json",
                (_ROW_ID, payload),
            )
        return merged

    def effective_variables(self) -> Variables:
        """YAML defaults with admin overrides applied on top."""
        defaults, _ = data_loader.load_variables()
        overrides = self.get_overrides()
        return defaults.model_copy(update=overrides) if overrides else defaults
