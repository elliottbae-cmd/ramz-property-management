"""
Ticket Dashboard — Admin/Property Manager view for managing all tickets.
Includes filtering, assignment, and ticket detail management.
"""

import streamlit as st
from database.supabase_client import (
    get_current_user, get_tickets, get_ticket_by_id, get_stores,
    get_ticket_photos, get_ticket_comments, get_approvals_for_ticket,
    update_ticket, add_ticket_comment, get_property_team_workload,
    get_contractors, get_form_categories, get_form_urgency_levels,
    create_work_order
)
from components.ticket_card import render_ticket_card, render_ticket_detail
from components.approval_chain import render_approval_actions, initiate_approval
from components.notifications import notify_ticket_assigned
from theme.branding import render_header, STATUS_COLORS
from utils.constants import TICKET_STATUSES, STATUS_LABELS
from utils.helpers import format_currency


def render():
    render_header("Ticket Dashboard", "Manage all repair requests")

    user = get_current_user()
    if not user:
        return

    # Check if viewing a specific ticket
    if "dashboard_ticket_id" in st.session_state:
        _render_management_view(st.session_state["dashboard_ticket_id"], user)
        return

    # ---- Filters ----
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        stores = get_stores()
        store_options = {"all": "All Stores"} | {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}
        store_filter = st.selectbox("Store", list(store_options.keys()),
                                     format_func=lambda x: store_options[x])

    with col2:
        status_options = {"all": "All Statuses"} | {s: STATUS_LABELS[s] for s in TICKET_STATUSES}
        status_filter = st.selectbox("Status", list(status_options.keys()),
                                      format_func=lambda x: status_options[x])

    with col3:
        categories = get_form_categories()
        cat_options = {"all": "All Categories"} | {c["name"]: c["name"] for c in categories}
        cat_filter = st.selectbox("Category", list(cat_options.keys()),
                                   format_func=lambda x: cat_options[x])

    with col4:
        urgency_levels = get_form_urgency_levels()
        urg_options = {"all": "All Urgencies"} | {u["name"]: u["name"] for u in urgency_levels}
        urg_filter = st.selectbox("Urgency", list(urg_options.keys()),
                                   format_func=lambda x: urg_options[x])

    # Build filter dict
    filters = {}
    if store_filter != "all":
        filters["store_id"] = store_filter
    if status_filter != "all":
        filters["status"] = status_filter
    if cat_filter != "all":
        filters["category"] = cat_filter
    if urg_filter != "all":
        filters["urgency"] = urg_filter

    tickets = get_tickets(filters)

    # ---- Summary metrics ----
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        submitted = sum(1 for t in tickets if t["status"] == "submitted")
        st.metric("New", submitted)
    with m2:
        in_progress = sum(1 for t in tickets if t["status"] in ("assigned", "pending_approval", "approved", "in_progress"))
        st.metric("In Progress", in_progress)
    with m3:
        emergency = sum(1 for t in tickets if t.get("urgency") == "911 Emergency" and t["status"] not in ("completed", "closed"))
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


def _render_management_view(ticket_id: str, user: dict):
    """Render the management/detail view for a ticket."""
    if st.button("< Back to Dashboard"):
        del st.session_state["dashboard_ticket_id"]
        st.rerun()

    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        st.error("Ticket not found.")
        return

    photos = get_ticket_photos(ticket_id)
    comments = get_ticket_comments(ticket_id)
    approvals = get_approvals_for_ticket(ticket_id)

    render_ticket_detail(ticket, photos, comments, approvals)

    # ---- Management Actions ----
    st.markdown("---")
    st.markdown("### Management Actions")

    tab_assign, tab_cost, tab_status, tab_workorder, tab_comment = st.tabs(
        ["Assign", "Cost Estimate", "Status", "Work Order", "Comment"]
    )

    with tab_assign:
        workload = get_property_team_workload()
        if workload:
            st.markdown("**Assign to team member** (sorted by fewest open tickets):")
            for member in workload:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(member["full_name"])
                with col2:
                    st.caption(f"{member['open_tickets']} open")
                with col3:
                    if st.button("Assign", key=f"assign_{member['id']}", use_container_width=True):
                        update_ticket(ticket_id, {"assigned_to": member["id"], "status": "assigned"})
                        notify_ticket_assigned(ticket_id, member["full_name"])
                        st.success(f"Assigned to {member['full_name']}")
                        st.rerun()
        else:
            st.info("No property team members found. Add users with the Property Manager role in Admin Settings.")

    with tab_cost:
        current_est = ticket.get("estimated_cost") or 0
        new_estimate = st.number_input(
            "Estimated Cost ($)", min_value=0.0, value=float(current_est), step=50.0
        )
        if st.button("Update Estimate", use_container_width=True):
            update_ticket(ticket_id, {"estimated_cost": new_estimate})
            st.success(f"Estimate updated to {format_currency(new_estimate)}")
            st.rerun()

        actual = ticket.get("actual_cost") or 0
        new_actual = st.number_input(
            "Actual Cost ($)", min_value=0.0, value=float(actual), step=50.0
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
            format_func=lambda x: STATUS_LABELS.get(x, x)
        )
        if st.button("Update Status", use_container_width=True):
            update_ticket(ticket_id, {"status": new_status})
            st.success(f"Status updated to {STATUS_LABELS.get(new_status, new_status)}")
            st.rerun()

    with tab_workorder:
        st.markdown("**Issue Work Order to Contractor**")
        # Match contractors by category
        store = ticket.get("stores", {}) or {}
        region = store.get("region", "")
        contractors = get_contractors(trade=ticket.get("category"), region=region)

        if not contractors:
            contractors = get_contractors()  # Fall back to all contractors

        if contractors:
            contractor_options = {c["id"]: f"{'⭐ ' if c.get('is_preferred') else ''}{c['company_name']} ({c.get('avg_rating', 0):.1f}/5)" for c in contractors}
            selected_contractor = st.selectbox(
                "Select Contractor",
                options=list(contractor_options.keys()),
                format_func=lambda x: contractor_options[x]
            )
            wo_amount = st.number_input("Work Order Amount ($)", min_value=0.0, step=50.0, key="wo_amount")
            wo_notes = st.text_area("Notes", key="wo_notes", placeholder="Special instructions for the contractor...")

            if st.button("Issue Work Order", type="primary", use_container_width=True):
                create_work_order({
                    "ticket_id": ticket_id,
                    "contractor_id": selected_contractor,
                    "amount": wo_amount,
                    "notes": wo_notes,
                })
                update_ticket(ticket_id, {"status": "in_progress"})
                st.success("Work order issued!")
                st.rerun()
        else:
            st.info("No contractors found. Add contractors in the Contractor Directory.")

    with tab_comment:
        new_comment = st.text_area("Add Management Note", key="mgmt_comment",
                                    placeholder="Internal note or update...")
        if st.button("Post Comment", key="post_mgmt_comment", use_container_width=True):
            if new_comment and new_comment.strip():
                add_ticket_comment(ticket_id, user["id"], new_comment.strip())
                st.success("Comment added!")
                st.rerun()

    # Approval actions (if applicable)
    render_approval_actions(ticket_id, ticket.get("status", ""))
