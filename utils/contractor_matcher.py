"""Geographic + trade matching for contractor selection."""

import streamlit as st
from database.supabase_client import get_client
from database.tenant import get_effective_client_id


def find_matching_contractors(store: dict, category: str) -> list[tuple[dict, str]]:
    """Find contractors that match a store's location and repair category.

    Parameters
    ----------
    store : dict
        Store record with city, state fields.
    category : str
        Repair category (mapped to contractor trade_type).

    Returns
    -------
    list of (contractor_dict, match_type) tuples sorted by:
        1. Preferred flag (preferred first)
        2. Rating (descending)
        3. Geographic match quality (city > state > exception)
    """
    sb = get_client()
    client_id = get_effective_client_id()
    if not client_id:
        return []

    try:
        # 1. Get contractors by trade matching category
        result = (
            sb.table("contractors")
            .select("*")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .execute()
        )
        contractors = result.data or []
    except Exception:
        return []

    # Filter by trade type matching the category
    trade_matched = [
        c for c in contractors
        if _trade_matches_category(c.get("trade_type", ""), category)
    ]

    store_city = (store.get("city") or "").strip().lower()
    store_state = (store.get("state") or "").strip().upper()

    scored = []
    for c in trade_matched:
        c_city = (c.get("city") or "").strip().lower()
        c_state = (c.get("state") or "").strip().upper()

        # 2. Filter by geography: city match > state match > exception
        if c_city and store_city and c_city == store_city:
            match_type = "city"
        elif c_state and store_state and c_state == store_state:
            match_type = "state"
        elif has_geographic_exception(c["id"], store.get("id", "")):
            match_type = "exception"
        else:
            continue  # No geographic match — skip

        scored.append((c, match_type))

    # 3. Rank: preferred first, then rating desc, then geo quality
    geo_rank = {"city": 0, "state": 1, "exception": 2}
    scored.sort(key=lambda pair: (
        0 if pair[0].get("is_preferred") else 1,
        -(pair[0].get("rating") or 0),
        geo_rank.get(pair[1], 99),
    ))

    return scored


def has_geographic_exception(contractor_id: str, store_id: str) -> bool:
    """Check if a contractor has a geographic exception for a given store."""
    if not contractor_id or not store_id:
        return False
    try:
        sb = get_client()
        result = (
            sb.table("contractor_geographic_exceptions")
            .select("id")
            .eq("contractor_id", contractor_id)
            .eq("store_id", store_id)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False


def _trade_matches_category(trade_type: str, category: str) -> bool:
    """Check if a contractor's trade type matches a repair category.

    Uses a simple substring / keyword comparison. Both values are
    lowercased for comparison.
    """
    if not trade_type or not category:
        return False
    trade_lower = trade_type.lower()
    category_lower = category.lower()

    # Direct match
    if trade_lower in category_lower or category_lower in trade_lower:
        return True

    # Keyword mapping — expand as needed
    keyword_map = {
        "boh": ["kitchen", "back of house", "boh", "cooking", "refrigeration"],
        "foh": ["front of house", "foh", "dining", "counter"],
        "hvac": ["hvac", "heating", "cooling", "air conditioning", "ac"],
        "roof": ["roof", "roofing", "leak"],
        "parking lot": ["parking", "lot", "asphalt", "striping"],
        "building exterior": ["exterior", "facade", "siding", "building"],
        "lighting": ["lighting", "light", "bulb", "fixture"],
        "landscaping": ["landscaping", "lawn", "tree", "irrigation"],
        "plumbing": ["plumbing", "pipe", "drain", "water", "toilet", "faucet"],
        "electrical": ["electrical", "wiring", "outlet", "panel", "breaker"],
        "signage": ["sign", "signage", "banner"],
    }

    for trade_key, keywords in keyword_map.items():
        if trade_key in trade_lower:
            if any(kw in category_lower for kw in keywords):
                return True

    return False
