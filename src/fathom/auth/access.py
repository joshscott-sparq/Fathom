"""Access resolution for estimates.

Combines role, ownership, client assignment, and explicit shares into an
AccessContext (can_view/comment/edit). This is the single place estimate
authorization is decided.
"""

from __future__ import annotations

from ..models.org import AccessContext, Permission, Role, User
from ..persistence.directory import SQLiteDirectoryRepository
from ..persistence.store import SQLiteEstimateRepository


def _ctx_from_permission(permission: Permission, reason: str) -> AccessContext:
    return AccessContext(
        can_view=True,
        can_comment=permission.rank() >= Permission.COMMENT.rank(),
        can_edit=permission.rank() >= Permission.EDIT.rank(),
        reason=reason,
    )


def resolve_access(
    user: User,
    estimate_id: str,
    store: SQLiteEstimateRepository,
    directory: SQLiteDirectoryRepository,
) -> AccessContext:
    """Highest permission the user has on the estimate."""
    if user.role is Role.ADMIN:
        return _ctx_from_permission(Permission.EDIT, "admin")

    owner_id, opportunity_id = store.owner_and_opportunity(estimate_id)
    if owner_id and owner_id == user.id:
        return _ctx_from_permission(Permission.EDIT, "owner")

    # Explicit per-estimate share.
    share = directory.share_for(estimate_id, user.email)
    if share is not None:
        return _ctx_from_permission(share, f"shared:{share.value}")

    # Clients get read-only on estimates for their assigned opportunities.
    if user.role is Role.CLIENT and opportunity_id:
        if opportunity_id in directory.visible_opportunity_ids(user.id):
            return _ctx_from_permission(Permission.VIEW, "client-assignment")

    return AccessContext(reason="no-access")


def visible_estimate_filter(user: User, store: SQLiteEstimateRepository,
                            directory: SQLiteDirectoryRepository):
    """Return a predicate(summary) -> bool for list scoping by role."""
    if user.role is Role.ADMIN:
        return lambda summary: True

    if user.role is Role.CLIENT:
        visible = directory.visible_opportunity_ids(user.id)
        return lambda summary: summary.opportunity_id in visible

    # USER: own estimates, plus anything explicitly shared with them.
    shared_ids = _estimates_shared_with(user.email, directory, store)

    def _pred(summary) -> bool:
        return summary.owner_id == user.id or summary.estimate_id in shared_ids

    return _pred


def _estimates_shared_with(email: str, directory: SQLiteDirectoryRepository,
                           store: SQLiteEstimateRepository) -> set[str]:
    ids: set[str] = set()
    for stored in store.all_latest():
        if directory.share_for(stored.estimate_id, email) is not None:
            ids.add(stored.estimate_id)
    return ids
