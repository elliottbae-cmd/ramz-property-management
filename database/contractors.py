"""Contractor CRUD and review management."""

import streamlit as st
from database.supabase_client import get_client


def get_contractors(filters: dict | None = None) -> list[dict]:
    """List contractors with optional trade/state/city filters.

    Supported filter keys: trade, state, city, is_preferred, active_only (bool).
    Delegates to a cached helper with hashable arguments.
    """
    if filters:
        return _fetch_contractors(
            trade=filters.get("trade", ""),
            state=filters.get("state", ""),
            city=filters.get("city", ""),
            is_preferred=filters.get("is_preferred"),
            active_only=filters.get("active_only", True),
        )
    return _fetch_contractors(trade="", state="", city="", is_preferred=None, active_only=True)


@st.cache_data(ttl=300)
def _fetch_contractors(
    trade: str, state: str, city: str,
    is_preferred: bool | None, active_only: bool,
) -> list[dict]:
    """Cached contractor fetch with hashable parameters."""
    try:
        sb = get_client()
        query = (
            sb.table("contractors")
            .select("*")
            .order("is_preferred", desc=True)
            .order("avg_rating", desc=True)
        )

        if active_only:
            query = query.eq("is_active", True)
        if trade:
            query = query.contains("trades", [trade])
        if state:
            query = query.contains("service_states", [state])
        if city:
            query = query.contains("service_cities", [city])
        if is_preferred is not None:
            query = query.eq("is_preferred", is_preferred)

        return query.execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_contractor(contractor_id: str) -> dict | None:
    """Fetch a single contractor record."""
    try:
        sb = get_client()
        result = (
            sb.table("contractors")
            .select("*")
            .eq("id", contractor_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def create_contractor(data: dict) -> dict | None:
    """Insert a new contractor.

    *data* should include: company_name, and optionally trades, phone,
    email, trades, service_cities, service_states, service_zip_codes, etc.
    """
    try:
        sb = get_client()
        result = sb.table("contractors").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_contractor(contractor_id: str, data: dict) -> dict | None:
    """Update an existing contractor."""
    try:
        sb = get_client()
        result = (
            sb.table("contractors")
            .update(data)
            .eq("id", contractor_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


# ------------------------------------------------------------------
# Reviews
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def get_contractor_reviews(contractor_id: str) -> list[dict]:
    """Get reviews for a contractor, newest first."""
    try:
        sb = get_client()
        result = (
            sb.table("contractor_reviews")
            .select("*, users:reviewed_by(full_name)")
            .eq("contractor_id", contractor_id)
            .order("id", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def add_review(data: dict) -> dict | None:
    """Add a review for a contractor and recalculate avg_rating.

    *data* should include: contractor_id, reviewed_by, rating, and optionally
    ticket_id, timeliness, quality, communication, comment.
    """
    try:
        sb = get_client()
        result = sb.table("contractor_reviews").insert(data).execute()

        # Recalculate average rating
        reviews = (
            sb.table("contractor_reviews")
            .select("rating")
            .eq("contractor_id", data["contractor_id"])
            .execute()
            .data
        )
        if reviews:
            avg = sum(r["rating"] for r in reviews) / len(reviews)
            sb.table("contractors").update(
                {"avg_rating": round(avg, 2), "total_jobs": len(reviews)}
            ).eq("id", data["contractor_id"]).execute()

        return result.data[0] if result.data else None
    except Exception:
        return None
