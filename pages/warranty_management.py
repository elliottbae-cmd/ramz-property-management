"""
Warranty Management -- Track and manage equipment warranties.
Active warranties, expiring-soon alerts, claim tracking, and AI lookup.
"""

import streamlit as st
from datetime import datetime, date, timedelta

from database.supabase_client import get_current_user, get_client
from database.tenant import get_effective_client_id
from database.equipment import (
    get_equipment_for_client,
    get_warranties,
    check_active_warranty,
    create_warranty,
)
from database.warranty_lookup import (
    check_warranty_status,
    save_warranty_from_ai,
    get_warranty_summary,
)
from theme.branding import render_header
from utils.permissions import require_permission, can_manage_tickets
from utils.helpers import format_date_short


def render():
    render_header("Warranty Management", "Track and manage equipment warranties")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    require_permission(can_manage_tickets, "You do not have access to this page.")

    client_id = get_effective_client_id()
    if not client_id:
        st.warning("No client context selected. Please select a client first.")
        return

    # Load all equipment for this client
    all_equipment = get_equipment_for_client(client_id)
    if not all_equipment:
        st.info("No equipment found for this client.")
        return

    # Enrich with warranty data (both functions are now cached per-item)
    for item in all_equipment:
        item["active_warranty"] = check_active_warranty(item["id"])
        item["all_warranties"] = get_warranties(item["id"]) if not item["active_warranty"] else []

    # Tabs
    tab_active, tab_expiring, tab_claims, tab_lookup = st.tabs([
        "Active Warranties",
        "Expiring Soon",
        "Warranty Claims",
        "AI Lookup",
    ])

    with tab_active:
        _render_active_warranties(all_equipment)

    with tab_expiring:
        _render_expiring_soon(all_equipment)

    with tab_claims:
        _render_warranty_claims(client_id)

    with tab_lookup:
        _render_ai_lookup(all_equipment, user)


# ------------------------------------------------------------------
# Tab 1: Active Warranties
# ------------------------------------------------------------------

def _render_active_warranties(equipment: list[dict]):
    """List all equipment with active warranties."""
    active_items = [e for e in equipment if e.get("active_warranty")]

    st.markdown(f"### Active Warranties ({len(active_items)})")

    if not active_items:
        st.info("No active warranties found.")
        return

    for item in active_items:
        warranty = item["active_warranty"]
        store = item.get("stores") or {}
        store_label = f"{store.get('store_number', '?')} - {store.get('name', 'Unknown')}"

        name = item.get("name", "Unknown")
        mfr = item.get("manufacturer") or ""
        provider = warranty.get("warranty_provider", "N/A")
        end_date = warranty.get("end_date", "N/A")

        # Calculate days remaining
        days_remaining = ""
        try:
            end_dt = datetime.fromisoformat(str(end_date)).date()
            remaining = (end_dt - date.today()).days
            days_remaining = f" ({remaining} days remaining)"
        except Exception:
            pass

        with st.expander(f"{name} -- {mfr} | {store_label} | Expires: {end_date}{days_remaining}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Equipment:** {name}")
                st.write(f"**Manufacturer:** {mfr}")
                st.write(f"**Model:** {item.get('model', 'N/A')}")
                st.write(f"**Serial Number:** {item.get('serial_number', 'N/A')}")
                st.write(f"**Store:** {store_label}")

            with col2:
                st.write(f"**Warranty Provider:** {provider}")
                st.write(f"**Start Date:** {format_date_short(str(warranty.get('start_date', '')))}")
                st.write(f"**End Date:** {format_date_short(str(warranty.get('end_date', '')))}")
                if warranty.get("coverage_description"):
                    st.write(f"**Coverage:** {warranty['coverage_description']}")
                if warranty.get("contact_phone"):
                    st.write(f"**Phone:** {warranty['contact_phone']}")
                if warranty.get("contact_email"):
                    st.write(f"**Email:** {warranty['contact_email']}")


# ------------------------------------------------------------------
# Tab 2: Expiring Soon
# ------------------------------------------------------------------

def _render_expiring_soon(equipment: list[dict]):
    """Warranties expiring within 30/60/90 days."""
    st.markdown("### Expiring Soon")

    window = st.radio(
        "Show warranties expiring within:",
        options=[30, 60, 90],
        format_func=lambda x: f"{x} days",
        horizontal=True,
        key="expiry_window",
    )

    today = date.today()
    cutoff = today + timedelta(days=window)

    expiring = []
    for item in equipment:
        warranty = item.get("active_warranty")
        if not warranty:
            continue
        try:
            end_dt = datetime.fromisoformat(str(warranty.get("end_date", ""))).date()
            if today <= end_dt <= cutoff:
                item["_expiry_date"] = end_dt
                item["_days_remaining"] = (end_dt - today).days
                expiring.append(item)
        except Exception:
            continue

    # Sort by soonest expiry first
    expiring.sort(key=lambda x: x.get("_days_remaining", 999))

    if not expiring:
        st.success(f"No warranties expiring in the next {window} days.")
        return

    st.warning(f"{len(expiring)} warranty(ies) expiring in the next {window} days:")

    for item in expiring:
        warranty = item["active_warranty"]
        store = item.get("stores") or {}
        store_label = f"{store.get('store_number', '?')} - {store.get('name', '')}"
        days_left = item["_days_remaining"]
        name = item.get("name", "Unknown")
        mfr = item.get("manufacturer") or ""
        end_date = warranty.get("end_date", "N/A")
        provider = warranty.get("warranty_provider", "N/A")

        # Color-code urgency
        if days_left <= 14:
            color = "#B71C1C"  # red
            urgency = "CRITICAL"
        elif days_left <= 30:
            color = "#F57F17"  # amber
            urgency = "WARNING"
        else:
            color = "#1565C0"  # blue
            urgency = "UPCOMING"

        st.markdown(
            f'<div style="border-left: 4px solid {color}; padding: 8px 16px; '
            f'margin: 4px 0; background-color: rgba(0,0,0,0.02); border-radius: 4px;">'
            f'<strong>{urgency}</strong> -- {name} ({mfr}) -- {store_label}<br>'
            f'Provider: {provider} | Expires: {end_date} | '
            f'<strong>{days_left} day{"s" if days_left != 1 else ""} remaining</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )

        contact = warranty.get("contact_phone") or warranty.get("contact_email")
        if contact:
            st.caption(f"Contact: {contact}")


# ------------------------------------------------------------------
# Tab 3: Warranty Claims
# ------------------------------------------------------------------

def _render_warranty_claims(client_id: str):
    """Track warranty claims submitted."""
    st.markdown("### Warranty Claims")

    try:
        sb = get_client()
        result = (
            sb.table("warranty_claims")
            .select("*, equipment(name, manufacturer, model, serial_number, stores(store_number, name))")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .execute()
        )
        claims = result.data or []
    except Exception:
        # Table may not exist yet
        claims = []

    if not claims:
        st.info(
            "No warranty claims on record. Claims will appear here when "
            "submitted through the warranty check process."
        )
        return

    for claim in claims:
        equip = claim.get("equipment") or {}
        store = equip.get("stores") or {}
        equip_name = equip.get("name", "Unknown")
        store_label = f"{store.get('store_number', '?')} - {store.get('name', '')}"
        status = claim.get("status", "unknown")
        created = format_date_short(str(claim.get("created_at", "")))
        claim_number = claim.get("claim_number", "N/A")

        # Status badge colors
        status_colors = {
            "submitted": "#1565C0",
            "in_progress": "#F57F17",
            "approved": "#1B5E20",
            "denied": "#B71C1C",
            "completed": "#4CAF50",
        }
        badge_color = status_colors.get(status, "#616161")

        st.markdown(
            f'<div style="border-left: 4px solid {badge_color}; padding: 8px 16px; '
            f'margin: 4px 0; background-color: rgba(0,0,0,0.02); border-radius: 4px;">'
            f'Claim #{claim_number} -- {equip_name} -- {store_label}<br>'
            f'Status: <strong style="color: {badge_color};">'
            f'{status.replace("_", " ").title()}</strong> | Filed: {created}'
            f'</div>',
            unsafe_allow_html=True,
        )

        if claim.get("notes"):
            st.caption(f"Notes: {claim['notes']}")


# ------------------------------------------------------------------
# Tab 4: AI Lookup
# ------------------------------------------------------------------

def _render_ai_lookup(equipment: list[dict], user: dict):
    """Manual AI warranty research tool."""
    st.markdown("### AI Warranty Research")
    st.caption(
        "Enter equipment details to research typical warranty coverage "
        "using AI. Results can be saved to your database."
    )

    from config.settings import _get_secret
    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        st.warning(
            "AI warranty lookup is not configured. "
            "Set the ANTHROPIC_API_KEY environment variable to enable this feature."
        )
        return

    # Show Tavily status
    tavily_key = _get_secret("TAVILY_API_KEY")
    if tavily_key and tavily_key != "your_tavily_api_key_here":
        st.caption("Web search enabled (Tavily) -- results will include real manufacturer sources.")
    else:
        st.caption("Web search not configured. AI will use training data only. Add TAVILY_API_KEY for better results.")

    # Option: pick from existing equipment or enter manually
    lookup_mode = st.radio(
        "Lookup source:",
        options=["Select existing equipment", "Enter details manually"],
        horizontal=True,
        key="lookup_mode",
    )

    equipment_data = {}
    selected_equipment_id = None

    if lookup_mode == "Select existing equipment":
        if not equipment:
            st.info("No equipment available.")
            return

        equip_options = {}
        for e in equipment:
            store = e.get("stores") or {}
            label = (
                f"{e.get('name', 'Unknown')} -- "
                f"{e.get('manufacturer', '')} "
                f"({store.get('store_number', '?')} - {store.get('name', '')})"
            )
            equip_options[e["id"]] = label

        selected_equipment_id = st.selectbox(
            "Equipment",
            options=list(equip_options.keys()),
            format_func=lambda x: equip_options[x],
            key="ai_lookup_equip",
        )

        if selected_equipment_id:
            item = next((e for e in equipment if e["id"] == selected_equipment_id), {})
            equipment_data = {
                "equipment_id": selected_equipment_id,
                "equipment_name": item.get("name", ""),
                "manufacturer": item.get("manufacturer", ""),
                "model": item.get("model", ""),
                "serial_number": item.get("serial_number", ""),
                "install_date": item.get("install_date", ""),
                "category": item.get("category", ""),
            }
            st.caption(
                f"Manufacturer: {equipment_data['manufacturer'] or 'N/A'} | "
                f"Model: {equipment_data['model'] or 'N/A'} | "
                f"Serial: {equipment_data['serial_number'] or 'N/A'} | "
                f"Installed: {equipment_data['install_date'] or 'N/A'}"
            )
    else:
        col1, col2 = st.columns(2)
        with col1:
            eq_name = st.text_input("Equipment Name", placeholder="e.g., Fryer", key="ai_eq_name")
            eq_mfr = st.text_input("Manufacturer", placeholder="e.g., Henny Penny", key="ai_eq_mfr")
            eq_model = st.text_input("Model", placeholder="e.g., OFE-322", key="ai_eq_model")
        with col2:
            eq_serial = st.text_input("Serial Number", placeholder="e.g., ABC-12345", key="ai_eq_serial")
            eq_install = st.date_input("Install Date", value=None, key="ai_eq_install")
            eq_category = st.text_input("Category", placeholder="e.g., BOH", key="ai_eq_category")

        equipment_data = {
            "equipment_name": eq_name or "",
            "manufacturer": eq_mfr or "",
            "model": eq_model or "",
            "serial_number": eq_serial or "",
            "install_date": eq_install.isoformat() if eq_install else "",
            "category": eq_category or "",
        }

    # Research button
    if st.button("Research Warranty", type="primary", key="ai_research_btn"):
        if not equipment_data.get("manufacturer") and not equipment_data.get("equipment_name"):
            st.error("Please provide at least an equipment name or manufacturer.")
            return

        with st.spinner("Researching warranty information with AI..."):
            result = check_warranty_status(equipment_data)

        st.session_state["ai_lookup_result"] = result
        st.session_state["ai_lookup_equip_id"] = selected_equipment_id

    # Display results
    result = st.session_state.get("ai_lookup_result")
    if not result:
        return

    st.markdown("---")
    st.markdown("### Results")

    recommendation = result.get("recommendation", "")

    if result.get("has_db_warranty"):
        st.markdown(
            f'<div style="background-color: #1B5E20; color: white; padding: 12px 16px; '
            f'border-radius: 8px; margin: 8px 0;">'
            f'<strong>Active Warranty on File</strong><br>{recommendation}</div>',
            unsafe_allow_html=True,
        )
    elif result.get("ai_lookup_performed") and result.get("ai_result"):
        ai = result["ai_result"]
        confidence = ai.get("confidence", "low")

        if ai.get("likely_under_warranty") and confidence in ("high", "medium"):
            bg = "#1B5E20" if confidence == "high" else "#F57F17"
            label = "Likely Under Warranty" if confidence == "high" else "Warranty Status Uncertain"
        else:
            bg = "#B71C1C"
            label = "Warranty Likely Expired"

        # Confidence badge
        conf_colors = {"high": "#1B5E20", "medium": "#F57F17", "low": "#B71C1C"}
        conf_color = conf_colors.get(confidence, "#616161")

        st.markdown(
            f'<div style="background-color: {bg}; color: white; padding: 12px 16px; '
            f'border-radius: 8px; margin: 8px 0;">'
            f'<strong>{label}</strong> '
            f'<span style="background-color: {conf_color}; color: white; '
            f'padding: 2px 8px; border-radius: 12px; font-size: 0.8em; '
            f'margin-left: 8px;">{confidence.upper()} confidence</span>'
            f'<br>{recommendation}</div>',
            unsafe_allow_html=True,
        )

        # Detail table
        col1, col2 = st.columns(2)
        with col1:
            warranty_period = ai.get("warranty_period") or ai.get("typical_warranty_period", "N/A")
            st.write(f"**Warranty Period:** {warranty_period}")
            st.write(f"**Coverage Type:** {ai.get('coverage_type', 'N/A')}")
            st.write(f"**Estimated Expiry:** {ai.get('estimated_expiry', 'N/A')}")
        with col2:
            st.write(f"**Manufacturer Contact:** {ai.get('manufacturer_contact', 'N/A')}")
            st.write(f"**Claim Process:** {ai.get('claim_process', 'N/A')}")
        if ai.get("notes"):
            st.write(f"**Notes:** {ai['notes']}")

        # Web search indicator
        if ai.get("web_search_used"):
            st.caption("Results based on live web search + AI analysis")
        else:
            st.caption("Results based on AI training data only (no web search)")

        # Sources section
        source_urls = ai.get("source_urls", [])
        if source_urls:
            st.markdown("#### Sources")
            for url in source_urls:
                # Display as clickable link
                display_url = url if len(url) <= 80 else url[:77] + "..."
                st.markdown(f"- [{display_url}]({url})")

        # Save to database option
        equip_id = st.session_state.get("ai_lookup_equip_id")
        if equip_id and result.get("ai_result"):
            st.markdown("---")
            if st.button("Save Warranty Info to Database", key="save_ai_warranty"):
                success = save_warranty_from_ai(equip_id, result["ai_result"], user["id"])
                if success:
                    st.success("Warranty information saved to database!")
                    # Clear caches
                    get_equipment_for_client.clear()
                    st.session_state.pop("ai_lookup_result", None)
                    st.rerun()
                else:
                    st.error("Failed to save warranty info. Please try again.")
        elif not equip_id:
            st.caption(
                "To save warranty info to the database, use the "
                "'Select existing equipment' option above."
            )
    else:
        st.markdown(
            f'<div style="background-color: #616161; color: white; padding: 12px 16px; '
            f'border-radius: 8px; margin: 8px 0;">'
            f'<strong>No Warranty Info</strong><br>{recommendation}</div>',
            unsafe_allow_html=True,
        )
