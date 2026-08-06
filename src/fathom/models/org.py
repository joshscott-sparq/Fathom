"""Organization and access models: users, accounts, opportunities, sharing.

Access hierarchy: Account -> Opportunity -> Estimate. An opportunity has many
estimates but one active/official one. Users have a role; clients are linked to
accounts/opportunities and are read-only. Estimates can also be shared at
edit/comment/view, and exposed via public view-only links.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    ADMIN = "admin"    # manage/access everything, plus users/accounts/opportunities
    USER = "user"      # sees only own estimates; training uses all history
    CLIENT = "client"  # read-only for assigned opportunities


class Permission(str, Enum):
    """Share permission level on a single estimate."""

    EDIT = "edit"
    COMMENT = "comment"
    VIEW = "view"

    def rank(self) -> int:
        return {"view": 1, "comment": 2, "edit": 3}[self.value]


class User(BaseModel):
    """Public user record (never carries the password hash)."""

    id: str
    email: str
    name: str
    role: Role = Role.USER
    auth_provider: str = Field(default="local", description="local | google | jumpcloud")
    created_at: str


class Account(BaseModel):
    id: str
    name: str
    sf_account_id: str | None = Field(default=None, description="Salesforce Account Id.")
    created_at: str


class Opportunity(BaseModel):
    id: str
    name: str
    account_id: str
    sf_opportunity_id: str | None = Field(default=None, description="Salesforce Opportunity Id.")
    notion_page_ref: str | None = Field(
        default=None, description="Notion page id/URL for opportunity notes."
    )
    active_estimate_id: str | None = Field(
        default=None, description="The one official estimate for this opportunity."
    )
    created_at: str


class EstimateShare(BaseModel):
    """A per-principal share on an estimate."""

    estimate_id: str
    principal_email: str
    permission: Permission


class ShareLink(BaseModel):
    """A public view-only link token for an estimate (no login required)."""

    token: str
    estimate_id: str
    created_by: str
    created_at: str


class Comment(BaseModel):
    id: str
    estimate_id: str
    author: str
    body: str
    created_at: str


class AccessContext(BaseModel):
    """Resolved access for a viewer on an estimate."""

    can_view: bool = False
    can_comment: bool = False
    can_edit: bool = False
    reason: str = ""
