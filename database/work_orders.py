"""Work order CRUD operations."""

import streamlit as st
from database.supabase_client import get_client


def create_work_order(data: dict) -> dict | None:
    """Insert a new work order.

    data should include: ticket_id, client_id, contractor_id, amount,
    and optionally notes, status (defaults to 'issued').
    """
    try:
        sb = get_client()
        if "status" not in data:
            data["status"] = "issued"
        result = sb.table("work_orders").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


@st.cache_data(ttl=60)
def get_work_orders(client_id: str, ticket_id: str | None = None) -> list[dict]:
    """Fetch work orders for a client, optionally filtered by ticket."""
    try:
        sb = get_client()
        query = (
            sb.table("work_orders")
            .select("*, contractors(company_name, phone, email)")
            .eq("client_id", client_id)
            .order("issued_at", desc=True)
        )
        if ticket_id:
            query = query.eq("ticket_id", ticket_id)
        result = query.execute()
        return result.data or []
    except Exception:
        return []


def update_work_order(work_order_id: str, data: dict) -> dict | None:
    """Update a work order."""
    try:
        sb = get_client()
        result = (
            sb.table("work_orders")
            .update(data)
            .eq("id", work_order_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None
