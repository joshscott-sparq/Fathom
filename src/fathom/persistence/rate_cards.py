"""Persisted rate cards (spec §2.6).

Multiple named rate cards can be saved; exactly one is active at a time and one is
the default. The default is seeded from the committed placeholder pricing file so
the app always has a working card. Each card holds (discipline, tier, location,
day_rate) rows. Stored in the same SQLite database as estimates.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .. import data_loader
from ..models.enums import Location
from ..models.team import RateRow


@dataclass
class SavedRateCard:
    id: str
    name: str
    is_default: bool
    is_active: bool
    created_at: str
    rows: list[RateRow]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows_to_json(rows: list[RateRow]) -> str:
    return json.dumps([
        {"discipline": r.discipline, "tier": r.tier, "location": r.location.value, "day_rate": r.day_rate}
        for r in rows
    ])


def _rows_from_json(payload: str) -> list[RateRow]:
    return [
        RateRow(discipline=d["discipline"], tier=d["tier"], location=Location(d["location"]), day_rate=d["day_rate"])
        for d in json.loads(payload)
    ]


class SQLiteRateCardRepository:
    """SQLite-backed rate-card store. Seeds a default card on first use."""

    def __init__(self, db_path: str | Path = "fathom.db"):
        self.db_path = str(db_path)
        self._init_schema()
        self._seed_default()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_cards (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    rows_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _seed_default(self) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM rate_cards").fetchone()
            if row["n"]:
                return
        rows, version, _ = data_loader.load_pricing()
        card_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO rate_cards (id, name, is_default, is_active, rows_json, created_at) VALUES (?, ?, 1, 1, ?, ?)",
                (card_id, f"Example rates (placeholder v{version})", _rows_to_json(rows), _now()),
            )

    def list_cards(self) -> list[SavedRateCard]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM rate_cards ORDER BY is_default DESC, created_at").fetchall()
        return [self._to_card(r) for r in rows]

    def get(self, card_id: str) -> SavedRateCard | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM rate_cards WHERE id = ?", (card_id,)).fetchone()
        return self._to_card(row) if row else None

    def active_card(self) -> SavedRateCard:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM rate_cards WHERE is_active = 1").fetchone()
            if row is None:
                row = conn.execute("SELECT * FROM rate_cards WHERE is_default = 1").fetchone()
        return self._to_card(row)

    def create(self, name: str, rows: list[RateRow], activate: bool = True) -> SavedRateCard:
        card_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            if activate:
                conn.execute("UPDATE rate_cards SET is_active = 0")
            conn.execute(
                "INSERT INTO rate_cards (id, name, is_default, is_active, rows_json, created_at) VALUES (?, ?, 0, ?, ?, ?)",
                (card_id, name, 1 if activate else 0, _rows_to_json(rows), _now()),
            )
        return self.get(card_id)

    def update_rows(self, card_id: str, rows: list[RateRow]) -> SavedRateCard:
        if self.get(card_id) is None:
            raise KeyError(f"rate card {card_id!r} not found")
        with self._connect() as conn:
            conn.execute("UPDATE rate_cards SET rows_json = ? WHERE id = ?", (_rows_to_json(rows), card_id))
        return self.get(card_id)

    def activate(self, card_id: str) -> SavedRateCard:
        if self.get(card_id) is None:
            raise KeyError(f"rate card {card_id!r} not found")
        with self._connect() as conn:
            conn.execute("UPDATE rate_cards SET is_active = 0")
            conn.execute("UPDATE rate_cards SET is_active = 1 WHERE id = ?", (card_id,))
        return self.get(card_id)

    def delete(self, card_id: str) -> None:
        card = self.get(card_id)
        if card is None:
            raise KeyError(f"rate card {card_id!r} not found")
        if card.is_default:
            raise ValueError("cannot delete the default rate card")
        with self._connect() as conn:
            conn.execute("DELETE FROM rate_cards WHERE id = ?", (card_id,))
            # If we deleted the active card, reactivate the default.
            if card.is_active:
                conn.execute("UPDATE rate_cards SET is_active = 1 WHERE is_default = 1")

    @staticmethod
    def _to_card(row: sqlite3.Row) -> SavedRateCard:
        return SavedRateCard(
            id=row["id"],
            name=row["name"],
            is_default=bool(row["is_default"]),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            rows=_rows_from_json(row["rows_json"]),
        )
