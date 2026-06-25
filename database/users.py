"""User management CRUD — multi-tenant aware."""

import streamlit as st
from database.supabase_client import get_client
from utils.cache import cached_query


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


@st.cache_data(ttl=300)
def _fetch_users_for_client(client_id: str, active_only: bool = True) -> list[dict]:
    """Cached fetch of users for a client. Raises on error (not cached)."""
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


def get_users_for_client(client_id: str, active_only: bool = True) -> list[dict]:
    """Return all users belonging to a specific client org.

    Catches outside the cached helper so a transient failure isn't memoized as
    "no users" (which would silently drop notification recipients for the TTL).
    """
    try:
        return _fetch_users_for_client(client_id, active_only)
    except Exception:
        return []


def clear_users_cache() -> None:
    """Invalidate the users cache so the next call fetches fresh data.

    Call this after creating, updating, or deactivating a user so the
    updated list appears immediately without requiring an app reboot.
    """
    _fetch_users_for_client.clear()


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


def get_psp_users_by_role(psp_role: str, active_only: bool = True) -> list[dict]:
    """Return PSP staff with a specific psp_role (e.g. 'project_manager', 'admin').

    Uses the admin client to bypass RLS — needed for cross-user email lookups.
    """
    try:
        from database.supabase_client import get_admin_client
        sb = get_admin_client()
        query = (
            sb.table("users")
            .select("*")
            .eq("user_tier", "psp")
            .eq("psp_role", psp_role)
            .order("full_name")
        )
        if active_only:
            query = query.eq("is_active", True)
        result = query.execute().data or []
        print(f"[NOTIFY] get_psp_users_by_role({psp_role}) → {len(result)} users found")
        return result
    except Exception as e:
        print(f"[NOTIFY] get_psp_users_by_role({psp_role}) ERROR: {e}")
        return []


@cached_query(ttl=300, default_factory=list)
def get_users_by_role(client_id: str, role: str, active_only: bool = True) -> list[dict]:
    """Return users with a specific client_role within a client org.

    Uses admin client to bypass RLS — needed for notification email lookups.
    Raises on error (caught by cached_query) so failures aren't cached as
    "no recipients".
    """
    from database.supabase_client import get_admin_client
    sb = get_admin_client()
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
