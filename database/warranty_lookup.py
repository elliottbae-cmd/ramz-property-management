"""AI-powered warranty lookup using Tavily web search + Claude API.

Three-step process:
1. Check our equipment_warranties table first.
2. If nothing on file, use Tavily to search the web for warranty info,
   then feed results to Claude for structured extraction.
3. Return structured results with a recommendation.
"""

import hashlib
from config.settings import _get_secret
import json
import os
import re
from datetime import datetime, date

import streamlit as st
from database.supabase_client import get_client
from database.equipment import check_active_warranty, get_warranties


# ------------------------------------------------------------------
# In-memory cache for Tavily+Claude results (keyed on equipment data)
# ------------------------------------------------------------------
_warranty_cache: dict[str, dict] = {}


def _cache_key(equipment_data: dict) -> str:
    """Build a deterministic cache key from equipment details."""
    parts = (
        equipment_data.get("manufacturer", ""),
        equipment_data.get("model", ""),
        equipment_data.get("serial_number", ""),
        equipment_data.get("equipment_name", ""),
        equipment_data.get("install_date", ""),
    )
    return hashlib.sha256("|".join(parts).lower().encode()).hexdigest()


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def check_warranty_status(equipment_data: dict, install_date=None, store_location: dict = None) -> dict:
    """Check warranty status for equipment.

    Parameters
    ----------
    equipment_data : dict
        Should include: manufacturer, model, serial_number, install_date,
        equipment_name, category.  An ``equipment_id`` key triggers the
        database lookup; without it only the AI path runs.
    store_location : dict, optional
        Store city/state for finding authorized service agents.
        e.g. {"city": "Bentonville", "state": "AR"}

    Returns
    -------
    dict with keys:
        has_db_warranty, db_warranty, ai_lookup_performed,
        ai_result, recommendation
    """
    result = {
        "has_db_warranty": False,
        "db_warranty": None,
        "ai_lookup_performed": False,
        "ai_result": None,
        "recommendation": "",
    }

    # Step 1 -- database check
    equipment_id = equipment_data.get("equipment_id")
    if equipment_id:
        active = check_active_warranty(equipment_id)
        if active:
            result["has_db_warranty"] = True
            result["db_warranty"] = active
            provider = active.get("warranty_provider", "manufacturer")
            end = active.get("end_date", "unknown")
            contact = active.get("contact_phone") or active.get("contact_email") or "see warranty record"
            result["recommendation"] = (
                f"Under warranty until {end} ({provider}). "
                f"Contact: {contact}"
            )
            return result

        # Check for expired warranties
        all_warranties = get_warranties(equipment_id)
        if all_warranties:
            latest = all_warranties[0]
            end = latest.get("end_date", "unknown")
            result["recommendation"] = f"Warranty expired ({end}). No active coverage on file."
            return result

    # Step 2 -- AI lookup (only if API key is available)
    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        result["recommendation"] = (
            "No warranty on file. AI lookup not configured "
            "(ANTHROPIC_API_KEY not set)."
        )
        return result

    # Inject install_date into equipment_data if provided externally
    if install_date is not None:
        if hasattr(install_date, "isoformat"):
            equipment_data["install_date"] = install_date.isoformat()
        else:
            equipment_data["install_date"] = str(install_date)

    try:
        ai_result = _ai_warranty_research(equipment_data, store_location=store_location)
        result["ai_lookup_performed"] = True
        result["ai_result"] = ai_result

        # Step 3 -- build recommendation from AI result
        if ai_result.get("likely_under_warranty"):
            confidence = ai_result.get("confidence", "low")
            contact = ai_result.get("manufacturer_contact", "N/A")
            if confidence == "high":
                result["recommendation"] = (
                    f"Likely under warranty! "
                    f"Contact manufacturer: {contact}"
                )
            elif confidence == "medium":
                result["recommendation"] = (
                    f"Warranty status uncertain -- PSP should verify with manufacturer. "
                    f"Contact: {contact}"
                )
            else:
                result["recommendation"] = (
                    f"Warranty status unclear (low confidence). "
                    f"Verify with manufacturer: {contact}"
                )
        else:
            period = ai_result.get("warranty_period") or ai_result.get("typical_warranty_period", "unknown")
            result["recommendation"] = (
                f"Warranty likely expired. "
                f"Typical warranty for this equipment: {period}."
            )
    except Exception as exc:
        result["recommendation"] = f"No warranty on file. AI lookup failed: {exc}"

    return result


# ------------------------------------------------------------------
# Tavily web search helpers
# ------------------------------------------------------------------

def _tavily_search(queries: list[str]) -> list[dict]:
    """Run multiple Tavily searches and return combined results.

    Each result dict has: title, url, content (snippet).
    Returns an empty list if Tavily is not available.
    """
    tavily_key = _get_secret("TAVILY_API_KEY")
    if not tavily_key:
        return []

    try:
        from tavily import TavilyClient  # deferred import
        client = TavilyClient(api_key=tavily_key)
    except Exception:
        return []

    all_results = []
    seen_urls = set()

    for query in queries:
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
            )
            for item in response.get("results", []):
                url = item.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                all_results.append({
                    "title": item.get("title", ""),
                    "url": url,
                    "content": item.get("content", ""),
                })
        except Exception:
            # Individual query failure is non-fatal; keep going
            continue

    return all_results


def _build_search_queries(equipment_data: dict, store_location: dict = None) -> list[str]:
    """Build targeted search queries from equipment details.

    Produces up to 6 queries covering:
      1. Warranty terms for this manufacturer/model
      2. Serial number format / manufacture date decoding
      3-6. Authorized service agent searches at city, state, and regional level
    """
    manufacturer = equipment_data.get("manufacturer", "").strip()
    model = equipment_data.get("model", "").strip()
    serial_number = equipment_data.get("serial_number", "").strip()
    equipment_name = equipment_data.get("equipment_name", "").strip()
    install_date = equipment_data.get("install_date", "").strip()

    # Normalise manufacturer slug for URL-style searches (e.g. "hoshizakiamerica")
    mfg_slug = manufacturer.lower().replace(" ", "").replace("-", "")

    # Extract year from install_date for more targeted warranty searches
    install_year = ""
    if install_date and "Unknown" not in install_date:
        install_year = install_date[:4]  # YYYY from YYYY-MM-DD

    queries = []

    # --- Query 1: Warranty terms ---
    if manufacturer and model:
        q = f"{manufacturer} {model} warranty terms coverage"
        if install_year:
            q += f" {install_year}"
        queries.append(q)
    elif manufacturer:
        queries.append(f"{manufacturer} {equipment_name} commercial warranty terms")
    else:
        queries.append(f"{equipment_name} commercial kitchen equipment warranty terms")

    # --- Query 2: Serial number format / manufacture date ---
    if manufacturer and serial_number:
        queries.append(
            f"{manufacturer} serial number format decode manufacture date how to read"
        )

    # --- Queries 3-6: Authorized service agents (city → state → regional) ---
    if manufacturer and store_location:
        city = store_location.get("city", "").strip()
        state = store_location.get("state", "").strip()
        state_name = _state_abbr_to_name(state)  # e.g. "AR" → "Arkansas"

        if city and state:
            # City-level: most specific
            queries.append(
                f"{manufacturer} authorized service dealer repair technician {city} {state}"
            )
            # State-level: broader net
            queries.append(
                f"{manufacturer} authorized service representative {state_name or state} commercial refrigeration repair"
            )

        if state:
            # Manufacturer's own service locator page
            queries.append(
                f"site:{mfg_slug}america.com OR site:{mfg_slug}.com "
                f"authorized service dealer locator {state}"
            )
            # Generic directory search
            queries.append(
                f"{manufacturer} service center dealer locator {state_name or state} find technician"
            )

    # Fallback: warranty claim info if we still have few queries
    if len(queries) < 2 and manufacturer:
        queries.append(f"{manufacturer} warranty claim process contact phone")

    return queries[:6]  # cap at 6 queries (Tavily will run each)


def _state_abbr_to_name(abbr: str) -> str:
    """Convert a US state abbreviation to its full name for broader searches."""
    _map = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington DC",
    }
    return _map.get(abbr.upper(), "")


# ------------------------------------------------------------------
# Core AI research (Tavily + Claude)
# ------------------------------------------------------------------

def _ai_warranty_research(equipment_data: dict, store_location: dict = None) -> dict:
    """Use Tavily web search + Claude API to research warranty information.

    Flow:
    1. Build search queries from equipment data.
    2. Call Tavily to get real web results.
    3. Feed results to Claude with a structured extraction prompt.
    4. Return structured JSON.

    Falls back to Claude-only if Tavily is unavailable or fails.

    Returns a dict with keys: likely_under_warranty, confidence,
    warranty_period, coverage_type, estimated_expiry,
    manufacturer_contact, claim_process, manufacture_date_from_serial,
    authorized_service_agents, source_urls, notes.
    """
    # Check cache first
    key = _cache_key(equipment_data)
    if key in _warranty_cache:
        return _warranty_cache[key]

    import anthropic  # deferred so import cost only hits when needed

    client = anthropic.Anthropic(api_key=_get_secret("ANTHROPIC_API_KEY"))

    # --- Tavily search ---
    search_queries = _build_search_queries(equipment_data, store_location=store_location)
    search_results = _tavily_search(search_queries)

    tavily_available = bool(search_results)
    tavily_key_set = bool(_get_secret("TAVILY_API_KEY"))

    # --- Build Claude prompt ---
    manufacturer = equipment_data.get("manufacturer", "Unknown")
    model = equipment_data.get("model", "Unknown")
    equipment_name = equipment_data.get("equipment_name", "Unknown")
    serial_number = equipment_data.get("serial_number", "Unknown")
    install_date = equipment_data.get("install_date", "Unknown")
    category = equipment_data.get("category", "Unknown")

    today_str = date.today().isoformat()

    # Build store location context
    store_context = ""
    if store_location:
        city = store_location.get("city", "")
        state = store_location.get("state", "")
        if city and state:
            store_context = f"Store Location: {city}, {state}\n"

    if tavily_available:
        # Format search results for Claude
        search_context = "\n\n".join(
            f"Source: {r['title']}\nURL: {r['url']}\nContent: {r['content']}"
            for r in search_results
        )
        prompt = (
            "You are a warranty research assistant for commercial restaurant equipment. "
            "Based on the following web search results and equipment details, extract "
            "warranty information.\n\n"
            f"IMPORTANT: Today's date is {today_str}. Use this date when determining "
            "if equipment is still under warranty. Do NOT assume any other date.\n\n"
            "== EQUIPMENT DETAILS ==\n"
            f"Equipment: {equipment_name}\n"
            f"Manufacturer/Make: {manufacturer}\n"
            f"Model: {model}\n"
            f"Serial Number: {serial_number}\n"
            f"Install Date: {install_date}\n"
            f"Category: {category}\n"
            f"{store_context}\n"
            "== WEB SEARCH RESULTS ==\n"
            f"{search_context}\n\n"
            "STEP 1 — FIND WARRANTY TERMS:\n"
            "Find the specific warranty period for this manufacturer and equipment type "
            "(e.g., '1 year parts and labor', '5 year compressor', '3 year sealed system'). "
            "Note what the warranty covers.\n\n"
            "STEP 2 — SERIAL NUMBER DATE DECODING:\n"
            f"Search the web results for {manufacturer}'s DOCUMENTED serial number format. "
            f"Attempt to decode the manufacture date from serial number '{serial_number}'.\n"
            "RULES (must follow exactly):\n"
            "- ONLY decode if the search results contain the manufacturer's DOCUMENTED serial format\n"
            "- Do NOT guess — if no documentation found in search results, return 'Unknown - serial format not documented in search results'\n"
            "- Do NOT apply another manufacturer's format to this one\n"
            "- Do NOT rely on training knowledge — only use what the search results explicitly state\n"
            "- Decoded date must be between 2000 and 2030, otherwise discard it\n"
            "- Show step-by-step logic: 'Source: [URL] says format is XYZ... applying to serial: ...'\n\n"
            "STEP 3 — CALCULATE EXPIRY DATE (THIS IS MANDATORY):\n"
            "You MUST compute estimated_expiry as a specific YYYY-MM-DD date using this logic:\n"
            "  a) If you successfully decoded a manufacture date in Step 2: start_date = manufacture_date\n"
            f" b) Else if an install date was provided ('{install_date}' and it is a real date): start_date = install_date\n"
            "  c) Else: estimated_expiry = 'Unknown - no start date available'\n"
            "If you have a start_date: estimated_expiry = start_date + warranty_period_in_years\n"
            "SHOW YOUR ARITHMETIC in the notes field, e.g.:\n"
            "  'Manufacture date: 2024-10-07. Warranty: 3 years. Expiry = 2024-10-07 + 3 years = 2027-10-07'\n"
            "  'Install date: 2022-06-01. Warranty: 1 year. Expiry = 2022-06-01 + 1 year = 2023-06-01'\n"
            f"COMPARE estimated_expiry to today ({today_str}) to determine likely_under_warranty.\n"
            "NEVER return a past expiry date for equipment with a recent manufacture or install date — "
            "double-check your arithmetic if the result seems wrong.\n\n"
            "STEP 4 — AUTHORIZED SERVICE AGENTS:\n"
            "From the search results, find up to 3 manufacturer-authorized service companies "
            f"near the store location ({store_context.strip() or 'unknown location'}). "
            "Search broadly — include agents in the same city, nearby cities, or anywhere in the same state. "
            "A technician 1-2 hours away is still useful. "
            "Include company name, phone number, and city/state for each. "
            "Return [] only if the search results contain absolutely no service agent information.\n\n"
            "STEP 5 — SOURCES AND CONFIDENCE:\n"
            "List the most relevant source URLs. "
            "Set confidence to 'high' if manufacturer's own site provided specific warranty terms, "
            "'medium' if third-party or general sources, 'low' if estimating.\n\n"
            "Respond in this exact JSON format:\n"
            "{\n"
            '    "likely_under_warranty": true/false,\n'
            '    "warranty_period": "e.g., 1 year parts and labor, 5 years compressor",\n'
            '    "coverage_type": "e.g., Parts and labor, Parts only",\n'
            '    "estimated_expiry": "YYYY-MM-DD (show arithmetic in notes) or Unknown - reason",\n'
            '    "manufacture_date_from_serial": "YYYY-MM-DD or YYYY-MM decoded from serial, OR Unknown - serial format not documented in search results",\n'
            '    "manufacturer_contact": "phone and/or website",\n'
            '    "claim_process": "brief steps to file a warranty claim",\n'
            '    "authorized_service_agents": [{"name": "Company Name", "phone": "phone", "city": "city, state"}],\n'
            '    "source_urls": ["url1", "url2"],\n'
            '    "confidence": "high/medium/low",\n'
            '    "notes": "REQUIRED: Show expiry date arithmetic here. E.g.: Manufacture date 2024-10-07 + 3yr warranty = expiry 2027-10-07. Also note any exclusions or caveats."\n'
            "}\n\n"
            "NEVER fabricate dates. ALWAYS show your expiry arithmetic in notes. "
            "Only respond with the JSON, no other text."
        )
    else:
        # Fallback: Claude-only (no web search results)
        fallback_note = ""
        if not tavily_key_set:
            fallback_note = (
                "\nNote: Web search is not configured (TAVILY_API_KEY not set), "
                "so you are relying on your training data only. "
                "Set confidence accordingly.\n"
            )
        prompt = (
            "You are a warranty research assistant for commercial restaurant equipment. "
            "Based on the following equipment details, provide warranty information "
            "from your knowledge.\n"
            f"\nIMPORTANT: Today's date is {today_str}. Use this date when determining "
            "if equipment is still under warranty. Do NOT assume any other date.\n"
            f"{fallback_note}\n"
            f"Equipment: {equipment_name}\n"
            f"Manufacturer/Make: {manufacturer}\n"
            f"Model: {model}\n"
            f"Serial Number: {serial_number}\n"
            f"Install Date: {install_date}\n"
            f"Category: {category}\n\n"
            "STEP 1 — WARRANTY TERMS:\n"
            "State the typical warranty period for this manufacturer and equipment type. "
            "Note what it covers (parts, labor, compressor, sealed system, etc.).\n\n"
            "STEP 2 — CALCULATE EXPIRY DATE (MANDATORY — show your arithmetic):\n"
            f" a) If a real install date was provided ('{install_date}'): start_date = install_date\n"
            "  b) Otherwise: estimated_expiry = 'Unknown - no install or manufacture date available'\n"
            "If you have a start_date: estimated_expiry = start_date + warranty_period_in_years\n"
            "EXAMPLE: 'Install date 2022-06-15. Warranty: 3 years. Expiry = 2022-06-15 + 3 years = 2025-06-15'\n"
            f"COMPARE estimated_expiry to today ({today_str}) to set likely_under_warranty.\n"
            "Put the arithmetic in the notes field. NEVER return an expiry date without showing the math.\n\n"
            "STEP 3 — CONTACT AND CLAIM PROCESS:\n"
            "Manufacturer warranty claim contact (phone, website) and general claim steps.\n\n"
            "STEP 4 — EXCLUSIONS:\n"
            "Note common warranty exclusions for this equipment type.\n\n"
            "Respond in this exact JSON format:\n"
            "{\n"
            '    "likely_under_warranty": true/false,\n'
            '    "warranty_period": "e.g., 1 year parts and labor",\n'
            '    "coverage_type": "e.g., Parts and labor, Parts only",\n'
            '    "estimated_expiry": "YYYY-MM-DD or Unknown - reason",\n'
            '    "manufacturer_contact": "phone and/or website",\n'
            '    "claim_process": "brief steps",\n'
            '    "source_urls": [],\n'
            '    "confidence": "high/medium/low",\n'
            '    "notes": "REQUIRED: Show expiry arithmetic here. E.g.: Install date 2022-06-15 + 3yr warranty = expiry 2025-06-15. Also note exclusions."\n'
            "}\n\n"
            "Since you don't have live web search results, set confidence to 'low' or 'medium' at most.\n"
            "NEVER return an estimated_expiry without showing the start_date + warranty_period arithmetic in notes.\n"
            "Only respond with the JSON, no other text."
        )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text

    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)

    # Normalise expected fields
    result = {
        "likely_under_warranty": bool(parsed.get("likely_under_warranty", False)),
        "confidence": str(parsed.get("confidence", "low")).lower(),
        "warranty_period": str(parsed.get("warranty_period", parsed.get("typical_warranty_period", "Unknown"))),
        "coverage_type": str(parsed.get("coverage_type", "Unknown")),
        "estimated_expiry": str(parsed.get("estimated_expiry", "Unknown")),
        "manufacture_date_from_serial": str(parsed.get("manufacture_date_from_serial", "Unknown - not decoded")),
        "authorized_service_agents": list(parsed.get("authorized_service_agents", [])),
        "manufacturer_contact": str(parsed.get("manufacturer_contact", "Unknown")),
        "claim_process": str(parsed.get("claim_process", "Unknown")),
        "source_urls": list(parsed.get("source_urls", [])),
        "notes": str(parsed.get("notes", "")),
        # Keep legacy key for backward compat with save_warranty_from_ai
        "typical_warranty_period": str(parsed.get("warranty_period", parsed.get("typical_warranty_period", "Unknown"))),
        # Metadata
        "web_search_used": tavily_available,
    }

    # Post-processing validation: if manufacture_date_from_serial was decoded,
    # sanity-check it against estimated_expiry. If expiry is in the past but
    # manufacture date is recent (within 2 years), the expiry is likely wrong.
    mfg_raw = result.get("manufacture_date_from_serial", "")
    expiry_raw = result.get("estimated_expiry", "Unknown")
    if mfg_raw and "Unknown" not in mfg_raw and expiry_raw and "Unknown" not in expiry_raw:
        try:
            # Parse manufacture date (YYYY-MM or YYYY-MM-DD)
            mfg_parts = mfg_raw[:7]  # Take YYYY-MM portion
            mfg_date = datetime.strptime(mfg_parts, "%Y-%m").date()
            expiry_date = datetime.strptime(expiry_raw[:10], "%Y-%m-%d").date()
            # If manufacture date is within last 3 years but expiry is in the past, flag it
            if mfg_date >= date(date.today().year - 3, 1, 1) and expiry_date < date.today():
                result["estimated_expiry"] = "Unknown - expiry date conflict (decoded manufacture date is recent but expiry appears past — PSP should verify)"
                result["likely_under_warranty"] = True  # Err on side of caution
                result["confidence"] = "low"
                result["notes"] = (
                    f"WARNING: Manufacture date decoded as {mfg_raw} (recent) but calculated expiry was "
                    f"{expiry_raw} (past). This is a contradiction — the serial number decoding may be wrong. "
                    "PSP should verify manufacture date directly with manufacturer. " + result.get("notes", "")
                )
        except (ValueError, TypeError):
            pass  # Can't parse dates — leave as-is

    # Also validate: if no manufacture date decoded but expiry is in the past,
    # and no install date was provided, flag as uncertain rather than confident
    if "Unknown" in mfg_raw and expiry_raw and "Unknown" not in expiry_raw and "Unknown" not in install_date:
        try:
            expiry_date = datetime.strptime(expiry_raw[:10], "%Y-%m-%d").date()
            if expiry_date < date.today() and install_date == "Unknown - decode from serial number":
                result["estimated_expiry"] = "Unknown - cannot verify without manufacture date or install date"
                result["likely_under_warranty"] = False
                result["confidence"] = "low"
        except (ValueError, TypeError):
            pass

    # Cache the result
    _warranty_cache[key] = result
    return result


def save_warranty_from_ai(equipment_id: str, ai_result: dict, user_id: str) -> bool:
    """Save AI-discovered warranty info to equipment_warranties table.

    Returns True on success, False on failure.
    """
    try:
        sb = get_client()

        # Build warranty record
        today = date.today().isoformat()
        end_date = ai_result.get("estimated_expiry", "Unknown")
        if end_date == "Unknown" or not _is_valid_date(end_date):
            # Default to 1 year from today if we can't parse expiry
            from datetime import timedelta
            end_date = (date.today() + timedelta(days=365)).isoformat()

        warranty_period = ai_result.get("warranty_period") or ai_result.get("typical_warranty_period", "N/A")
        source_urls = ai_result.get("source_urls", [])
        sources_text = ", ".join(source_urls) if source_urls else "AI research (no web sources)"

        warranty_data = {
            "equipment_id": equipment_id,
            "warranty_provider": _extract_provider(ai_result),
            "start_date": today,
            "end_date": end_date,
            "coverage_description": (
                f"AI-researched warranty. "
                f"Typical period: {warranty_period}. "
                f"Coverage: {ai_result.get('coverage_type', 'N/A')}. "
                f"Confidence: {ai_result.get('confidence', 'low')}. "
                f"Sources: {sources_text}. "
                f"{ai_result.get('notes', '')}"
            ),
            "contact_phone": ai_result.get("manufacturer_contact", ""),
        }

        result = sb.table("equipment_warranties").insert(warranty_data).execute()
        return bool(result.data)
    except Exception:
        return False


def get_warranty_summary(equipment_id: str) -> str:
    """Quick one-line summary for display in lists.

    Returns strings like:
    - "Active warranty until 2027-03-15 (Henny Penny)"
    - "Warranty expired 2024-01-01"
    - "No warranty on file"
    """
    active = check_active_warranty(equipment_id)
    if active:
        provider = active.get("warranty_provider", "")
        end = active.get("end_date", "unknown")
        suffix = f" ({provider})" if provider else ""
        return f"Active warranty until {end}{suffix}"

    all_warranties = get_warranties(equipment_id)
    if all_warranties:
        latest = all_warranties[0]
        end = latest.get("end_date", "unknown")
        return f"Warranty expired {end}"

    return "No warranty on file"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _is_valid_date(s: str) -> bool:
    """Return True if *s* can be parsed as YYYY-MM-DD."""
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def _extract_provider(ai_result: dict) -> str:
    """Try to extract a short provider name from the AI contact info."""
    contact = ai_result.get("manufacturer_contact", "")
    # Just use first 100 chars as a label
    return contact[:100] if contact else "Manufacturer (AI-researched)"
