"""
Warranty Review Queue -- PSP reviews warranty status before tickets enter
the normal DM/GM approval flow.

Workflow:
1. GM submits ticket -> status = "warranty_check" -> appears here
2. PSP reviews warranty (runs AI lookup, checks install date, verifies coverage)
   - UNDER WARRANTY -> saves warranty record, routes to DM & GM with instructions
   - NOT UNDER WARRANTY -> moves to normal approval chain
   - UNKNOWN -> stays in queue for later review
3. Normal approval chain continues from pending_approval status
"""

from datetime import date, datetime

import streamlit as st

from database.supabase_client import get_current_user, get_client
from database.tenant import get_effective_client_id
from database.tickets import (
    get_tickets_for_client,
    get_ticket,
    get_ticket_comments,
    add_comment,
    update_ticket,
)
from database.equipment import create_warranty, get_equipment_by_id
from database.warranty_lookup import check_warranty_status
from database.approvals import initiate_approval_chain
from database.audit import log_action
from theme.branding import render_header
from utils.permissions import require_permission, can_access_psp_admin
from utils.constants import URGENCY_COLORS


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_warranty_review_tickets(client_id: str) -> list[dict]:
    """Fetch all tickets with status = warranty_check for the client."""
    return get_tickets_for_client(client_id, filters={"status": "warranty_check"}, limit=200)


def _get_completed_today_count(client_id: str) -> int:
    """Count tickets that moved out of warranty_check today."""
    try:
        sb = get_client()
        today = date.today().isoformat()
        result = (
            sb.table("ticket_comments")
            .select("id", count="exact")
            .like("comment", "%Warranty review complete%")
            .gte("created_at", today)
            .execute()
        )
        return result.count or 0
    except Exception:
        return 0


def _get_warranties_found_this_month(client_id: str) -> int:
    """Count warranty records created this month."""
    try:
        sb = get_client()
        first_of_month = date.today().replace(day=1).isoformat()
        result = (
            sb.table("equipment_warranties")
            .select("id", count="exact")
            .gte("created_at", first_of_month)
            .execute()
        )
        return result.count or 0
    except Exception:
        return 0


# ------------------------------------------------------------------
# Main render
# ------------------------------------------------------------------

def render():
    """Render the PSP Warranty Review Queue page."""
    # Gold banner header
    st.markdown(
        '<div style="background: linear-gradient(135deg, #C4A04D, #a6863a); '
        'color: white; padding: 1rem 1.5rem; border-radius: 8px; margin-bottom: 1rem; '
        'text-align: center;">'
        '<h1 style="margin:0; font-size:1.5rem; font-weight:700;">Warranty Review Queue</h1>'
        '<p style="margin:0.25rem 0 0 0; font-size:0.85rem; opacity:0.9;">'
        'Review warranty status before approving repairs</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    require_permission(can_access_psp_admin, "Only PSP users can access the Warranty Review Queue.")

    client_id = get_effective_client_id()
    if not client_id:
        st.warning("No client context selected. Please select a client first.")
        return

    # ---- Metrics ----
    tickets = _get_warranty_review_tickets(client_id)
    pending_count = len(tickets)
    completed_today = _get_completed_today_count(client_id)
    warranties_found = _get_warranties_found_this_month(client_id)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Pending Reviews", pending_count)
    with m2:
        st.metric("Completed Today", completed_today)
    with m3:
        st.metric("Warranties Found (Month)", warranties_found)

    st.markdown("---")

    # ---- Queue list ----
    if not tickets:
        st.success("No tickets awaiting warranty review. You're all caught up!")
        return

    # Sort by urgency (911 first) then created_at
    urgency_order = {"911 Emergency": 0, "Extremely Urgent": 1, "Somewhat Urgent": 2, "Not Urgent": 3}
    tickets.sort(key=lambda t: (urgency_order.get(t.get("urgency", ""), 99), t.get("created_at", "")))

    for ticket in tickets:
        _render_ticket_review(ticket, user, client_id)


# ------------------------------------------------------------------
# Individual ticket review card
# ------------------------------------------------------------------

def _render_ticket_review(ticket: dict, user: dict, client_id: str):
    """Render one ticket's review card with expander for full review form."""
    store = ticket.get("stores") or {}
    store_label = f"{store.get('store_number', '?')} - {store.get('name', 'Unknown')}"
    urgency = ticket.get("urgency", "")
    urg_color = URGENCY_COLORS.get(urgency, "#9E9E9E")
    ticket_id = ticket["id"]
    ticket_num = ticket.get("ticket_number", "N/A")

    header_line = (
        f"Ticket #{ticket_num}  |  {store_label}  |  "
        f"{ticket.get('category', '')}  |  {urgency}"
    )

    with st.expander(header_line, expanded=False):
        # ---- Ticket summary ----
        col_info, col_urgency = st.columns([3, 1])
        with col_info:
            st.markdown(f"**Description:** {(ticket.get('description') or '')[:300]}")
            st.caption(
                f"Submitted: {ticket.get('created_at', '')[:10]}  |  "
                f"Category: {ticket.get('category', '')}  |  "
                f"Est. Cost: ${ticket.get('estimated_cost') or 0:,.0f}"
            )
        with col_urgency:
            st.markdown(
                f'<span style="background-color:{urg_color}; color:white; '
                f'padding:4px 12px; border-radius:12px; font-size:0.8rem; font-weight:600;">'
                f'{urgency}</span>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ---- Equipment info from ticket ----
        equipment_info = ticket.get("equipment") or {}
        equipment_id = ticket.get("equipment_id")

        # If we have an equipment_id, load full details
        if equipment_id and not equipment_info:
            equipment_info = get_equipment_by_id(equipment_id) or {}

        equip_name = equipment_info.get("name", "N/A")
        manufacturer = equipment_info.get("manufacturer", "")
        model = equipment_info.get("brand", "") or equipment_info.get("model", "")
        serial_number = equipment_info.get("serial_number", "")

        st.markdown("**Equipment Information**")
        ec1, ec2, ec3, ec4 = st.columns(4)
        with ec1:
            st.text_input("Equipment", value=equip_name, disabled=True, key=f"wr_equip_{ticket_id}")
        with ec2:
            st.text_input("Manufacturer", value=manufacturer or "N/A", disabled=True, key=f"wr_mfg_{ticket_id}")
        with ec3:
            st.text_input("Model", value=model or "N/A", disabled=True, key=f"wr_model_{ticket_id}")
        with ec4:
            st.text_input("Serial #", value=serial_number or "N/A", disabled=True, key=f"wr_serial_{ticket_id}")

        # ---- Install/Purchase Date ----
        st.markdown("**Install / Purchase Date**")
        install_date = st.date_input(
            "Enter the install or purchase date for this equipment",
            value=None,
            key=f"wr_install_date_{ticket_id}",
            help="Enter the date this equipment was installed or purchased. Used to calculate warranty coverage.",
        )

        # ---- AI Warranty Check ----
        st.markdown("---")

        # Session state key for AI results
        ai_key = f"wr_ai_result_{ticket_id}"

        if st.button("Run AI Warranty Check", key=f"wr_ai_btn_{ticket_id}", type="secondary"):
            equipment_data = {
                "equipment_name": equip_name,
                "manufacturer": manufacturer or "",
                "model": model or "",
                "serial_number": serial_number or "",
                "category": ticket.get("category", ""),
                "install_date": install_date.isoformat() if install_date else "Unknown",
            }
            if equipment_id:
                equipment_data["equipment_id"] = equipment_id

            with st.spinner("Running AI warranty research..."):
                ai_result = check_warranty_status(equipment_data, install_date=install_date)

            st.session_state[ai_key] = ai_result

        # Display AI results if available
        ai_result = st.session_state.get(ai_key)
        if ai_result:
            _render_ai_results(ai_result, ticket_id)

        # ---- Warranty Decision ----
        st.markdown("---")
        st.markdown("**Warranty Decision**")

        decision = st.radio(
            "Warranty Status",
            ["Under Warranty", "Not Under Warranty", "Unknown - Need More Info"],
            key=f"wr_decision_{ticket_id}",
            horizontal=True,
        )

        # Pre-fill from AI results if available
        ai_data = (ai_result or {}).get("ai_result") or {}

        if decision == "Under Warranty":
            _render_under_warranty_form(ticket_id, ai_data)
        elif decision == "Not Under Warranty":
            _render_not_under_warranty_form(ticket_id)
        else:
            _render_unknown_form(ticket_id)

        # ---- Complete Review Button ----
        st.markdown("---")
        if st.button(
            "Complete Warranty Review",
            key=f"wr_complete_{ticket_id}",
            type="primary",
            use_container_width=True,
        ):
            _complete_review(ticket, user, client_id, decision, ai_result, install_date)


# ------------------------------------------------------------------
# AI results display
# ------------------------------------------------------------------

def _render_ai_results(result: dict, ticket_id: str):
    """Display the AI warranty check results."""
    if result.get("has_db_warranty"):
        db_w = result.get("db_warranty", {})
        st.markdown(
            f'<div style="background-color:#1B5E20; color:white; padding:12px 16px; '
            f'border-radius:8px; margin:8px 0;">'
            f'<strong>Active Warranty on File</strong><br>'
            f'{result.get("recommendation", "")}</div>',
            unsafe_allow_html=True,
        )
        return

    ai = result.get("ai_result")
    if not ai:
        st.info(result.get("recommendation", "No warranty information found."))
        return

    confidence = ai.get("confidence", "low")
    conf_colors = {"high": "#1B5E20", "medium": "#F57F17", "low": "#B71C1C"}
    conf_color = conf_colors.get(confidence, "#616161")

    likely = ai.get("likely_under_warranty", False)
    if likely:
        bg = "#1B5E20" if confidence == "high" else "#F57F17"
        label = "Likely Under Warranty" if confidence == "high" else "Possibly Under Warranty"
    else:
        bg = "#B71C1C"
        label = "Warranty Likely Expired"

    st.markdown(
        f'<div style="background-color:{bg}; color:white; padding:12px 16px; '
        f'border-radius:8px; margin:8px 0;">'
        f'<strong>{label}</strong> '
        f'<span style="background-color:{conf_color}; color:white; padding:2px 8px; '
        f'border-radius:12px; font-size:0.8em; margin-left:8px;">'
        f'{confidence.upper()} confidence</span>'
        f'<br>{result.get("recommendation", "")}</div>',
        unsafe_allow_html=True,
    )

    # Details
    with st.expander("AI Research Details", expanded=True):
        d1, d2 = st.columns(2)
        with d1:
            st.write(f"**Warranty Period:** {ai.get('warranty_period', 'N/A')}")
            st.write(f"**Coverage Type:** {ai.get('coverage_type', 'N/A')}")
            st.write(f"**Estimated Expiry:** {ai.get('estimated_expiry', 'N/A')}")
        with d2:
            st.write(f"**Manufacturer Contact:** {ai.get('manufacturer_contact', 'N/A')}")
            st.write(f"**Claim Process:** {ai.get('claim_process', 'N/A')}")
            if ai.get("notes"):
                st.write(f"**Notes:** {ai['notes']}")

        if ai.get("web_search_used"):
            st.caption("Results based on live web search + AI analysis")
        else:
            st.caption("Results based on AI training data only (no web search)")

        source_urls = ai.get("source_urls", [])
        if source_urls:
            st.markdown("**Sources:**")
            for url in source_urls:
                display_url = url if len(url) <= 80 else url[:77] + "..."
                st.markdown(f"- [{display_url}]({url})")


# ------------------------------------------------------------------
# Decision sub-forms
# ------------------------------------------------------------------

def _render_under_warranty_form(ticket_id: str, ai_data: dict):
    """Render the 'Under Warranty' detail form with pre-filled AI data."""
    st.markdown("##### Warranty Details")

    warranty_provider = st.text_input(
        "Warranty Provider",
        value=ai_data.get("manufacturer_contact", "")[:100] if ai_data.get("manufacturer_contact") else "",
        key=f"wr_provider_{ticket_id}",
        help="Name of the warranty provider or manufacturer",
    )

    col_contact, col_url = st.columns(2)
    with col_contact:
        claim_contact = st.text_input(
            "Warranty Claim Contact (phone/email)",
            value=ai_data.get("manufacturer_contact", ""),
            key=f"wr_contact_{ticket_id}",
        )
    with col_url:
        claim_url = st.text_input(
            "Warranty Claim URL",
            value=(ai_data.get("source_urls", [None]) or [None])[0] or "",
            key=f"wr_claim_url_{ticket_id}",
        )

    coverage_details = st.text_area(
        "Coverage Details",
        value=(
            f"Period: {ai_data.get('warranty_period', 'N/A')}\n"
            f"Coverage: {ai_data.get('coverage_type', 'N/A')}\n"
            f"Expires: {ai_data.get('estimated_expiry', 'N/A')}"
            if ai_data else ""
        ),
        key=f"wr_coverage_{ticket_id}",
        height=100,
    )

    instructions = st.text_area(
        "Instructions for GM/DM",
        value="Contact manufacturer for warranty claim before hiring a contractor.",
        key=f"wr_instructions_{ticket_id}",
        height=80,
    )


def _render_not_under_warranty_form(ticket_id: str):
    """Render the 'Not Under Warranty' notes form."""
    st.text_area(
        "Notes (optional)",
        key=f"wr_nowarranty_notes_{ticket_id}",
        placeholder="Any additional notes about the warranty check...",
        height=80,
    )


def _render_unknown_form(ticket_id: str):
    """Render the 'Unknown' notes form."""
    st.text_area(
        "Notes - what additional info is needed?",
        key=f"wr_unknown_notes_{ticket_id}",
        placeholder="Describe what information is missing or needs verification...",
        height=80,
    )


# ------------------------------------------------------------------
# Complete review action
# ------------------------------------------------------------------

def _complete_review(
    ticket: dict,
    user: dict,
    client_id: str,
    decision: str,
    ai_result: dict | None,
    install_date: date | None,
):
    """Process the warranty review decision and update the ticket."""
    ticket_id = ticket["id"]
    user_id = user["id"]

    if decision == "Under Warranty":
        _complete_under_warranty(ticket, user, client_id, ai_result, install_date)
    elif decision == "Not Under Warranty":
        _complete_not_under_warranty(ticket, user, client_id)
    else:
        _complete_unknown(ticket, user, client_id)


def _complete_under_warranty(
    ticket: dict,
    user: dict,
    client_id: str,
    ai_result: dict | None,
    install_date: date | None,
):
    """Handle Under Warranty decision."""
    ticket_id = ticket["id"]
    user_id = user["id"]

    # Gather form values from session state
    provider = st.session_state.get(f"wr_provider_{ticket_id}", "")
    contact = st.session_state.get(f"wr_contact_{ticket_id}", "")
    claim_url = st.session_state.get(f"wr_claim_url_{ticket_id}", "")
    coverage = st.session_state.get(f"wr_coverage_{ticket_id}", "")
    instructions = st.session_state.get(f"wr_instructions_{ticket_id}", "")

    # Save warranty record to equipment_warranties table
    equipment_id = ticket.get("equipment_id")
    if equipment_id:
        today = date.today().isoformat()
        # Estimate end date: 1 year from install or today if no install date
        ai_data = (ai_result or {}).get("ai_result") or {}
        end_date = ai_data.get("estimated_expiry", "Unknown")
        if end_date == "Unknown" or not _is_valid_date(end_date):
            from datetime import timedelta
            base = install_date if install_date else date.today()
            end_date = (base + timedelta(days=365)).isoformat()

        warranty_data = {
            "equipment_id": equipment_id,
            "warranty_provider": provider or "Manufacturer",
            "start_date": install_date.isoformat() if install_date else today,
            "end_date": end_date,
            "coverage_description": coverage,
            "contact_phone": contact,
        }
        create_warranty(warranty_data)

    # Update ticket status to pending_approval and mark warranty_checked
    update_ticket(ticket_id, {
        "status": "pending_approval",
        "warranty_checked": True,
    })

    # Add internal comment with warranty details
    internal_note = (
        f"Warranty review complete - UNDER WARRANTY.\n"
        f"Provider: {provider}\n"
        f"Contact: {contact}\n"
        f"Claim URL: {claim_url}\n"
        f"Coverage: {coverage}"
    )
    add_comment(ticket_id, user_id, internal_note, is_internal=True)

    # Add comment visible to GM/DM with warranty info and instructions
    gm_dm_comment = (
        f"This equipment is under warranty with {provider}. "
        f"Please contact {contact} to file a warranty claim before proceeding with repairs.\n\n"
        f"{instructions}"
    )
    if claim_url:
        gm_dm_comment += f"\n\nWarranty claim URL: {claim_url}"
    add_comment(ticket_id, user_id, gm_dm_comment, is_internal=False)

    # Initiate normal approval chain
    estimated_cost = ticket.get("estimated_cost") or 0
    if estimated_cost > 0:
        initiate_approval_chain(ticket_id, client_id, estimated_cost)

    # Audit log
    log_action(
        client_id=client_id,
        user_id=user_id,
        action="warranty_review",
        entity_type="ticket",
        entity_id=ticket_id,
        details={"decision": "under_warranty", "provider": provider},
    )

    st.success(f"Warranty review complete for Ticket #{ticket.get('ticket_number', 'N/A')}. Routed to approval queue with warranty instructions.")
    st.rerun()


def _complete_not_under_warranty(ticket: dict, user: dict, client_id: str):
    """Handle Not Under Warranty decision."""
    ticket_id = ticket["id"]
    user_id = user["id"]

    notes = st.session_state.get(f"wr_nowarranty_notes_{ticket_id}", "")

    # Update ticket status to pending_approval
    update_ticket(ticket_id, {
        "status": "pending_approval",
        "warranty_checked": True,
    })

    # Add internal comment
    internal_note = "Warranty review complete - no active warranty found."
    if notes:
        internal_note += f"\nNotes: {notes}"
    add_comment(ticket_id, user_id, internal_note, is_internal=True)

    # Initiate normal approval chain
    estimated_cost = ticket.get("estimated_cost") or 0
    if estimated_cost > 0:
        initiate_approval_chain(ticket_id, client_id, estimated_cost)

    # Audit log
    log_action(
        client_id=client_id,
        user_id=user_id,
        action="warranty_review",
        entity_type="ticket",
        entity_id=ticket_id,
        details={"decision": "not_under_warranty"},
    )

    st.success(f"Warranty review complete for Ticket #{ticket.get('ticket_number', 'N/A')}. Moved to normal approval flow.")
    st.rerun()


def _complete_unknown(ticket: dict, user: dict, client_id: str):
    """Handle Unknown decision - keep in warranty_check status."""
    ticket_id = ticket["id"]
    user_id = user["id"]

    notes = st.session_state.get(f"wr_unknown_notes_{ticket_id}", "")

    # Keep status as warranty_check
    # Add internal comment with notes
    internal_note = "Warranty review - additional information needed."
    if notes:
        internal_note += f"\nNotes: {notes}"
    add_comment(ticket_id, user_id, internal_note, is_internal=True)

    # Audit log
    log_action(
        client_id=client_id,
        user_id=user_id,
        action="warranty_review",
        entity_type="ticket",
        entity_id=ticket_id,
        details={"decision": "unknown", "notes": notes},
    )

    st.info(f"Ticket #{ticket.get('ticket_number', 'N/A')} remains in warranty review queue for further investigation.")
    st.rerun()


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _is_valid_date(s: str) -> bool:
    """Return True if s can be parsed as YYYY-MM-DD."""
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False
