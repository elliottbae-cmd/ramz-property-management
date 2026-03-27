"""Knowledge base (KB) CRUD — tips, troubleshooting guides, and feedback."""

from database.supabase_client import get_client


def get_tips(equipment_type: str | None = None,
             issue_category: str | None = None) -> list[dict]:
    """Find relevant KB tips, optionally filtered by equipment type or category."""
    try:
        sb = get_client()
        query = (
            sb.table("knowledge_base")
            .select("*")
            .eq("is_active", True)
            .order("created_at", desc=True)
        )
        if equipment_type:
            query = query.eq("equipment_type", equipment_type)
        if issue_category:
            query = query.eq("issue_category", issue_category)
        return query.execute().data or []
    except Exception:
        return []


def create_tip(data: dict) -> dict | None:
    """Insert a new KB tip.

    *data* should include: title, content, and optionally equipment_type,
    issue_category, author_id.
    """
    try:
        sb = get_client()
        result = sb.table("knowledge_base").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_tip(tip_id: str, data: dict) -> dict | None:
    """Update an existing KB tip."""
    try:
        sb = get_client()
        result = (
            sb.table("knowledge_base")
            .update(data)
            .eq("id", tip_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


# ------------------------------------------------------------------
# Feedback
# ------------------------------------------------------------------

def record_feedback(data: dict) -> dict | None:
    """Record user feedback (helpful / not helpful) on a KB tip.

    *data* should include: tip_id, user_id, is_helpful (bool), and
    optionally comment.
    """
    try:
        sb = get_client()
        result = sb.table("kb_feedback").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_tip_stats(tip_id: str) -> dict:
    """Return helpful / not-helpful counts for a KB tip.

    Returns {'helpful': int, 'not_helpful': int}.
    """
    try:
        sb = get_client()
        result = (
            sb.table("kb_feedback")
            .select("is_helpful")
            .eq("tip_id", tip_id)
            .execute()
        )
        rows = result.data or []
        helpful = sum(1 for r in rows if r.get("is_helpful"))
        not_helpful = len(rows) - helpful
        return {"helpful": helpful, "not_helpful": not_helpful}
    except Exception:
        return {"helpful": 0, "not_helpful": 0}
