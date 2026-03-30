"""Parse a PSP Project Closeout PDF and extract structured equipment,
warranty, and service agent data for import into the app.

Flow:
1. Use pdfplumber to extract all text from the PDF.
2. Send the raw text to Claude with a structured extraction prompt.
3. Claude returns a JSON array of equipment records with warranties
   and service agents embedded.
4. Caller can preview and then call import_to_supabase() to commit.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Optional

from config.settings import _get_secret
from database.supabase_client import get_client


# ------------------------------------------------------------------
# PDF text extraction
# ------------------------------------------------------------------

def extract_pdf_text(pdf_path: str) -> str:
    """Extract all text from a PDF using pdfplumber.

    Returns concatenated text from all pages.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "pdfplumber is required for PDF parsing. "
            "Add 'pdfplumber' to requirements.txt and reinstall."
        )

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(f"--- PAGE {i + 1} ---\n{page_text}")

    return "\n\n".join(text_parts)


# ------------------------------------------------------------------
# Claude-powered structured extraction
# ------------------------------------------------------------------

def parse_closeout_with_claude(pdf_text: str, store_state: str = "") -> dict:
    """Send extracted PDF text to Claude and get structured data back.

    Returns a dict with keys:
      store_info       : dict (address, phone, opening_date)
      equipment_list   : list of equipment dicts (see schema below)
      vendor_contacts  : list of vendor dicts
      health_permit    : dict (permit_number, expiry_date)

    Equipment dict schema:
      name             : str  (description, e.g. "Ice Maker - Back of House")
      manufacturer     : str  (e.g. "Hoshizaki")
      manufacturer_phone: str
      manufacturer_website: str
      model            : str
      serial_numbers   : list[str]  (split if multiple)
      category         : str  (inferred: Refrigeration / Cooking / Ice / etc.)
      warranty_terms   : str  (raw, e.g. "5 Yr P&L, 6 Yr Parts, 7 Yr Compressor")
      warranty_years_pl: float  (parts & labor years, 0 if none)
      warranty_years_parts: float  (parts-only years)
      warranty_years_compressor: float
      service_agent_name: str
      service_agent_phone: str
      contact_factory_first: bool  (true if "CONTACT FACTORY FIRST")
    """
    import anthropic

    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured.")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a data extraction assistant. Extract structured data from this
restaurant construction closeout package PDF text.

Focus on these sections:
1. Store information (address, phone, opening date)
2. Equipment Warranty & Service List (the main equipment table)
3. Health permit details
4. Vendor contacts list

PDF TEXT:
{pdf_text[:15000]}

Return ONLY valid JSON in this exact format (no other text):
{{
  "store_info": {{
    "address": "full street address",
    "city": "city name",
    "state": "2-letter state abbreviation e.g. OK",
    "zip": "zip code",
    "phone": "store phone number",
    "opening_date": "YYYY-MM-DD or null",
    "cofo_date": "YYYY-MM-DD or null — Certificate of Occupancy date if found in the document"
  }},
  "health_permit": {{
    "permit_number": "permit number or null",
    "expiry_date": "YYYY-MM-DD or null",
    "issue_date": "YYYY-MM-DD or null",
    "issuing_authority": "name of health dept"
  }},
  "equipment_list": [
    {{
      "name": "human-readable description e.g. Ice Maker - Back of House",
      "manufacturer": "manufacturer name only (no phone)",
      "manufacturer_phone": "phone number",
      "manufacturer_website": "website URL or empty string",
      "model": "model number",
      "serial_numbers": ["serial1", "serial2"],
      "category": "one of: Refrigeration, Ice Machine, Cooking, Fryer, Custard, Beverage, HVAC, POS, Safety, Signage, Audio/Visual, Warewashing, Other",
      "warranty_terms": "raw warranty text e.g. 5 Yr P&L on Machine, 6 Yr Parts, 7 Yr Compressor",
      "warranty_years_pl": 1.0,
      "warranty_years_parts": 0.0,
      "warranty_years_compressor": 0.0,
      "service_agent_name": "service company name or CONTACT FACTORY FIRST",
      "service_agent_phone": "service agent phone",
      "contact_factory_first": false
    }}
  ],
  "vendor_contacts": [
    {{
      "category": "category label",
      "vendor_name": "company name",
      "contact_name": "person name or empty",
      "phone": "phone number",
      "email": "email or empty",
      "notes": "any notes"
    }}
  ]
}}

IMPORTANT RULES:
- Split serial numbers that contain "/" or "," into separate items in the serial_numbers array
- For warranty_years_pl: extract the parts & labor (P&L) years as a number. E.g. "5 Yr P&L" → 5.0, "2 Yr P&L / 1 Yr Labor" → 1.0 (use the labor years), "1 Year" → 1.0
- For warranty_years_parts: extract parts-only years beyond P&L. E.g. "6 Yr Parts" → 6.0
- For warranty_years_compressor: extract compressor warranty years. E.g. "7 Yr Compressor" → 7.0
- Set contact_factory_first to true if the service agent column says "CONTACT FACTORY FIRST"
- Infer category from the description (Ice Maker → Ice Machine, Griddle/Fryer → Cooking, Freezer/Cooler/Refrigerator → Refrigeration, etc.)
- Include ALL rows from the equipment table, even items without serial numbers
- Return empty string for missing text fields, null for missing dates, 0.0 for missing numeric fields
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    # Try to parse as-is first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # If the response was cut off, try to repair it by truncating to the last
    # complete equipment item and closing all open structures
    repaired = _repair_truncated_json(raw)
    if repaired:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    # Final fallback: ask Claude to re-parse just the equipment table
    # with a simpler prompt that produces less output
    return _parse_equipment_only(client, pdf_text)


# ------------------------------------------------------------------
# JSON repair helpers
# ------------------------------------------------------------------

def _repair_truncated_json(raw: str) -> str | None:
    """Attempt to repair JSON that was cut off mid-response.

    Strategy: find the last complete equipment object (ends with }),
    truncate there, then close all open arrays/objects.
    """
    # Find the last complete '}' that closes an equipment item
    # Equipment items end with a closing brace before a comma or the array close
    last_good = raw.rfind('},\n')
    if last_good == -1:
        last_good = raw.rfind('},')
    if last_good == -1:
        last_good = raw.rfind('}')

    if last_good == -1:
        return None

    # Truncate after last complete object
    truncated = raw[:last_good + 1]

    # Count unmatched open brackets/braces to figure out what needs closing
    opens = truncated.count('{') - truncated.count('}')
    open_arrays = truncated.count('[') - truncated.count(']')

    # Close any open structures
    closing = ''
    for _ in range(opens):
        closing += '}'
    for _ in range(open_arrays):
        closing = ']' + closing

    repaired = truncated + closing
    return repaired


def _parse_equipment_only(client, pdf_text: str) -> dict:
    """Fallback: ask Claude to return only the equipment list with a simpler,
    more compact prompt that fits in fewer tokens."""

    simple_prompt = f"""Extract the equipment warranty table from this closeout PDF.
Return ONLY a JSON object with these fields. Be concise — use short values.

PDF TEXT (first 12000 chars):
{pdf_text[:12000]}

Return this JSON (no other text):
{{
  "store_info": {{"address": "", "city": "", "state": "", "zip": "", "phone": "", "opening_date": null, "cofo_date": null}},
  "health_permit": {{"permit_number": "", "expiry_date": null, "issue_date": null, "issuing_authority": ""}},
  "vendor_contacts": [],
  "equipment_list": [
    {{
      "name": "short description",
      "manufacturer": "name",
      "manufacturer_phone": "",
      "manufacturer_website": "",
      "model": "",
      "serial_numbers": [],
      "category": "Refrigeration|Ice Machine|Cooking|Fryer|Custard|Beverage|HVAC|POS|Safety|Other",
      "warranty_terms": "raw text",
      "warranty_years_pl": 0,
      "warranty_years_parts": 0,
      "warranty_years_compressor": 0,
      "service_agent_name": "",
      "service_agent_phone": "",
      "contact_factory_first": false
    }}
  ]
}}
Split serial numbers containing "/" or "," into the array. Only respond with JSON."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{"role": "user", "content": simple_prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    # Try repair again if needed
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(raw)
        if repaired:
            return json.loads(repaired)
        raise


# ------------------------------------------------------------------
# Import to Supabase
# ------------------------------------------------------------------

def import_to_supabase(
    parsed: dict,
    store_id: str,
    client_id: str,
    user_id: str,
    opening_date: Optional[date] = None,
    dry_run: bool = False,
) -> dict:
    """Import parsed closeout data into Supabase.

    Parameters
    ----------
    parsed      : output from parse_closeout_with_claude()
    store_id    : UUID of the store to attach equipment to
    client_id   : UUID of the client (for contractors)
    user_id     : UUID of the PSP user performing the import
    opening_date: store opening date (used as install_date fallback)
    dry_run     : if True, validate but don't write to DB

    Returns
    -------
    dict with keys:
      equipment_created  : int
      warranties_created : int
      contractors_created: int
      contractors_updated: int
      skipped            : list of (name, reason) tuples
      errors             : list of error strings
    """
    sb = get_client()
    result = {
        "equipment_created": 0,
        "warranties_created": 0,
        "contractors_created": 0,
        "contractors_updated": 0,
        "store_updated": False,
        "skipped": [],
        "errors": [],
    }

    install_date = opening_date.isoformat() if opening_date else None

    # ---- Update store record with CofO, opening date, health permit ----
    store_info = parsed.get("store_info", {})
    permit_info = parsed.get("health_permit", {})
    store_updates = {}

    if opening_date:
        store_updates["opening_date"] = opening_date.isoformat()
    elif store_info.get("opening_date"):
        store_updates["opening_date"] = store_info["opening_date"]

    if store_info.get("cofo_date"):
        store_updates["cofo_date"] = store_info["cofo_date"]

    if permit_info.get("permit_number"):
        store_updates["health_permit_number"] = permit_info["permit_number"]

    if permit_info.get("expiry_date"):
        store_updates["health_permit_expiry"] = permit_info["expiry_date"]

    store_updates["closeout_imported_at"] = "NOW()"

    if store_updates and not dry_run:
        try:
            # Remove NOW() placeholder — use DB default via RPC instead
            store_updates.pop("closeout_imported_at", None)
            sb.table("stores").update(store_updates).eq("id", store_id).execute()
            # Set closeout_imported_at separately via raw update
            sb.table("stores").update({"closeout_imported_at": date.today().isoformat() + "T00:00:00Z"}).eq("id", store_id).execute()
            result["store_updated"] = True
        except Exception as e:
            result["errors"].append(f"Store record update: {e}")

    # Track service agents seen so we don't create duplicates
    # key: normalised company name → contractor_id
    agent_id_map: dict[str, str] = {}

    for item in parsed.get("equipment_list", []):
        name = item.get("name", "").strip()
        if not name:
            result["skipped"].append(("(unnamed)", "No equipment name"))
            continue

        # ---- Step 1: Upsert service agent as contractor ----
        agent_name = item.get("service_agent_name", "").strip()
        contact_factory = item.get("contact_factory_first", False)
        agent_id = None

        if agent_name and not contact_factory and agent_name.upper() != "CONTACT FACTORY FIRST":
            agent_key = agent_name.lower().strip()
            if agent_key in agent_id_map:
                agent_id = agent_id_map[agent_key]
            else:
                try:
                    # Check if contractor already exists by name
                    existing = (
                        sb.table("contractors")
                        .select("id, trades, service_states, service_cities")
                        .ilike("company_name", agent_name)
                        .execute()
                    )
                    if existing.data:
                        # Update trades/states if needed
                        contractor = existing.data[0]
                        agent_id = contractor["id"]
                        # Add the inferred trade if not already present
                        trade = _category_to_trade(item.get("category", ""))
                        current_trades = contractor.get("trades") or []
                        current_states = contractor.get("service_states") or []
                        store_info = parsed.get("store_info", {})
                        state = store_info.get("state", "")
                        city = store_info.get("city", "")
                        updates = {}
                        if trade and trade not in current_trades:
                            updates["trades"] = list(set(current_trades + [trade]))
                        if state and state not in current_states:
                            updates["service_states"] = list(set(current_states + [state]))
                        if updates and not dry_run:
                            # Also add city
                            current_cities = contractor.get("service_cities") or []
                            if city and city not in current_cities:
                                updates["service_cities"] = list(set(current_cities + [city]))
                            sb.table("contractors").update(updates).eq("id", agent_id).execute()
                            result["contractors_updated"] += 1
                    else:
                        # Create new contractor
                        store_info = parsed.get("store_info", {})
                        state = store_info.get("state", "")
                        city = store_info.get("city", "")
                        trade = _category_to_trade(item.get("category", ""))
                        contractor_data = {
                            "company_name": agent_name,
                            "phone": item.get("service_agent_phone", ""),
                            "trades": [trade] if trade else [],
                            "service_states": [state] if state else [],
                            "service_cities": [city] if city else [],
                            "is_active": True,
                            "is_preferred": False,
                            "notes": f"Added via closeout import for store {store_id}",
                        }
                        if not dry_run:
                            new_c = sb.table("contractors").insert(contractor_data).execute()
                            if new_c.data:
                                agent_id = new_c.data[0]["id"]
                                result["contractors_created"] += 1
                        else:
                            result["contractors_created"] += 1

                    agent_id_map[agent_key] = agent_id
                except Exception as e:
                    result["errors"].append(f"Contractor '{agent_name}': {e}")

        # ---- Step 2: Create equipment record ----
        serial_numbers = item.get("serial_numbers", [])
        # Create one equipment record per serial (or one if no serial)
        serials_to_create = serial_numbers if serial_numbers else [""]

        for serial in serials_to_create:
            # Skip placeholder serials
            if serial.upper() in ("N/A", "NA", ""):
                serial = ""

            equip_name = name
            if len(serials_to_create) > 1 and serial:
                equip_name = f"{name} (S/N: {serial})"

            equip_data = {
                "store_id": store_id,
                "name": equip_name,
                "manufacturer": item.get("manufacturer", ""),
                "model": item.get("model", ""),
                "serial_number": serial or None,
                "category": item.get("category", "Other"),
                "install_date": install_date,
                "notes": (
                    f"Manufacturer contact: {item.get('manufacturer_phone', '')}\n"
                    f"Manufacturer website: {item.get('manufacturer_website', '')}\n"
                    f"Service agent: {agent_name or 'Contact factory first'} "
                    f"{item.get('service_agent_phone', '')}"
                ).strip(),
                "is_active": True,
            }

            equipment_id = None
            if not dry_run:
                try:
                    new_eq = sb.table("equipment").insert(equip_data).execute()
                    if new_eq.data:
                        equipment_id = new_eq.data[0]["id"]
                        result["equipment_created"] += 1
                except Exception as e:
                    result["errors"].append(f"Equipment '{equip_name}': {e}")
                    continue
            else:
                result["equipment_created"] += 1

            # ---- Step 3: Create warranty record ----
            warranty_terms = item.get("warranty_terms", "").strip()
            if warranty_terms and equipment_id:
                # Calculate end date from best available warranty period
                pl_years = float(item.get("warranty_years_pl") or 0)
                parts_years = float(item.get("warranty_years_parts") or 0)
                comp_years = float(item.get("warranty_years_compressor") or 0)
                best_years = max(pl_years, parts_years, comp_years, 1.0)

                start = opening_date or date.today()
                end = date(
                    start.year + int(best_years),
                    start.month,
                    start.day,
                )

                # Build coverage description
                coverage_parts = []
                if pl_years:
                    coverage_parts.append(f"{pl_years:.0f}-year Parts & Labor")
                if parts_years:
                    coverage_parts.append(f"{parts_years:.0f}-year Parts")
                if comp_years:
                    coverage_parts.append(f"{comp_years:.0f}-year Compressor")
                coverage_str = "; ".join(coverage_parts) if coverage_parts else warranty_terms

                warranty_data = {
                    "equipment_id": equipment_id,
                    "warranty_provider": item.get("manufacturer", "Manufacturer"),
                    "warranty_type": "manufacturer",
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "coverage_description": (
                        f"{coverage_str}. "
                        f"Raw terms: {warranty_terms}. "
                        f"Contact: {item.get('manufacturer_phone', '')} "
                        f"{item.get('manufacturer_website', '')}"
                    ),
                    "contact_phone": item.get("manufacturer_phone", ""),
                    "claim_url": item.get("manufacturer_website", "") or None,
                    "status": "active",
                    "created_by": user_id,
                }

                if not dry_run:
                    try:
                        new_w = sb.table("equipment_warranties").insert(warranty_data).execute()
                        if new_w.data:
                            result["warranties_created"] += 1
                    except Exception as e:
                        result["errors"].append(f"Warranty for '{equip_name}': {e}")
                else:
                    result["warranties_created"] += 1

    return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _category_to_trade(category: str) -> str:
    """Map an equipment category to a contractor trade."""
    _map = {
        "Refrigeration": "Refrigeration",
        "Ice Machine": "Refrigeration",
        "Cooking": "Kitchen Equipment",
        "Fryer": "Kitchen Equipment",
        "Custard": "Kitchen Equipment",
        "HVAC": "HVAC",
        "Warewashing": "Kitchen Equipment",
        "Beverage": "Kitchen Equipment",
        "POS": "Technology",
        "Audio/Visual": "Technology",
        "Signage": "Signage",
        "Safety": "General",
        "Other": "General",
    }
    return _map.get(category, "General")


def summarise_parsed(parsed: dict) -> dict:
    """Return a human-readable summary for the preview UI."""
    equipment = parsed.get("equipment_list", [])
    store = parsed.get("store_info", {})
    permit = parsed.get("health_permit", {})

    # Count service agents
    agents = {}
    for item in equipment:
        a = item.get("service_agent_name", "")
        if a and "CONTACT FACTORY FIRST" not in a.upper():
            agents[a] = agents.get(a, 0) + 1

    # Count by category
    categories: dict[str, int] = {}
    for item in equipment:
        cat = item.get("category", "Other")
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "store_address": f"{store.get('address', '')}, {store.get('city', '')}, {store.get('state', '')} {store.get('zip', '')}".strip(", "),
        "opening_date": store.get("opening_date"),
        "cofo_date": store.get("cofo_date"),
        "permit_number": permit.get("permit_number"),
        "permit_expiry": permit.get("expiry_date"),
        "total_equipment": len(equipment),
        "total_serials": sum(len(i.get("serial_numbers", [])) for i in equipment),
        "categories": categories,
        "service_agents": agents,
        "vendors": len(parsed.get("vendor_contacts", [])),
    }
