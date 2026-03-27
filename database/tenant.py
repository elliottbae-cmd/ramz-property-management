"""Client (tenant) context manager for multi-tenant operations."""

import streamlit as st
from database.supabase_client import get_client


def get_effective_client_id() -> str | None:
    """Return the active client_id for the current session.

    - Client-tier users always use their own client_id.
    - PSP-tier users use whichever client they have selected via switch_client().
    """
    return st.session_state.get("effective_client_id")


def switch_client(client_id: str) -> dict | None:
    """Switch the active client context (PSP users only).

    Validates that the PSP user has access to the requested client via
    the psp_client_access table, then updates session state.

    Returns the client record on success, None on failure.
    """
    user = st.session_state.get("user_profile")
    if not user or user.get("user_tier") != "psp":
        return None

    try:
        sb = get_client()
        # Verify PSP user has access to this client
        access = (
            sb.table("psp_client_access")
            .select("id")
            .eq("psp_user_id", user["id"])
            .eq("client_id", client_id)
            .execute()
        )
        if not access.data:
            return None

        # Fetch client record
        client_record = (
            sb.table("clients")
            .select("*")
            .eq("id", client_id)
            .single()
            .execute()
        )
        st.session_state["effective_client_id"] = client_id
        st.session_state["current_client"] = client_record.data
        return client_record.data
    except Exception:
        return None


def get_current_client() -> dict | None:
    """Return the full client record for the active tenant context.

    Caches the result in session state so repeated calls in the same
    request don't hit the database.
    """
    # Return cached copy if available
    cached = st.session_state.get("current_client")
    if cached:
        return cached

    client_id = get_effective_client_id()
    if not client_id:
        return None

    try:
        sb = get_client()
        result = (
            sb.table("clients")
            .select("*")
            .eq("id", client_id)
            .single()
            .execute()
        )
        st.session_state["current_client"] = result.data
        return result.data
    except Exception:
        return None


def get_all_clients() -> list[dict]:
    """Return all clients the current PSP user has access to.

    For PSP admins this may be every client; for other PSP roles it is
    filtered through psp_client_access.
    """
    user = st.session_state.get("user_profile")
    if not user or user.get("user_tier") != "psp":
        return []

    try:
        sb = get_client()

        # PSP admin sees everything
        if user.get("psp_role") == "admin":
            result = (
                sb.table("clients")
                .select("*")
                .order("name")
                .execute()
            )
            return result.data or []

        # Other PSP roles see only their assigned clients
        access = (
            sb.table("psp_client_access")
            .select("client_id, clients(*)")
            .eq("psp_user_id", user["id"])
            .execute()
        )
        return [row["clients"] for row in (access.data or []) if row.get("clients")]
    except Exception:
        return []
