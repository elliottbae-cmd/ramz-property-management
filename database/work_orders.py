"""Work order CRUD — client-scoped."""

from database.supabase_client import get_client


def create_work_order(data: dict) -> dict | None:
    """Insert a new work order.

    *data* should include: ticket_id, client_id, contractor_id, and
    optionally amount, notes, scheduled_date, etc.
    """
    try:
        sb = get_client()
        result = sb.table("work_orders").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_work_orders(client_id: str, ticket_id: str | None = None) -> list[dict]:
    """List work orders for a client, optionally filtered to a ticket."""
    try:
        sb = get_client()
        query = (
            sb.table("work_orders")
            .select(
                "*, contractors(company_name, phone, email), "
                "tickets(ticket_number, store_id)"
            )
            .eq("client_id", client_id)
            .order("issued_at", desc=True)
        )
        if ticket_id:
            query = query.eq("ticket_id", ticket_id)
        return query.execute().data or []
    except Exception:
        return []


def get_work_order(wo_id: str) -> dict | None:
    """Fetch a single work order with contractor and ticket details."""
    try:
        sb = get_client()
        result = (
            sb.table("work_orders")
            .select(
                "*, contractors(company_name, phone, email), "
                "tickets(ticket_number, store_id, description)"
            )
            .eq("id", wo_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def update_work_order(wo_id: str, data: dict) -> dict | None:
    """Update a work order (status, amount, completion notes, etc.)."""
    try:
        sb = get_client()
        result = (
            sb.table("work_orders")
            .update(data)
            .eq("id", wo_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None
