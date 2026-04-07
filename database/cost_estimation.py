"""Historical cost estimation helpers — pull min/max/avg from past completed tickets."""

import streamlit as st
from database.supabase_client import get_client


@st.cache_data(ttl=300)
def get_cost_estimate_details(
    client_id: str,
    category: str,
    equipment_name: str | None = None,
) -> dict | None:
    """Return historical cost statistics for similar repairs.

    Returns a dict with an 'estimate' key containing min, max, avg, count,
    and low_confidence (True when fewer than 3 data points).
    Returns None if no historical data exists.
    """
    try:
        sb = get_client()
        query = (
            sb.table("tickets")
            .select("actual_cost")
            .eq("client_id", client_id)
            .eq("category", category)
            .eq("status", "completed")
            .not_.is_("actual_cost", "null")
            .gt("actual_cost", 0)
        )
        result = query.execute()
        costs = [r["actual_cost"] for r in (result.data or []) if r.get("actual_cost")]

        if not costs:
            return None

        avg = sum(costs) / len(costs)
        return {
            "estimate": {
                "min": min(costs),
                "max": max(costs),
                "avg": round(avg, 2),
                "count": len(costs),
                "low_confidence": len(costs) < 3,
            }
        }
    except Exception:
        return None
