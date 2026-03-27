"""Reporting queries — client-scoped analytics."""

from database.supabase_client import get_client


def get_store_metrics(client_id: str, store_id: str | None = None,
                      date_range: tuple | None = None) -> list[dict]:
    """Get ticket counts and spend for stores within a client.

    Parameters
    ----------
    date_range : tuple | None
        (start_date_iso, end_date_iso) strings. Filters tickets.created_at.
    """
    try:
        sb = get_client()
        query = (
            sb.table("tickets")
            .select(
                "store_id, stores(store_number, name), "
                "actual_cost, estimated_cost, status, urgency, created_at"
            )
            .eq("client_id", client_id)
        )
        if store_id:
            query = query.eq("store_id", store_id)
        if date_range:
            start, end = date_range
            query = query.gte("created_at", start).lte("created_at", end)
        return query.execute().data or []
    except Exception:
        return []


def get_client_summary(client_id: str, date_range: tuple | None = None) -> dict:
    """Aggregate metrics for a client: total tickets, spend, open count.

    Returns a dict with keys: total_tickets, open_tickets, total_spend,
    avg_cost.
    """
    try:
        sb = get_client()

        # Total tickets
        total_query = (
            sb.table("tickets")
            .select("id", count="exact")
            .eq("client_id", client_id)
        )
        if date_range:
            total_query = total_query.gte("created_at", date_range[0]).lte("created_at", date_range[1])
        total_result = total_query.execute()
        total_tickets = total_result.count or 0

        # Open tickets
        open_result = (
            sb.table("tickets")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .in_("status", ["submitted", "troubleshooting", "warranty_check", "pending_approval", "approved", "assigned", "in_progress"])
            .execute()
        )
        open_tickets = open_result.count or 0

        # Spend on completed/closed tickets
        spend_query = (
            sb.table("tickets")
            .select("actual_cost")
            .eq("client_id", client_id)
            .in_("status", ["completed", "closed"])
        )
        if date_range:
            spend_query = spend_query.gte("created_at", date_range[0]).lte("created_at", date_range[1])
        spend_data = spend_query.execute().data or []

        costs = [row["actual_cost"] for row in spend_data if row.get("actual_cost")]
        total_spend = sum(costs)
        avg_cost = total_spend / len(costs) if costs else 0

        return {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "total_spend": round(total_spend, 2),
            "avg_cost": round(avg_cost, 2),
        }
    except Exception:
        return {
            "total_tickets": 0,
            "open_tickets": 0,
            "total_spend": 0.0,
            "avg_cost": 0.0,
        }


def get_resolution_times(client_id: str) -> list[dict]:
    """Return tickets with their resolution duration for avg-time analysis.

    Only includes completed/closed tickets that have both created_at and
    resolved_at timestamps.
    """
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .select("id, ticket_number, created_at, resolved_at, category, urgency")
            .eq("client_id", client_id)
            .in_("status", ["completed", "closed"])
            .not_.is_("resolved_at", "null")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def get_urgency_breakdown(client_id: str) -> dict:
    """Return ticket counts grouped by urgency level.

    Returns a dict like {'low': 12, 'medium': 8, 'high': 3, 'emergency': 1}.
    """
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .select("urgency")
            .eq("client_id", client_id)
            .execute()
        )
        breakdown: dict[str, int] = {}
        for row in (result.data or []):
            level = row.get("urgency", "unknown")
            breakdown[level] = breakdown.get(level, 0) + 1
        return breakdown
    except Exception:
        return {}
