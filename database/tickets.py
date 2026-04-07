"""Ticket CRUD — all client-scoped queries filter by client_id."""

import streamlit as st
from database.supabase_client import get_client


def create_ticket(data: dict) -> dict | None:
    """Insert a new ticket.

    *data* should include: client_id, store_id, submitted_by, category,
    urgency, description, and optionally equipment_id, estimated_cost, etc.
    """
    try:
        sb = get_client()
        result = sb.table("tickets").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_ticket(ticket_id: str) -> dict | None:
    """Fetch a single ticket with joined store, submitter, and equipment data."""
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .select("*, stores(store_number, name, phone, client_id), equipment(name, serial_number)")
            .eq("id", ticket_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


@st.cache_data(ttl=120)
def get_tickets_for_user(user_id: str) -> list[dict]:
    """Return tickets submitted by or assigned to a specific user."""
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .select("*, stores(store_number, name, phone)")
            .or_(f"submitted_by.eq.{user_id},assigned_to.eq.{user_id}")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def get_tickets_for_client(client_id: str, filters: dict | None = None, limit: int = 100) -> list[dict]:
    """Return all tickets for a client with optional filtering.

    Supported filter keys: store_id, status, urgency, category,
    submitted_by, assigned_to.
    Delegates to a cached helper with hashable arguments.
    """
    if filters:
        return _fetch_tickets_for_client(
            client_id, limit,
            store_id=filters.get("store_id", ""),
            status=filters.get("status", ""),
            urgency=filters.get("urgency", ""),
            category=filters.get("category", ""),
            submitted_by=filters.get("submitted_by", ""),
            assigned_to=filters.get("assigned_to", ""),
        )
    return _fetch_tickets_for_client(client_id, limit)


@st.cache_data(ttl=120)
def _fetch_tickets_for_client(
    client_id: str, limit: int = 100,
    store_id: str = "", status: str = "", urgency: str = "",
    category: str = "", submitted_by: str = "", assigned_to: str = "",
) -> list[dict]:
    """Cached ticket fetch with hashable parameters."""
    try:
        sb = get_client()
        query = (
            sb.table("tickets")
            .select("*, stores(store_number, name, phone)")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if store_id:
            query = query.eq("store_id", store_id)
        if status:
            query = query.eq("status", status)
        if urgency:
            query = query.eq("urgency", urgency)
        if category:
            query = query.eq("category", category)
        if submitted_by:
            query = query.eq("submitted_by", submitted_by)
        if assigned_to:
            query = query.eq("assigned_to", assigned_to)
        return query.execute().data or []
    except Exception:
        return []


def update_ticket(ticket_id: str, data: dict) -> dict | None:
    """Update an existing ticket."""
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .update(data)
            .eq("id", ticket_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


# ------------------------------------------------------------------
# Comments
# ------------------------------------------------------------------

@st.cache_data(ttl=120)
def get_ticket_comments(ticket_id: str) -> list[dict]:
    """Get comments for a ticket, chronological order."""
    try:
        sb = get_client()
        result = (
            sb.table("ticket_comments")
            .select("*, users(full_name)")
            .eq("ticket_id", ticket_id)
            .order("created_at")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


@st.cache_data(ttl=120)
def get_ticket_photos(ticket_id: str) -> list[dict]:
    """Fetch photos for a ticket."""
    try:
        sb = get_client()
        result = (
            sb.table("ticket_photos")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("uploaded_at")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


@st.cache_data(ttl=120)
def get_ticket_approvals(ticket_id: str) -> list[dict]:
    """Fetch approval records for a ticket with approver names."""
    try:
        sb = get_client()
        result = (
            sb.table("approvals")
            .select("*, users:approver_id(full_name)")
            .eq("ticket_id", ticket_id)
            .order("step_order")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def add_comment(ticket_id: str, user_id: str, comment: str,
                is_internal: bool = False) -> dict | None:
    """Add a comment to a ticket.

    Parameters
    ----------
    is_internal : bool
        If True the comment is only visible to PSP and elevated client roles.
    """
    try:
        sb = get_client()
        result = (
            sb.table("ticket_comments")
            .insert({
                "ticket_id": ticket_id,
                "user_id": user_id,
                "comment": comment,
                "is_internal": is_internal,
            })
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None
