"""
Ticket Dashboard -- Admin/Property Manager view for managing all tickets.
Includes filtering, assignment, and ticket detail management.
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user, get_client
from database.tenant import get_effective_client_id
from database.stores import get_stores
from database.tickets import get_tickets_for_client, get_ticket, get_ticket_comments, add_comment, update_ticket
from database.users import get_users_for_client
from database.contractors import get_contractors
from database.work_orders import create_work_order
from database.audit import log_action
from components.ticket_card import render_ticket_card, render_ticket_detail
from theme.branding import render_header
from utils.constants import TICKET_STATUSES, STATUS_LABELS, URGENCY_LEVELS
from database.cost_estimation import get_cost_estimate_details
from utils.permissions import require_permission, can_manage_tickets
from utils.helpers import format_currency


def render():
    render_header("Ticket Dashboard", "Manage all repair requests")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    require_permission(can_manage_tickets, "You do not have access to the ticket dashboard.")

    client_id = get_effective_client_id()
    if not client_id:
        st.warning("No client context selected.")
        return

    # Check if viewing a specific ticket
    if "dashboard_ticket_id" in st.session_state:
        _render_management_view(st.session_state["dashboard_ticket_id"], user, client_id)
        return

    # ---- Filters ----
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        stores = get_stores(client_id)
        store_options = {"all": "All Stores"} | {
            s["id"]: f"{s['store_number']} - {s['name']}" for s in stores
        }
        store_filter = st.selectbox(
            "Store", list(store_options.keys()),
            format_func=lambda x: store_options[x],
        )

    with col2:
        status_options = {"all": "All Statuses"} | {s: STATUS_LABELS[s] for s in TICKET_STATUSES}
        status_filter = st.selectbox(
            "Status", list(status_options.keys()),
            format_func=lambda x: status_options[x],
        )

    with col3:
        cat_options = {"all": "All Categories"} | {u: u for u in URGENCY_LEVELS}
        # Use urgency levels from constants as a simple filter
        urg_filter = st.selectbox(
            "Urgency", list(cat_options.keys()),
            format_func=lambda x: cat_options[x],
        )

    with col4:
        # Date range filter
        date_range = st.date_input("Date Range", value=[], key="dash_date_range")

    # Build filter dict
    filters = {}
    if store_filter != "all":
        filters["store_id"] = store_filter
    if status_filter != "all":
        filters["status"] = status_filter
    if urg_filter != "all":
        filters["urgency"] = urg_filter

    tickets = get_tickets_for_client(client_id, filters if filters else None)

    # ---- Summary metrics ----
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        submitted = sum(1 for t in tickets if t["status"] == "submitted")
        st.metric("New", submitted)
    with m2:
        in_progress = sum(
            1 for t in tickets
            if t["status"] in ("troubleshooting", "warranty_check", "assigned", "pending_approval", "approved", "in_progress")
        )
        st.metric("In Progress", in_progress)
    with m3:
        emergency = sum(
            1 for t in tickets
            if t.get("urgency") == "911 Emergency"
            and t["status"] not in ("completed", "closed")
        )
        st.metric("Emergencies", emergency)
    with m4:
        st.metric("Total", len(tickets))

    # ---- Ticket list ----
    st.markdown("---")

    if not tickets:
        st.info("No tickets match your filters.")
        return

    for ticket in tickets:
        col_card, col_action = st.columns([4, 1])
        with col_card:
            render_ticket_card(ticket)
        with col_action:
            if st.button("Manage", key=f"manage_{ticket['id']}", use_container_width=True):
                st.session_state["dashboard_ticket_id"] = ticket["id"]
                st.rerun()


def _render_management_view(ticket_id: str, user: dict, client_id: str):
    """Render the management/detail view for a ticket."""
    if st.button("< Back to Dashboard"):
        del st.session_state["dashboard_ticket_id"]
        st.rerun()

    ticket = get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket not found.")
        return

    # Get photos
    photos = _get_ticket_photos(ticket_id)
    comments = get_ticket_comments(ticket_id)
    approvals = _get_ticket_approvals(ticket_id)

    render_ticket_detail(ticket, photos, comments, approvals)

    # ---- Management Actions ----
    st.markdown("---")
    st.markdown("### Management Actions")

    tab_assign, tab_cost, tab_status, tab_workorder, tab_comment = st.tabs(
        ["Assign", "Cost Estimate", "Status", "Work Order", "Comment"]
    )

    with tab_assign:
        # Get users for this client who can be assigned
        client_users = get_users_for_client(client_id)
        if client_users:
            st.markdown("**Assign to team member:**")
            user_options = {u["id"]: f"{u['full_name']} ({u.get('client_role', 'N/A')})" for u in client_users}
            selected_user = st.selectbox(
                "Select team member",
                options=list(user_options.keys()),
                format_func=lambda x: user_options[x],
                key="assign_user",
            )
            if st.button("Assign", key="do_assign", use_container_width=True):
                result = update_ticket(ticket_id, {"assigned_to": selected_user, "status": "assigned"})
                if result:
                    log_action(client_id, user["id"], "update", "ticket", ticket_id,
                               {"action": "assigned", "assigned_to": selected_user})
                    st.success(f"Assigned to {user_options[selected_user]}")
                    st.rerun()
                else:
                    st.error("Failed to assign ticket.")
        else:
            st.info("No team members found for this client.")

    with tab_cost:
        # Historical cost estimate from past repairs
        ticket_category = ticket.get("category", "")
        equip_name = None
        if ticket.get("equipment") and isinstance(ticket["equipment"], dict):
            equip_name = ticket["equipment"].get("name")
        cost_details = get_cost_estimate_details(client_id, ticket_category, equip_name) if ticket_category else None

        if cost_details:
            est = cost_details["estimate"]
            confidence = "low confidence" if est["low_confidence"] else f"{est['count']} repairs"
            st.info(
                f"Historical estimate ({confidence}): "
                f"${est['min']:,.0f} - ${est['max']:,.0f} (avg: ${est['avg']:,.0f})"
            )

        # Show comparison if actual cost is filled in
        actual = ticket.get("actual_cost") or 0
        current_est = ticket.get("estimated_cost") or 0
        if actual > 0 and cost_details:
            est = cost_details["estimate"]
            st.markdown(
                f"**Estimated range:** ${est['min']:,.0f} - ${est['max']:,.0f} | "
                f"**User estimate:** {format_currency(current_est)} | "
                f"**Actual:** {format_currency(actual)}"
            )
        elif actual > 0 and current_est > 0:
            st.markdown(
                f"**User estimate:** {format_currency(current_est)} | "
                f"**Actual:** {format_currency(actual)}"
            )

        new_estimate = st.number_input(
            "Estimated Cost ($)", min_value=0.0, value=float(current_est), step=50.0,
        )
        if cost_details:
            st.caption(
                f"Suggested range: ${cost_details['estimate']['min']:,.0f} - "
                f"${cost_details['estimate']['max']:,.0f}"
            )
        if st.button("Update Estimate", use_container_width=True):
            update_ticket(ticket_id, {"estimated_cost": new_estimate})
            st.success(f"Estimate updated to {format_currency(new_estimate)}")
            st.rerun()

        new_actual = st.number_input(
            "Actual Cost ($)", min_value=0.0, value=float(actual), step=50.0,
        )
        if st.button("Update Actual Cost", use_container_width=True):
            update_ticket(ticket_id, {"actual_cost": new_actual})
            st.success(f"Actual cost updated to {format_currency(new_actual)}")
            st.rerun()

    with tab_status:
        current_status = ticket.get("status", "submitted")
        new_status = st.selectbox(
            "Change Status",
            options=TICKET_STATUSES,
            index=TICKET_STATUSES.index(current_status) if current_status in TICKET_STATUSES else 0,
            format_func=lambda x: STATUS_LABELS.get(x, x),
        )
        if st.button("Update Status", use_container_width=True):
            update_ticket(ticket_id, {"status": new_status})
            log_action(client_id, user["id"], "update", "ticket", ticket_id,
                       {"status_change": f"{current_status} -> {new_status}"})
            st.success(f"Status updated to {STATUS_LABELS.get(new_status, new_status)}")
            st.rerun()

    with tab_workorder:
        st.markdown("**Issue Work Order to Contractor**")
        contractors = get_contractors({"active_only": True})

        if contractors:
            contractor_options = {
                c["id"]: f"{'* ' if c.get('is_preferred') else ''}{c['company_name']} ({c.get('avg_rating', 0):.1f}/5)"
                for c in contractors
            }
            selected_contractor = st.selectbox(
                "Select Contractor",
                options=list(contractor_options.keys()),
                format_func=lambda x: contractor_options[x],
            )
            wo_amount = st.number_input("Work Order Amount ($)", min_value=0.0, step=50.0, key="wo_amount")
            wo_notes = st.text_area("Notes", key="wo_notes", placeholder="Special instructions for the contractor...")

            if st.button("Issue Work Order", type="primary", use_container_width=True):
                wo = create_work_order({
                    "ticket_id": ticket_id,
                    "client_id": client_id,
                    "contractor_id": selected_contractor,
                    "amount": wo_amount,
                    "notes": wo_notes or None,
                })
                if wo:
                    update_ticket(ticket_id, {"status": "in_progress"})
                    log_action(client_id, user["id"], "create", "work_order", wo["id"],
                               {"ticket_id": ticket_id, "contractor_id": selected_contractor})
                    st.success("Work order issued!")
                    st.rerun()
                else:
                    st.error("Failed to create work order.")
        else:
            st.info("No contractors found. Add contractors in the Contractor Directory.")

    with tab_comment:
        new_comment = st.text_area(
            "Add Management Note", key="mgmt_comment",
            placeholder="Internal note or update...",
        )
        is_internal = st.checkbox("Internal note (visible to management only)", value=True, key="mgmt_internal")
        if st.button("Post Comment", key="post_mgmt_comment", use_container_width=True):
            if new_comment and new_comment.strip():
                result = add_comment(ticket_id, user["id"], new_comment.strip(), is_internal=is_internal)
                if result:
                    st.success("Comment added!")
                    st.rerun()
                else:
                    st.error("Failed to add comment.")


def _get_ticket_photos(ticket_id: str) -> list[dict]:
    """Fetch photos for a ticket."""
    try:
        sb = get_client()
        result = (
            sb.table("ticket_photos")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("uploaded_at")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def _get_ticket_approvals(ticket_id: str) -> list[dict]:
    """Fetch approval records for a ticket."""
    try:
        sb = get_client()
        result = (
            sb.table("approvals")
            .select("*, users:approver_id(full_name)")
            .eq("ticket_id", ticket_id)
            .order("step_order")
            .execute()
        )
        return result.data or []
    except Exception:
        return []
