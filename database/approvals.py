"""Approval chain and threshold logic — client-scoped."""

from datetime import datetime, timezone
from database.supabase_client import get_client
from config.settings import DEFAULT_APPROVAL_THRESHOLD


def get_approval_config(client_id: str) -> list[dict]:
    """Get the approval chain configuration for a client.

    Returns ordered list of approval steps (role, sequence, etc.).
    """
    try:
        sb = get_client()
        result = (
            sb.table("approval_configs")
            .select("*")
            .eq("client_id", client_id)
            .order("sequence")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def get_threshold(client_id: str) -> float:
    """Return the dollar threshold above which tickets need approval.

    Falls back to the app-level default if no client-specific value is set.
    """
    try:
        sb = get_client()
        result = (
            sb.table("client_settings")
            .select("approval_threshold")
            .eq("client_id", client_id)
            .single()
            .execute()
        )
        if result.data and result.data.get("approval_threshold") is not None:
            return float(result.data["approval_threshold"])
    except Exception:
        pass
    return DEFAULT_APPROVAL_THRESHOLD


def initiate_approval_chain(ticket_id: str, client_id: str,
                            estimated_cost: float) -> list[dict]:
    """Create approval records for a ticket based on the client's config.

    Only creates records when estimated_cost exceeds the client threshold.
    Returns the created approval rows, or an empty list if no approval needed.
    """
    threshold = get_threshold(client_id)
    if estimated_cost <= threshold:
        return []

    config = get_approval_config(client_id)
    if not config:
        # No chain configured — fall back to a single generic approval step
        config = [{"role_level": "admin", "sequence": 1}]

    try:
        sb = get_client()
        rows = []
        for step in config:
            row = {
                "ticket_id": ticket_id,
                "client_id": client_id,
                "role_level": step.get("role_level", "admin"),
                "sequence": step.get("sequence", 1),
                "status": "pending",
            }
            result = sb.table("approvals").insert(row).execute()
            if result.data:
                rows.append(result.data[0])
        return rows
    except Exception:
        return []


def get_pending_approvals(user_id: str) -> list[dict]:
    """Return approval records waiting on this user.

    Matches by the user's client_role against the approval role_level.
    """
    try:
        sb = get_client()
        # First determine the user's role_level
        user = (
            sb.table("users")
            .select("client_id, client_role")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not user.data or not user.data.get("client_role"):
            return []

        role = user.data["client_role"]
        client_id = user.data["client_id"]

        result = (
            sb.table("approvals")
            .select("*, tickets(*, stores(store_number, name))")
            .eq("client_id", client_id)
            .eq("role_level", role)
            .eq("status", "pending")
            .order("created_at")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def approve_ticket(approval_id: str, user_id: str, notes: str = None) -> dict | None:
    """Mark an approval step as approved."""
    try:
        sb = get_client()
        data = {
            "status": "approved",
            "approver_id": user_id,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        if notes:
            data["notes"] = notes
        result = (
            sb.table("approvals")
            .update(data)
            .eq("id", approval_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def reject_ticket(approval_id: str, user_id: str, notes: str = None) -> dict | None:
    """Mark an approval step as rejected."""
    try:
        sb = get_client()
        data = {
            "status": "rejected",
            "approver_id": user_id,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        if notes:
            data["notes"] = notes
        result = (
            sb.table("approvals")
            .update(data)
            .eq("id", approval_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def check_all_approved(ticket_id: str) -> bool:
    """Return True if every approval step for the ticket is approved."""
    try:
        sb = get_client()
        result = (
            sb.table("approvals")
            .select("status")
            .eq("ticket_id", ticket_id)
            .execute()
        )
        if not result.data:
            return False
        return all(row["status"] == "approved" for row in result.data)
    except Exception:
        return False
