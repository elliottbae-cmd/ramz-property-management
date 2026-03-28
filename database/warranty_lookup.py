"""AI-powered warranty lookup using Claude API.

Three-step process:
1. Check our equipment_warranties table first.
2. If nothing on file, use Claude to research typical warranty info.
3. Return structured results with a recommendation.
"""

import json
import os
import re
from datetime import datetime, date

import streamlit as st
from database.supabase_client import get_client
from database.equipment import check_active_warranty, get_warranties


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def check_warranty_status(equipment_data: dict) -> dict:
    """Check warranty status for equipment.

    Parameters
    ----------
    equipment_data : dict
        Should include: manufacturer, model, serial_number, install_date,
        equipment_name, category.  An ``equipment_id`` key triggers the
        database lookup; without it only the AI path runs.

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
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        result["recommendation"] = (
            "No warranty on file. AI lookup not configured "
            "(ANTHROPIC_API_KEY not set)."
        )
        return result

    try:
        ai_result = _ai_warranty_research(equipment_data)
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
            period = ai_result.get("typical_warranty_period", "unknown")
            result["recommendation"] = (
                f"Warranty likely expired. "
                f"Typical warranty for this equipment: {period}."
            )
    except Exception as exc:
        result["recommendation"] = f"No warranty on file. AI lookup failed: {exc}"

    return result


def _ai_warranty_research(equipment_data: dict) -> dict:
    """Use Claude API to research warranty information.

    Returns a dict with keys: likely_under_warranty, confidence,
    typical_warranty_period, estimated_expiry, manufacturer_contact,
    claim_process, notes.
    """
    import anthropic  # deferred so import cost only hits when needed

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = (
        "You are a warranty research assistant for commercial restaurant equipment. "
        "Based on the following equipment details, provide warranty information.\n\n"
        f"Equipment: {equipment_data.get('equipment_name', 'Unknown')}\n"
        f"Manufacturer/Make: {equipment_data.get('manufacturer', 'Unknown')}\n"
        f"Model: {equipment_data.get('model', 'Unknown')}\n"
        f"Serial Number: {equipment_data.get('serial_number', 'Unknown')}\n"
        f"Install Date: {equipment_data.get('install_date', 'Unknown')}\n"
        f"Category: {equipment_data.get('category', 'Unknown')}\n\n"
        "Please provide:\n"
        "1. Typical warranty period for this type of equipment from this manufacturer\n"
        "2. Whether the equipment is likely still under warranty based on install date\n"
        "3. Manufacturer's warranty claim contact information (phone, website)\n"
        "4. General claim process steps\n"
        "5. Any notes about common warranty exclusions\n\n"
        "Respond in this exact JSON format:\n"
        "{\n"
        '    "likely_under_warranty": true/false,\n'
        '    "confidence": "high/medium/low",\n'
        '    "typical_warranty_period": "X years parts, Y years labor",\n'
        '    "estimated_expiry": "YYYY-MM-DD or Unknown",\n'
        '    "manufacturer_contact": "phone and/or website",\n'
        '    "claim_process": "brief steps",\n'
        '    "notes": "any important notes or exclusions"\n'
        "}\n\n"
        "If you don't have enough information, still provide your best estimate with "
        "low confidence and explain in the notes field.\n"
        "Only respond with the JSON, no other text."
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
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
    return {
        "likely_under_warranty": bool(parsed.get("likely_under_warranty", False)),
        "confidence": str(parsed.get("confidence", "low")).lower(),
        "typical_warranty_period": str(parsed.get("typical_warranty_period", "Unknown")),
        "estimated_expiry": str(parsed.get("estimated_expiry", "Unknown")),
        "manufacturer_contact": str(parsed.get("manufacturer_contact", "Unknown")),
        "claim_process": str(parsed.get("claim_process", "Unknown")),
        "notes": str(parsed.get("notes", "")),
    }


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

        warranty_data = {
            "equipment_id": equipment_id,
            "warranty_provider": _extract_provider(ai_result),
            "start_date": today,
            "end_date": end_date,
            "coverage_description": (
                f"AI-researched warranty. "
                f"Typical period: {ai_result.get('typical_warranty_period', 'N/A')}. "
                f"Confidence: {ai_result.get('confidence', 'low')}. "
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
