"""Audit log — records all significant actions per client."""

from datetime import datetime, timezone
from database.supabase_client import get_client


def log_action(client_id: str, user_id: str, action: str,
               entity_type: str, entity_id: str,
               details: dict | None = None) -> dict | None:
    """Insert an audit log entry.

    Parameters
    ----------
    action : str
        Short verb, e.g. 'create', 'update', 'approve', 'reject', 'delete'.
    entity_type : str
        Table/entity name, e.g. 'ticket', 'work_order', 'equipment'.
    entity_id : str
        Primary key of the affected record.
    details : dict | None
        Optional JSON blob with before/after data or context.
    """
    try:
        sb = get_client()
        row = {
            "client_id": client_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = sb.table("audit_log").insert(row).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_audit_log(client_id: str, filters: dict | None = None) -> list[dict]:
    """Read the audit log for a client with optional filters.

    Supported filter keys: user_id, action, entity_type, entity_id,
    start_date, end_date, limit (int, default 100).
    """
    try:
        sb = get_client()
        query = (
            sb.table("audit_log")
            .select("*, users(full_name)")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
        )

        if filters:
            if filters.get("user_id"):
                query = query.eq("user_id", filters["user_id"])
            if filters.get("action"):
                query = query.eq("action", filters["action"])
            if filters.get("entity_type"):
                query = query.eq("entity_type", filters["entity_type"])
            if filters.get("entity_id"):
                query = query.eq("entity_id", filters["entity_id"])
            if filters.get("start_date"):
                query = query.gte("created_at", filters["start_date"])
            if filters.get("end_date"):
                query = query.lte("created_at", filters["end_date"])

            limit = filters.get("limit", 100)
        else:
            limit = 100

        query = query.limit(limit)
        return query.execute().data or []
    except Exception:
        return []
