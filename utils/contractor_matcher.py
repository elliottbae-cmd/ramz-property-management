"""Geographic + trade matching for contractor selection."""

import streamlit as st
from database.supabase_client import get_client
from database.tenant import get_effective_client_id


def find_matching_contractors(
    store: dict,
    category: str,
    equipment_name: str = "",
) -> list[tuple[dict, str]]:
    """Find contractors that match a store's location and repair category.

    Parameters
    ----------
    store : dict
        Store record with city, state, zip_code fields.
    category : str
        Repair category (e.g. "BOH (Back of House)").
    equipment_name : str, optional
        Specific equipment name (e.g. "Fryer", "Walk-in Cooler"). When
        provided this is used as the primary trade match term; category
        is used as a fallback so we never return zero results purely due
        to a missing equipment name.

    Returns
    -------
    list of (contractor_dict, match_type) tuples sorted by:
        1. Preferred flag (preferred first)
        2. Rating (descending)
        3. Geographic match quality (city > zip > state > exception)
    """
    sb = get_client()

    try:
        result = (
            sb.table("contractors")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        contractors = result.data or []
    except Exception:
        return []

    # Match on equipment name first (more specific), fall back to category
    def _matches(trades):
        if equipment_name and _trade_matches_category(trades, equipment_name):
            return True
        return _trade_matches_category(trades, category)

    trade_matched = [c for c in contractors if _matches(c.get("trades", []))]

    store_city = (store.get("city") or "").strip().lower()
    store_state = (store.get("state") or "").strip().upper()
    store_zip = (store.get("zip_code") or "").strip()

    scored = []
    for c in trade_matched:
        service_cities = [city.strip().lower() for city in (c.get("service_cities") or [])]
        service_states = [st_code.strip().upper() for st_code in (c.get("service_states") or [])]
        service_zips = [z.strip() for z in (c.get("service_zip_codes") or [])]

        # Filter by geography: city match > zip match > state match > exception
        if store_city and store_city in service_cities:
            match_type = "city"
        elif store_zip and store_zip in service_zips:
            match_type = "zip"
        elif store_state and store_state in service_states:
            match_type = "state"
        elif has_geographic_exception(c["id"], store.get("id", "")):
            match_type = "exception"
        else:
            continue  # No geographic match — skip

        scored.append((c, match_type))

    # Rank: preferred first, then rating desc, then geo quality
    geo_rank = {"city": 0, "zip": 1, "state": 2, "exception": 3}
    scored.sort(key=lambda pair: (
        0 if pair[0].get("is_preferred") else 1,
        -(pair[0].get("avg_rating") or 0),
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


def _trade_matches_category(trades: list, category: str) -> bool:
    """Check if a contractor's trades list matches a repair category.

    Uses a simple substring / keyword comparison. Both values are
    lowercased for comparison.
    """
    if not trades or not category:
        return False
    category_lower = category.lower()

    for trade in (trades if isinstance(trades, list) else [trades]):
        trade_lower = str(trade).lower()

        # Direct match
        if trade_lower in category_lower or category_lower in trade_lower:
            return True

        # Keyword mapping — trade keyword → what it covers
        keyword_map = {
            # BOH cooking equipment
            "cooking": ["fryer", "oven", "grill", "griddle", "broiler", "range", "steamer",
                        "warmer", "hot holding", "cooking", "boh", "back of house", "kitchen"],
            "refrigeration": ["walk-in", "cooler", "freezer", "refrigerator", "reach-in",
                              "cold storage", "refrigeration", "ice cream", "custard"],
            "ice": ["ice machine", "ice maker", "ice", "hoshizaki", "manitowoc", "scotsman"],
            "warewashing": ["dishwasher", "dish machine", "warewash", "dish", "sanitizer"],
            "beverage": ["beverage", "soda", "fountain", "coffee", "espresso", "tea"],
            # FOH / building
            "foh": ["front of house", "foh", "dining", "counter", "pos", "register"],
            # Building systems
            "hvac": ["hvac", "heating", "cooling", "air conditioning", "ac", "heat",
                     "ventilation", "exhaust", "hood", "make-up air"],
            "plumbing": ["plumbing", "pipe", "drain", "water", "toilet", "faucet",
                         "grease trap", "sink", "leak", "sewer"],
            "electrical": ["electrical", "wiring", "outlet", "panel", "breaker",
                           "lighting", "light", "fixture", "bulb", "sign", "signage"],
            # Exterior
            "roofing": ["roof", "roofing", "leak", "membrane", "flashing"],
            "parking lot": ["parking", "lot", "asphalt", "paving", "striping", "curb"],
            "building exterior": ["exterior", "facade", "siding", "building", "window",
                                  "door", "glass", "caulk"],
            "landscaping": ["landscaping", "lawn", "tree", "irrigation", "sprinkler"],
            # General
            "general": ["general", "handyman", "maintenance", "repair"],
        }

        for trade_key, keywords in keyword_map.items():
            if trade_key in trade_lower:
                if any(kw in category_lower for kw in keywords):
                    return True

    return False
