"""Cost estimation from historical ticket data.

Provides statistical cost estimates (min, max, avg, median) based on
completed tickets with recorded actual costs.  No AI/ML libraries —
pure aggregation of past repair data.
"""

import statistics
import streamlit as st
from database.supabase_client import get_client


@st.cache_data(ttl=600)
def estimate_repair_cost(
    client_id: str,
    category: str,
    equipment_type: str | None = None,
    urgency: str | None = None,
) -> dict | None:
    """Look up past completed tickets with actual_cost > 0.

    Parameters
    ----------
    client_id : str
        Tenant scope.
    category : str
        Ticket category (e.g. "BOH", "HVAC").
    equipment_type : str | None
        Equipment name to narrow the search.
    urgency : str | None
        Urgency level (reserved for future weighting; currently unused
        in the query but accepted for forward-compatibility).

    Returns
    -------
    dict | None
        ``{"min", "max", "avg", "median", "count", "low_confidence"}``
        or *None* when no historical data exists at all.
    """
    try:
        costs = _query_costs(client_id, category, equipment_type)

        # If fewer than 3 results with equipment filter, broaden search
        if len(costs) < 3 and equipment_type:
            costs = _query_costs(client_id, category, equipment_type=None)

        if not costs:
            return None

        return {
            "min": min(costs),
            "max": max(costs),
            "avg": round(statistics.mean(costs), 2),
            "median": round(statistics.median(costs), 2),
            "count": len(costs),
            "low_confidence": len(costs) < 3,
        }
    except Exception:
        return None


def _query_costs(
    client_id: str,
    category: str,
    equipment_type: str | None = None,
) -> list[float]:
    """Fetch actual_cost values from completed/closed tickets."""
    try:
        sb = get_client()
        query = (
            sb.table("tickets")
            .select("actual_cost, equipment(name)")
            .eq("client_id", client_id)
            .eq("category", category)
            .in_("status", ["completed", "closed"])
            .gt("actual_cost", 0)
        )

        if equipment_type:
            # We need to filter by joined equipment name; fetch all and
            # filter in Python because PostgREST nested-column filters
            # have limited support.
            result = query.execute()
            rows = result.data or []
            costs = [
                float(r["actual_cost"])
                for r in rows
                if r.get("equipment")
                and r["equipment"].get("name", "").lower() == equipment_type.lower()
            ]
            return costs

        result = query.execute()
        return [float(r["actual_cost"]) for r in (result.data or [])]
    except Exception:
        return []


def get_cost_context(
    client_id: str,
    category: str,
    equipment_type: str | None = None,
) -> str | None:
    """Return a human-readable cost-estimate string for display.

    Returns *None* when there is insufficient data (0 past repairs).
    """
    est = estimate_repair_cost(client_id, category, equipment_type)
    if est is None:
        return None

    count = est["count"]
    low = est["min"]
    high = est["max"]
    avg = est["avg"]

    if count == 1:
        return (
            f"Based on 1 similar repair, the cost was "
            f"${avg:,.0f}"
        )

    confidence_note = " (low confidence)" if est["low_confidence"] else ""
    return (
        f"Based on {count} similar repairs, estimated cost: "
        f"${low:,.0f} - ${high:,.0f} (avg: ${avg:,.0f}){confidence_note}"
    )


def get_cost_estimate_details(
    client_id: str,
    category: str,
    equipment_type: str | None = None,
) -> dict | None:
    """Convenience wrapper returning both the raw estimate and display string.

    Returns ``{"estimate": {...}, "display": "..."}`` or *None*.
    """
    est = estimate_repair_cost(client_id, category, equipment_type)
    if est is None:
        return None
    display = get_cost_context(client_id, category, equipment_type)
    return {"estimate": est, "display": display}
