"""Persisted t-shirt scale overrides (D31 — org-wide only, no per-estimate tier;
see DECISIONS.md D31's scoping note: sizing convention, not a per-deal lever).

Same shape as `persistence/variables.py`: a single row of admin-set overrides,
sparse per size (only sizes an admin has touched), merged with
`data_loader.load_tshirt_scale()`'s defaults fresh on every read.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .. import data_loader

_ROW_ID = "global"


class SQLiteTshirtScaleRepository:
    """SQLite-backed store for org-wide t-shirt scale overrides."""

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
                CREATE TABLE IF NOT EXISTS tshirt_scale_overrides (
                    id TEXT PRIMARY KEY,
                    overrides_json TEXT NOT NULL
                );
                """
            )

    def get_overrides(self) -> dict:
        """size -> {epic/feature/story -> points}, sparse."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT overrides_json FROM tshirt_scale_overrides WHERE id = ?", (_ROW_ID,)
            ).fetchone()
        return json.loads(row["overrides_json"]) if row else {}

    def set_overrides(self, overrides: dict) -> dict:
        """Merge `overrides` (size -> {level -> points}) into what's stored,
        merging within a size too (setting one level doesn't drop another
        already-overridden level for that same size)."""
        existing = self.get_overrides()
        merged = {**existing}
        for size, levels in overrides.items():
            merged[size] = {**existing.get(size, {}), **levels}
        payload = json.dumps(merged)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tshirt_scale_overrides (id, overrides_json) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET overrides_json = excluded.overrides_json",
                (_ROW_ID, payload),
            )
        return merged

    def effective_scale(self) -> dict[str, dict[str, float]]:
        """YAML defaults with admin overrides applied on top, per size."""
        defaults, _ = data_loader.load_tshirt_scale()
        overrides = self.get_overrides()
        if not overrides:
            return defaults
        merged = {size: dict(levels) for size, levels in defaults.items()}
        for size, levels in overrides.items():
            merged.setdefault(size, {}).update(levels)
        return merged
