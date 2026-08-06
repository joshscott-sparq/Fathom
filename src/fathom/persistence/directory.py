"""Directory persistence: users, accounts, opportunities, assignments, shares.

SQLite-backed, sharing the estimate database. Seeds a default admin on first use
(credentials from FATHOM_ADMIN_EMAIL / FATHOM_ADMIN_PASSWORD, with a dev
fallback and a warning).
"""

from __future__ import annotations

import os
import sqlite3
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

from ..auth.security import hash_password
from ..models.org import Account, Comment, EstimateShare, Opportunity, Permission, Role, ShareLink, User


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


class SQLiteDirectoryRepository:
    def __init__(self, db_path: str | Path = "fathom.db"):
        self.db_path = str(db_path)
        self._init_schema()
        self._seed_users()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    role TEXT NOT NULL, auth_provider TEXT NOT NULL DEFAULT 'local',
                    password_hash TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, sf_account_id TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, account_id TEXT NOT NULL,
                    sf_opportunity_id TEXT, notion_page_ref TEXT, active_estimate_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS client_assignments (
                    user_id TEXT NOT NULL, account_id TEXT, opportunity_id TEXT
                );
                CREATE TABLE IF NOT EXISTS estimate_shares (
                    estimate_id TEXT NOT NULL, principal_email TEXT NOT NULL, permission TEXT NOT NULL,
                    PRIMARY KEY (estimate_id, principal_email)
                );
                CREATE TABLE IF NOT EXISTS share_links (
                    token TEXT PRIMARY KEY, estimate_id TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS comments (
                    id TEXT PRIMARY KEY, estimate_id TEXT NOT NULL, author TEXT NOT NULL,
                    body TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )

    # One sample login per role for now (documented in the README). Override the
    # admin via FATHOM_ADMIN_EMAIL/PASSWORD; these dev creds must not ship to
    # production as-is.
    SAMPLE_USERS = [
        ("admin@teamsparq.com", "Administrator", Role.ADMIN, "admin123"),
        ("user@teamsparq.com", "Sample User", Role.USER, "user123"),
        ("client@teamsparq.com", "Sample Client", Role.CLIENT, "client123"),
    ]

    def _seed_users(self) -> None:
        with self._connect() as conn:
            if conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]:
                return
        warnings.warn(
            "Seeding sample users with dev passwords (see README). Set "
            "FATHOM_ADMIN_PASSWORD and rotate credentials in production.",
            stacklevel=2,
        )
        admin_email = os.environ.get("FATHOM_ADMIN_EMAIL", "admin@teamsparq.com")
        admin_password = os.environ.get("FATHOM_ADMIN_PASSWORD", "admin123")
        self.create_user(email=admin_email, name="Administrator", role=Role.ADMIN, password=admin_password)
        for email, name, role, password in self.SAMPLE_USERS[1:]:
            self.create_user(email=email, name=name, role=role, password=password)

    # --- Users ---

    def create_user(self, *, email: str, name: str, role: Role, password: str | None = None,
                    auth_provider: str = "local") -> User:
        user_id = _id()
        now = _now()
        pw_hash = hash_password(password) if password else None
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users (id, email, name, role, auth_provider, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, email.lower(), name, role.value, auth_provider, pw_hash, now),
            )
        return User(id=user_id, email=email.lower(), name=name, role=role, auth_provider=auth_provider, created_at=now)

    def get_user(self, user_id: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._to_user(row) if row else None

    def get_user_by_email(self, email: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return self._to_user(row) if row else None

    def password_hash_for(self, email: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return row["password_hash"] if row else None

    def list_users(self) -> list[User]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [self._to_user(r) for r in rows]

    def set_role(self, user_id: str, role: Role) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role.value, user_id))

    def upsert_oauth_user(self, *, email: str, name: str, provider: str) -> User:
        existing = self.get_user_by_email(email)
        if existing:
            return existing
        # New OIDC users default to the USER role; an admin can elevate them.
        return self.create_user(email=email, name=name, role=Role.USER, auth_provider=provider)

    # --- Accounts ---

    def create_account(self, name: str, sf_account_id: str | None = None) -> Account:
        acc = Account(id=_id(), name=name, sf_account_id=sf_account_id, created_at=_now())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO accounts (id, name, sf_account_id, created_at) VALUES (?, ?, ?, ?)",
                (acc.id, acc.name, acc.sf_account_id, acc.created_at),
            )
        return acc

    def list_accounts(self) -> list[Account]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()
        return [Account(**dict(r)) for r in rows]

    def get_account(self, account_id: str) -> Account | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return Account(**dict(row)) if row else None

    # --- Opportunities ---

    def create_opportunity(self, *, name: str, account_id: str, sf_opportunity_id: str | None = None,
                           notion_page_ref: str | None = None) -> Opportunity:
        opp = Opportunity(id=_id(), name=name, account_id=account_id, sf_opportunity_id=sf_opportunity_id,
                          notion_page_ref=notion_page_ref, active_estimate_id=None, created_at=_now())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO opportunities (id, name, account_id, sf_opportunity_id, notion_page_ref, "
                "active_estimate_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (opp.id, opp.name, opp.account_id, opp.sf_opportunity_id, opp.notion_page_ref, None, opp.created_at),
            )
        return opp

    def list_opportunities(self, account_id: str | None = None) -> list[Opportunity]:
        with self._connect() as conn:
            if account_id:
                rows = conn.execute("SELECT * FROM opportunities WHERE account_id = ? ORDER BY name", (account_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM opportunities ORDER BY name").fetchall()
        return [Opportunity(**dict(r)) for r in rows]

    def get_opportunity(self, opp_id: str) -> Opportunity | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
        return Opportunity(**dict(row)) if row else None

    def set_active_estimate(self, opp_id: str, estimate_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE opportunities SET active_estimate_id = ? WHERE id = ?", (estimate_id, opp_id))

    def set_notion_ref(self, opp_id: str, ref: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE opportunities SET notion_page_ref = ? WHERE id = ?", (ref, opp_id))

    # --- Client assignments ---

    def assign_client(self, user_id: str, *, account_id: str | None = None, opportunity_id: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO client_assignments (user_id, account_id, opportunity_id) VALUES (?, ?, ?)",
                (user_id, account_id, opportunity_id),
            )

    def visible_opportunity_ids(self, user_id: str) -> set[str]:
        """Opportunities a client can see: assigned directly or via their accounts."""
        with self._connect() as conn:
            rows = conn.execute("SELECT account_id, opportunity_id FROM client_assignments WHERE user_id = ?", (user_id,)).fetchall()
            account_ids = {r["account_id"] for r in rows if r["account_id"]}
            opp_ids = {r["opportunity_id"] for r in rows if r["opportunity_id"]}
            for acc_id in account_ids:
                for opp in conn.execute("SELECT id FROM opportunities WHERE account_id = ?", (acc_id,)).fetchall():
                    opp_ids.add(opp["id"])
        return opp_ids

    # --- Shares ---

    def add_share(self, estimate_id: str, principal_email: str, permission: Permission) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO estimate_shares (estimate_id, principal_email, permission) VALUES (?, ?, ?) "
                "ON CONFLICT(estimate_id, principal_email) DO UPDATE SET permission = excluded.permission",
                (estimate_id, principal_email.lower(), permission.value),
            )

    def remove_share(self, estimate_id: str, principal_email: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM estimate_shares WHERE estimate_id = ? AND principal_email = ?",
                         (estimate_id, principal_email.lower()))

    def list_shares(self, estimate_id: str) -> list[EstimateShare]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM estimate_shares WHERE estimate_id = ?", (estimate_id,)).fetchall()
        return [EstimateShare(estimate_id=r["estimate_id"], principal_email=r["principal_email"],
                              permission=Permission(r["permission"])) for r in rows]

    def share_for(self, estimate_id: str, email: str) -> Permission | None:
        with self._connect() as conn:
            row = conn.execute("SELECT permission FROM estimate_shares WHERE estimate_id = ? AND principal_email = ?",
                               (estimate_id, email.lower())).fetchone()
        return Permission(row["permission"]) if row else None

    # --- Public share links ---

    def create_share_link(self, estimate_id: str, created_by: str) -> ShareLink:
        token = uuid.uuid4().hex
        link = ShareLink(token=token, estimate_id=estimate_id, created_by=created_by, created_at=_now())
        with self._connect() as conn:
            conn.execute("INSERT INTO share_links (token, estimate_id, created_by, created_at) VALUES (?, ?, ?, ?)",
                         (link.token, link.estimate_id, link.created_by, link.created_at))
        return link

    def get_share_link(self, token: str) -> ShareLink | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM share_links WHERE token = ?", (token,)).fetchone()
        return ShareLink(**dict(row)) if row else None

    def list_share_links(self, estimate_id: str) -> list[ShareLink]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM share_links WHERE estimate_id = ?", (estimate_id,)).fetchall()
        return [ShareLink(**dict(r)) for r in rows]

    def revoke_share_link(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM share_links WHERE token = ?", (token,))

    # --- Comments ---

    def add_comment(self, estimate_id: str, author: str, body: str) -> Comment:
        comment = Comment(id=_id(), estimate_id=estimate_id, author=author, body=body, created_at=_now())
        with self._connect() as conn:
            conn.execute("INSERT INTO comments (id, estimate_id, author, body, created_at) VALUES (?, ?, ?, ?, ?)",
                         (comment.id, comment.estimate_id, comment.author, comment.body, comment.created_at))
        return comment

    def list_comments(self, estimate_id: str) -> list[Comment]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM comments WHERE estimate_id = ? ORDER BY created_at", (estimate_id,)).fetchall()
        return [Comment(**dict(r)) for r in rows]

    @staticmethod
    def _to_user(row: sqlite3.Row) -> User:
        return User(id=row["id"], email=row["email"], name=row["name"], role=Role(row["role"]),
                    auth_provider=row["auth_provider"], created_at=row["created_at"])
