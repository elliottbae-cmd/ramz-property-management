"""Equipment and warranty CRUD."""

from database.supabase_client import get_client


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


# ------------------------------------------------------------------
# Warranty helpers
# ------------------------------------------------------------------

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
