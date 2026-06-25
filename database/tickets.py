"""Ticket CRUD — all client-scoped queries filter by client_id."""

import streamlit as st
from database.supabase_client import get_client
from utils.cache import cached_query


def create_ticket(data: dict) -> dict | None:
    """Insert a new ticket.

    *data* should include: client_id, store_id, submitted_by, category,
    urgency, description, and optionally equipment_id, estimated_cost, etc.
    """
    try:
        sb = get_client()
        result = sb.table("tickets").insert(data).execute()
        if result.data:
            clear_tickets_cache()
            return result.data[0]
        return None
    except Exception:
        return None


def get_ticket(ticket_id: str) -> dict | None:
    """Fetch a single ticket with joined store and equipment data.

    Submitter name is resolved separately because submitted_by references
    auth.users, not the public users table — PostgREST cannot auto-join across
    that boundary.
    """
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .select("*, stores(store_number, name, phone, city, state, client_id), equipment(name, serial_number, category)")
            .eq("id", ticket_id)
            .single()
            .execute()
        )
        ticket = result.data
        if not ticket:
            return None

        # Resolve submitter full_name from public users table
        submitted_by = ticket.get("submitted_by")
        if submitted_by:
            try:
                user_result = (
                    sb.table("users")
                    .select("full_name")
                    .eq("id", submitted_by)
                    .single()
                    .execute()
                )
                ticket["users"] = user_result.data or {}
            except Exception:
                ticket["users"] = {}

        return ticket
    except Exception:
        return None


@cached_query(ttl=120, default_factory=list)
def get_tickets_for_user(user_id: str) -> list[dict]:
    """Return tickets submitted by or assigned to a specific user."""
    sb = get_client()
    result = (
        sb.table("tickets")
        .select("*, stores(store_number, name, phone)")
        .or_(f"submitted_by.eq.{user_id},assigned_to.eq.{user_id}")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def get_tickets_for_client(client_id: str, filters: dict | None = None, limit: int = 100) -> list[dict]:
    """Return all tickets for a client with optional filtering.

    Supported filter keys: store_id, status, urgency, category,
    submitted_by, assigned_to, exclude_statuses (list/tuple of statuses to
    omit — e.g. for an "open tickets" view).
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
            exclude_statuses=tuple(filters.get("exclude_statuses", ())),
        )
    return _fetch_tickets_for_client(client_id, limit)


@st.cache_data(ttl=120)
def _fetch_tickets_for_client(
    client_id: str, limit: int = 100,
    store_id: str = "", status: str = "", urgency: str = "",
    category: str = "", submitted_by: str = "", assigned_to: str = "",
    exclude_statuses: tuple = (),
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
        if exclude_statuses:
            query = query.not_.in_("status", list(exclude_statuses))
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


def clear_tickets_cache() -> None:
    """Invalidate all cached ticket lists.

    Call after any insert/update/status change so queues (warranty review,
    dashboard, approvals, etc.) reflect the new state immediately instead of
    showing stale rows until the 120s TTL expires.
    """
    _fetch_tickets_for_client.clear()
    get_tickets_for_user.clear()


def update_ticket(ticket_id: str, data: dict) -> dict | None:
    """Update an existing ticket.

    Clears the cached ticket lists on success so status changes are reflected
    immediately across all queues.
    """
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .update(data)
            .eq("id", ticket_id)
            .execute()
        )
        if result.data:
            clear_tickets_cache()
            return result.data[0]
        return None
    except Exception:
        return None


# ------------------------------------------------------------------
# Comments
# ------------------------------------------------------------------

def get_ticket_comments(ticket_id: str) -> list[dict]:
    """Get comments for a ticket, chronological order.

    Wraps the cached helper so errors are never cached as empty lists.
    """
    try:
        return _fetch_ticket_comments(ticket_id)
    except Exception:
        return []


@st.cache_data(ttl=120)
def _fetch_ticket_comments(ticket_id: str) -> list[dict]:
    """Cached comment fetch — raises on error so failures are never cached.

    Resolves commenter names separately (same pattern as get_ticket) to avoid
    the PostgREST cross-schema join issue with auth.users vs public.users.
    """
    sb = get_client()
    result = (
        sb.table("ticket_comments")
        .select("*")
        .eq("ticket_id", ticket_id)
        .order("created_at")
        .execute()
    )
    comments = result.data or []

    # Resolve commenter names in ONE bulk query (not per-comment) — avoids the
    # N+1 round trips while still sidestepping the auth.users/public.users
    # cross-schema join PostgREST can't do.
    user_ids = list({c["user_id"] for c in comments if c.get("user_id")})
    name_map: dict[str, dict] = {}
    if user_ids:
        users_result = (
            sb.table("users")
            .select("id, full_name")
            .in_("id", user_ids)
            .execute()
        )
        name_map = {u["id"]: u for u in (users_result.data or [])}

    for comment in comments:
        comment["users"] = name_map.get(comment.get("user_id"), {})

    return comments


def clear_comments_cache() -> None:
    """Invalidate the comments cache after an add."""
    _fetch_ticket_comments.clear()


@cached_query(ttl=120, default_factory=list)
def get_ticket_photos(ticket_id: str) -> list[dict]:
    """Fetch photos for a ticket."""
    sb = get_client()
    result = (
        sb.table("ticket_photos")
        .select("*")
        .eq("ticket_id", ticket_id)
        .order("uploaded_at")
        .execute()
    )
    return result.data or []


@cached_query(ttl=120, default_factory=list)
def get_ticket_approvals(ticket_id: str) -> list[dict]:
    """Fetch approval records for a ticket with approver names."""
    sb = get_client()
    result = (
        sb.table("approvals")
        .select("*, users:approver_id(full_name)")
        .eq("ticket_id", ticket_id)
        .order("step_order")
        .execute()
    )
    return result.data or []


def add_comment(ticket_id: str, user_id: str, comment: str,
                is_internal: bool = False) -> dict | None:
    """Add a comment to a ticket.

    Parameters
    ----------
    is_internal : bool
        If True the comment is only visible to PSP and elevated client roles.

    Raises on DB error so the caller can surface the real message.
    """
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
