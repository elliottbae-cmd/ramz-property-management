"""AI-powered warranty lookup using Tavily web search + Claude API.

Four-step process:
1. Check our equipment_warranties table first.
2. Run deterministic Python serial number decoder (serial_decoder.py).
   This is the ONLY source of manufacture date — Claude is NOT asked to decode serials.
3. Use Tavily + Claude to look up warranty terms, contact info, service agents.
4. Combine Python-decoded manufacture date with AI warranty period to compute expiry.
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
from database.serial_decoder import decode_manufacture_date, format_decode_result


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
    """Research warranty information using Python serial decoder + Tavily + Claude.

    Flow:
    1. Run deterministic Python serial decoder — sole source of manufacture date.
    2. Build Tavily search queries for warranty terms + service agents.
    3. Feed Tavily results + decoded manufacture date to Claude.
       Claude's ONLY jobs: warranty period, contact info, service agents, expiry math.
    4. Combine everything into a structured result.

    Returns a dict with keys: likely_under_warranty, confidence,
    warranty_period, coverage_type, estimated_expiry,
    manufacturer_contact, claim_process, manufacture_date_from_serial,
    manufacture_date_source, authorized_service_agents, source_urls, notes.
    """
    # Check cache first
    key = _cache_key(equipment_data)
    if key in _warranty_cache:
        return _warranty_cache[key]

    import anthropic  # deferred so import cost only hits when needed

    client = anthropic.Anthropic(api_key=_get_secret("ANTHROPIC_API_KEY"))

    manufacturer = equipment_data.get("manufacturer", "Unknown")
    model = equipment_data.get("model", "Unknown")
    equipment_name = equipment_data.get("equipment_name", "Unknown")
    serial_number = equipment_data.get("serial_number", "Unknown")
    install_date = equipment_data.get("install_date", "Unknown")
    category = equipment_data.get("category", "Unknown")

    today_str = date.today().isoformat()

    # ------------------------------------------------------------------
    # Step 1: Deterministic Python serial number decode
    # This is the ONLY place manufacture date comes from.
    # Claude will NOT be asked to decode serials.
    # ------------------------------------------------------------------
    serial_decode = decode_manufacture_date(manufacturer, serial_number)
    if serial_decode.decoded and serial_decode.manufacture_date:
        mfg_date_str = serial_decode.manufacture_date.isoformat()
        mfg_context = (
            f"Manufacture Date (decoded by PSP system from serial number): {mfg_date_str}\n"
            f"Decode method: {serial_decode.method}\n"
            f"Decode confidence: {serial_decode.confidence}\n"
        )
        manufacture_date_from_serial = (
            f"{mfg_date_str} — {serial_decode.method}"
        )
        manufacture_date_source = "python_decoder"
    else:
        mfg_context = (
            f"Manufacture Date: Unknown (serial number format for '{manufacturer}' "
            "is not in PSP's decoder library — do NOT attempt to decode it yourself)\n"
        )
        manufacture_date_from_serial = f"Unknown — {serial_decode.notes}"
        manufacture_date_source = "not_decoded"

    # ------------------------------------------------------------------
    # Step 2: Tavily web search for warranty terms + service agents
    # Remove serial decoding queries since Python handles that now
    # ------------------------------------------------------------------
    search_queries = _build_search_queries(equipment_data, store_location=store_location)
    search_results = _tavily_search(search_queries)

    tavily_available = bool(search_results)
    tavily_key_set = bool(_get_secret("TAVILY_API_KEY"))

    # Build store location context
    store_context = ""
    if store_location:
        city = store_location.get("city", "")
        state = store_location.get("state", "")
        if city and state:
            store_context = f"Store Location: {city}, {state}\n"

    # Determine the best start date for expiry calculation.
    # Priority: install date > manufacture date > unknown.
    # Most manufacturers start the warranty clock from installation, not manufacture.
    # If an install date is known, use it. Fall back to manufacture date only if no
    # install date is on file.
    no_install = "Unknown" in install_date

    has_install = not no_install
    has_mfg = serial_decode.decoded and serial_decode.manufacture_date

    if has_install:
        start_date_str = install_date[:10]
        start_date_label = f"install date {start_date_str} (most manufacturers start warranty at installation)"
    elif has_mfg:
        start_date_str = serial_decode.manufacture_date.isoformat()
        start_date_label = (
            f"manufacture date {start_date_str} (decoded from serial — "
            "use this only if no install date is available, as some manufacturers "
            "start warranty from manufacture, others from installation)"
        )
    else:
        start_date_str = None
        start_date_label = None

    # Build mfg context note for Claude (informational even if not used for expiry)
    mfg_info_note = ""
    if has_mfg and has_install:
        mfg_info_note = (
            f"Note: manufacture date is {serial_decode.manufacture_date.isoformat()} "
            f"(decoded from serial), but install date {install_date[:10]} is known "
            "and takes priority for warranty start. "
            "Mention both dates in your notes for PSP's reference.\n"
        )

    expiry_instruction = (
        f"Warranty start date: {start_date_label}\n"
        f"Formula: estimated_expiry = {start_date_str} + warranty_period_in_years\n"
        f"Show the arithmetic in notes: e.g. '{start_date_str} + 3 years = YYYY-MM-DD'\n"
        f"Compare result to today ({today_str}) to set likely_under_warranty.\n"
        f"{mfg_info_note}"
        "IMPORTANT: Check the search results to confirm whether this manufacturer "
        "starts the warranty from installation date or manufacture date — they differ by brand."
        if start_date_str else
        "No install date or manufacture date is available. "
        "Set estimated_expiry = 'Unknown - no start date available' and likely_under_warranty = false."
    )

    # ------------------------------------------------------------------
    # Step 3: Build Claude prompt — warranty terms + service agents ONLY
    # ------------------------------------------------------------------
    if tavily_available:
        search_context = "\n\n".join(
            f"Source: {r['title']}\nURL: {r['url']}\nContent: {r['content']}"
            for r in search_results
        )
        prompt = (
            "You are a warranty research assistant for commercial restaurant equipment.\n"
            f"IMPORTANT: Today's date is {today_str}.\n\n"
            "== EQUIPMENT DETAILS ==\n"
            f"Equipment: {equipment_name}\n"
            f"Manufacturer/Make: {manufacturer}\n"
            f"Model: {model}\n"
            f"Serial Number: {serial_number}\n"
            f"{mfg_context}"
            f"Category: {category}\n"
            f"{store_context}\n"
            "== WEB SEARCH RESULTS ==\n"
            f"{search_context}\n\n"
            "YOUR TASKS (do NOT decode the serial number — manufacture date is already provided above):\n\n"
            "TASK 1 — WARRANTY TERMS:\n"
            "From the search results, find the specific warranty period for this manufacturer "
            "and equipment type (e.g., '1 year parts and labor', '5 year compressor'). "
            "Note exactly what is covered.\n\n"
            "TASK 2 — CALCULATE EXPIRY DATE:\n"
            f"{expiry_instruction}\n"
            "Put the arithmetic in the notes field.\n\n"
            "TASK 3 — MANUFACTURER CONTACT:\n"
            "Warranty claim phone number and/or website from search results.\n\n"
            "TASK 4 — AUTHORIZED SERVICE AGENTS:\n"
            "From the search results, find up to 3 manufacturer-authorized service companies "
            f"near {store_context.strip() or 'the store location'}. "
            "Include agents in the same city, nearby cities, or anywhere in the same state — "
            "a technician 1-2 hours away is still useful. "
            "Include name, phone, and city/state. Return [] if none found.\n\n"
            "TASK 5 — CONFIDENCE:\n"
            "Set to 'high' if manufacturer's own site had specific terms, "
            "'medium' for third-party sources, 'low' if estimating.\n\n"
            "Respond with ONLY this JSON:\n"
            "{\n"
            '    "likely_under_warranty": true/false,\n'
            '    "warranty_period": "e.g., 1 year parts and labor, 5 years compressor",\n'
            '    "coverage_type": "e.g., Parts and labor, Parts only",\n'
            '    "estimated_expiry": "YYYY-MM-DD or Unknown - reason",\n'
            '    "manufacturer_contact": "phone and/or website",\n'
            '    "claim_process": "brief steps to file a warranty claim",\n'
            '    "authorized_service_agents": [{"name": "...", "phone": "...", "city": "city, state"}],\n'
            '    "source_urls": ["url1", "url2"],\n'
            '    "confidence": "high/medium/low",\n'
            '    "notes": "Show expiry arithmetic here, e.g.: 2024-10-01 + 3yr = 2027-10-01. Note exclusions."\n'
            "}"
        )
    else:
        fallback_note = (
            "Note: No live web search results available — using training knowledge only. "
            "Set confidence to 'low' or 'medium' at most.\n"
        )
        prompt = (
            "You are a warranty research assistant for commercial restaurant equipment.\n"
            f"IMPORTANT: Today's date is {today_str}.\n"
            f"{fallback_note}\n"
            "== EQUIPMENT DETAILS ==\n"
            f"Equipment: {equipment_name}\n"
            f"Manufacturer/Make: {manufacturer}\n"
            f"Model: {model}\n"
            f"Serial Number: {serial_number}\n"
            f"{mfg_context}"
            f"Category: {category}\n\n"
            "YOUR TASKS (do NOT decode the serial number — manufacture date is already provided above):\n\n"
            "TASK 1 — WARRANTY TERMS: Typical warranty period and coverage for this manufacturer/equipment.\n\n"
            "TASK 2 — CALCULATE EXPIRY DATE:\n"
            f"{expiry_instruction}\n"
            "Put the arithmetic in notes.\n\n"
            "TASK 3 — MANUFACTURER CONTACT: Warranty claim phone and website.\n\n"
            "TASK 4 — EXCLUSIONS: Common warranty exclusions for this equipment.\n\n"
            "Respond with ONLY this JSON:\n"
            "{\n"
            '    "likely_under_warranty": true/false,\n'
            '    "warranty_period": "e.g., 1 year parts and labor",\n'
            '    "coverage_type": "e.g., Parts and labor, Parts only",\n'
            '    "estimated_expiry": "YYYY-MM-DD or Unknown - reason",\n'
            '    "manufacturer_contact": "phone and/or website",\n'
            '    "claim_process": "brief steps",\n'
            '    "source_urls": [],\n'
            '    "confidence": "low/medium",\n'
            '    "notes": "Show expiry arithmetic here. Note exclusions."\n'
            "}"
        )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)

    # Normalise expected fields — manufacture date comes from Python decoder, not Claude
    result = {
        "likely_under_warranty": bool(parsed.get("likely_under_warranty", False)),
        "confidence": str(parsed.get("confidence", "low")).lower(),
        "warranty_period": str(parsed.get("warranty_period", parsed.get("typical_warranty_period", "Unknown"))),
        "coverage_type": str(parsed.get("coverage_type", "Unknown")),
        "estimated_expiry": str(parsed.get("estimated_expiry", "Unknown")),
        # Manufacture date is from Python decoder — authoritative and consistent
        "manufacture_date_from_serial": manufacture_date_from_serial,
        "manufacture_date_source": manufacture_date_source,
        "serial_decode_confidence": serial_decode.confidence,
        "serial_decode_notes": serial_decode.notes,
        "authorized_service_agents": list(parsed.get("authorized_service_agents", [])),
        "manufacturer_contact": str(parsed.get("manufacturer_contact", "Unknown")),
        "claim_process": str(parsed.get("claim_process", "Unknown")),
        "source_urls": list(parsed.get("source_urls", [])),
        "notes": str(parsed.get("notes", "")),
        # Keep legacy key for backward compat
        "typical_warranty_period": str(parsed.get("warranty_period", parsed.get("typical_warranty_period", "Unknown"))),
        "web_search_used": tavily_available,
    }

    # ------------------------------------------------------------------
    # Post-processing: expiry sanity check using Python-decoded mfg date
    # (No need to re-validate serial decode here — Python decoder is authoritative)
    # ------------------------------------------------------------------
    expiry_raw = result.get("estimated_expiry", "Unknown")
    no_install = "Unknown" in install_date
    today = date.today()

    # If we have a verified Python-decoded manufacture date, check that Claude's
    # calculated expiry is consistent with it (should be mfg_date + warranty_period)
    if serial_decode.decoded and serial_decode.manufacture_date:
        expiry_date = None
        _e = re.search(r"(\d{4}-\d{2}-\d{2})", expiry_raw)
        if _e:
            try:
                expiry_date = datetime.strptime(_e.group(1), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        # If expiry is in the past but manufacture date is recent → Claude messed up the math
        if expiry_date and expiry_date < today:
            age_years = (today - serial_decode.manufacture_date).days / 365.25
            if age_years < 5:
                result["estimated_expiry"] = (
                    f"Unknown — expiry arithmetic error: manufacture date "
                    f"{serial_decode.manufacture_date} is only {age_years:.1f} years ago "
                    f"but calculated expiry {expiry_date} is in the past. PSP should verify."
                )
                result["likely_under_warranty"] = True
                result["confidence"] = "low"
                result["notes"] = (
                    f"⚠️ Expiry calculation error: manufacture date {serial_decode.manufacture_date} "
                    f"+ warranty period should produce a future date, but got {expiry_date} (past). "
                    "PSP should manually calculate: manufacture date + warranty period. "
                ) + result.get("notes", "")

    # If no manufacture date and no install date, can't confirm expired
    elif not serial_decode.decoded and no_install:
        expiry_date = None
        _e = re.search(r"(\d{4}-\d{2}-\d{2})", expiry_raw)
        if _e:
            try:
                expiry_date = datetime.strptime(_e.group(1), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        if expiry_date and expiry_date < today:
            result["estimated_expiry"] = "Unknown — cannot confirm without manufacture or install date"
            result["likely_under_warranty"] = False
            result["confidence"] = "low"

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
