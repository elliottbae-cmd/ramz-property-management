"""User management CRUD — multi-tenant aware."""

import streamlit as st
from database.supabase_client import get_client


def get_current_user_profile() -> dict | None:
    """Fetch the full user record for the currently authenticated user.

    Uses auth.uid (stored in session_state['user_id']) to look up the
    users table.  Returns None if not logged in or on error.
    """
    user_id = st.session_state.get("user_id")
    if not user_id:
        return None

    try:
        sb = get_client()
        result = (
            sb.table("users")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_users_for_client(client_id: str, active_only: bool = True) -> list[dict]:
    """Return all users belonging to a specific client org."""
    try:
        sb = get_client()
        query = (
            sb.table("users")
            .select("*")
            .eq("client_id", client_id)
            .order("full_name")
        )
        if active_only:
            query = query.eq("is_active", True)
        return query.execute().data or []
    except Exception:
        return []


def create_user_profile(data: dict) -> dict | None:
    """Insert a new row into the users table.

    Expected keys in *data*: id, email, full_name, user_tier,
    and optionally client_id, client_role, psp_role.
    """
    try:
        sb = get_client()
        result = sb.table("users").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_user(user_id: str, data: dict) -> dict | None:
    """Update an existing user profile."""
    try:
        sb = get_client()
        result = (
            sb.table("users")
            .update(data)
            .eq("id", user_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_users_by_role(client_id: str, role: str, active_only: bool = True) -> list[dict]:
    """Return users with a specific client_role within a client org."""
    try:
        sb = get_client()
        query = (
            sb.table("users")
            .select("*")
            .eq("client_id", client_id)
            .eq("client_role", role)
            .order("full_name")
        )
        if active_only:
            query = query.eq("is_active", True)
        return query.execute().data or []
    except Exception:
        return []
