"""Store CRUD — all queries scoped by client_id."""

import streamlit as st
from database.supabase_client import get_client


@st.cache_data(ttl=300)
def get_stores(client_id: str, active_only: bool = True) -> list[dict]:
    """List stores for a client, ordered by store_number."""
    try:
        sb = get_client()
        query = (
            sb.table("stores")
            .select("*")
            .eq("client_id", client_id)
            .order("store_number")
        )
        if active_only:
            query = query.eq("is_active", True)
        return query.execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_store(store_id: str) -> dict | None:
    """Fetch a single store by id."""
    try:
        sb = get_client()
        result = (
            sb.table("stores")
            .select("*")
            .eq("id", store_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def create_store(data: dict) -> dict | None:
    """Insert a new store record.

    *data* should include at minimum: client_id, store_number, name.
    """
    try:
        sb = get_client()
        result = sb.table("stores").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_store(store_id: str, data: dict) -> dict | None:
    """Update an existing store."""
    try:
        sb = get_client()
        result = (
            sb.table("stores")
            .update(data)
            .eq("id", store_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_user_stores(user_id: str) -> list[dict]:
    """Return stores a user oversees (via user_stores junction table)."""
    try:
        sb = get_client()
        result = (
            sb.table("user_stores")
            .select("store_id, stores(*)")
            .eq("user_id", user_id)
            .execute()
        )
        return [row["stores"] for row in (result.data or []) if row.get("stores")]
    except Exception:
        return []


def get_stores_for_user(user, client_id: str) -> list[dict]:
    """Return stores filtered by user role.

    - GM: only their assigned store
    - DM: stores they oversee (from user_stores table) + their home store
    - VP/DOO/Admin/COO/PSP: all stores for the client
    """
    user_tier = user.get("user_tier", "")
    client_role = user.get("client_role", "")

    # PSP users and senior client roles see all stores
    if user_tier == "psp" or client_role in ("admin", "coo", "vp", "doo"):
        return get_stores(client_id)

    stores = []
    user_id = user.get("id", "")

    # GM: only their assigned store
    if client_role == "gm":
        store_id = user.get("store_id")
        if store_id:
            store = get_store(store_id)
            if store:
                stores = [store]
        return stores

    # DM: their overseen stores + home store
    if client_role == "dm":
        stores = get_user_stores(user_id)
        # Also include home store if not already in list
        store_id = user.get("store_id")
        if store_id:
            store_ids = [s["id"] for s in stores]
            if store_id not in store_ids:
                home_store = get_store(store_id)
                if home_store:
                    stores.append(home_store)
        # Sort by store_number
        stores.sort(key=lambda s: s.get("store_number", ""))
        return stores

    # Fallback: all stores
    return get_stores(client_id)
