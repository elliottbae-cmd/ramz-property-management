"""Equipment and warranty CRUD."""

import streamlit as st
from database.supabase_client import get_client


@st.cache_data(ttl=300)
def get_equipment(store_id: str, active_only: bool = True) -> list[dict]:
    """List equipment for a store, ordered by name."""
    try:
        sb = get_client()
        query = (
            sb.table("equipment")
            .select("*")
            .eq("store_id", store_id)
            .order("name")
        )
        if active_only:
            query = query.eq("is_active", True)
        return query.execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_equipment_by_id(equip_id: str) -> dict | None:
    """Fetch a single equipment record."""
    try:
        sb = get_client()
        result = (
            sb.table("equipment")
            .select("*, stores(store_number, name, client_id)")
            .eq("id", equip_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_equipment_for_client(client_id: str) -> list[dict]:
    """Get all equipment across all stores for a client, with store info."""
    try:
        sb = get_client()
        result = (
            sb.table("equipment")
            .select("*, stores(id, store_number, name, brand)")
            .eq("stores.client_id", client_id)
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        # Filter out rows where the store join didn't match (client_id filter)
        return [r for r in (result.data or []) if r.get("stores")]
    except Exception:
        return []


def get_equipment_with_details(store_id: str) -> list[dict]:
    """Get equipment for a store with warranty status and open ticket counts.

    Returns equipment rows enriched with 'active_warranty' and 'open_ticket_count'.
    """
    try:
        sb = get_client()
        # Get equipment
        eq_result = (
            sb.table("equipment")
            .select("*")
            .eq("store_id", store_id)
            .eq("is_active", True)
            .order("category, name")
            .execute()
        )
        equipment = eq_result.data or []

        if not equipment:
            return []

        # Check warranties (cached per-item)
        for item in equipment:
            item["active_warranty"] = check_active_warranty(item["id"])

        # Batch-fetch open ticket counts instead of N+1 queries
        eq_ids = [item["id"] for item in equipment]
        try:
            ticket_result = (
                sb.table("tickets")
                .select("equipment_id")
                .in_("equipment_id", eq_ids)
                .not_.in_("status", ["completed", "closed", "rejected"])
                .execute()
            )
            counts: dict[str, int] = {}
            for row in (ticket_result.data or []):
                eid = row.get("equipment_id")
                if eid:
                    counts[eid] = counts.get(eid, 0) + 1
        except Exception:
            counts = {}

        for item in equipment:
            item["open_ticket_count"] = counts.get(item["id"], 0)

        return equipment
    except Exception:
        return []


@st.cache_data(ttl=60)
def get_repair_history(equipment_id: str) -> list[dict]:
    """Get all tickets (repair history) for a specific piece of equipment."""
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .select("*, stores(store_number, name)")
            .eq("equipment_id", equipment_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def create_equipment(data: dict) -> dict | None:
    """Insert a new equipment record.

    *data* should include: store_id, name, category, and optionally
    serial_number, manufacturer, brand, model, install_date, etc.
    """
    try:
        sb = get_client()
        result = sb.table("equipment").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_equipment(equip_id: str, data: dict) -> dict | None:
    """Update an existing equipment record."""
    try:
        sb = get_client()
        result = (
            sb.table("equipment")
            .update(data)
            .eq("id", equip_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def save_manufacture_date(equip_id: str, manufacture_date, decode_method: str = "") -> bool:
    """Save a decoded manufacture date back to the equipment record.

    Parameters
    ----------
    equip_id        : equipment UUID
    manufacture_date: date object or ISO string (YYYY-MM-DD)
    decode_method   : human-readable description of how the date was decoded

    Returns True on success, False on failure.
    """
    try:
        if hasattr(manufacture_date, "isoformat"):
            date_str = manufacture_date.isoformat()
        else:
            date_str = str(manufacture_date)[:10]

        update_equipment(equip_id, {
            "manufacture_date": date_str,
            "serial_decode_method": decode_method or "Decoded from serial number",
        })
        return True
    except Exception:
        return False


# ------------------------------------------------------------------
# Warranty helpers
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def get_warranties(equipment_id: str) -> list[dict]:
    """Get all warranty records for a piece of equipment."""
    try:
        sb = get_client()
        result = (
            sb.table("equipment_warranties")
            .select("*")
            .eq("equipment_id", equipment_id)
            .order("end_date", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


@st.cache_data(ttl=60)
def check_active_warranty(equipment_id: str) -> dict | None:
    """Return the active warranty for an equipment item, or None.

    A warranty is 'active' when today falls between start_date and end_date.
    """
    try:
        sb = get_client()
        result = (
            sb.table("equipment_warranties")
            .select("*")
            .eq("equipment_id", equipment_id)
            .lte("start_date", "now()")
            .gte("end_date", "now()")
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def create_warranty(data: dict) -> dict | None:
    """Insert a new warranty record.

    *data* should include: equipment_id, warranty_provider, start_date, end_date,
    and optionally coverage_description, contact_phone, contact_email.
    """
    try:
        sb = get_client()
        result = sb.table("equipment_warranties").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None
