"""All role/limit decisions live here so new restrictions are added in one place
and the owner/moderator bypass can't be forgotten at a call site."""
from __future__ import annotations

STAFF = {"owner", "moderator"}
ORDINARY = {"free", "pro"}


def is_staff(role: str) -> bool:
    return role in STAFF


def bypasses_limits(role: str) -> bool:
    """Owner and moderators are exempt from every cap and gate."""
    return role in STAFF


def can_use_byok(role: str) -> bool:
    return role in {"pro", "owner", "moderator"}


def daily_cap(role: str, free_cap: int, pro_cap: int) -> int | None:
    """Turns/day on the app's rotating keys. None = unlimited."""
    if bypasses_limits(role):
        return None
    return pro_cap if role == "pro" else free_cap


def can_change_plan(actor_role: str, target_role: str) -> bool:
    """Grant/revoke Pro: staff may do it for ordinary users only (never owner or moderators)."""
    return is_staff(actor_role) and target_role in ORDINARY


def can_set_moderator(actor_role: str, target_role: str, enable: bool) -> bool:
    """Only the owner promotes/demotes moderators; the owner row itself is untouchable."""
    if actor_role != "owner" or target_role == "owner":
        return False
    return (target_role in ORDINARY) if enable else (target_role == "moderator")


def role_after_moderator_removed(plan: str) -> str:
    return "pro" if plan == "pro" else "free"
