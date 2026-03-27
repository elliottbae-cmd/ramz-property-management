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
