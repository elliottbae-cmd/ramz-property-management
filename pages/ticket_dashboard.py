"""
Ticket Dashboard -- Admin/Property Manager view for managing all tickets.
Includes filtering, assignment, and ticket detail management.
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user, get_client
from database.tenant import get_effective_client_id
from database.stores import get_stores_for_user
from database.tickets import get_tickets_for_client, get_ticket, get_ticket_comments, get_ticket_photos, get_ticket_approvals, add_comment, update_ticket
from database.contractors import get_contractors
from utils.contractor_matcher import find_matching_contractors
from database.work_orders import create_work_order, get_work_orders
from database.audit import log_action
from database.approvals import initiate_approval_chain
from components.ticket_card import render_ticket_card, render_ticket_detail
from components.document_upload import render_document_upload, render_document_list
from theme.branding import render_header
from utils.constants import TICKET_STATUSES, STATUS_LABELS, STATUS_COLORS, URGENCY_LEVELS
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
        stores = get_stores_for_user(user, client_id)
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
        urg_options = {"all": "All Urgencies"} | {u: u for u in URGENCY_LEVELS}
        urg_filter = st.selectbox(
            "Urgency", list(urg_options.keys()),
            format_func=lambda x: urg_options[x],
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
            # Visual indicator for warranty_check status
            if ticket.get("status") == "warranty_check":
                st.markdown(
                    '<span style="background-color:#C4A04D; color:white; padding:2px 8px; '
                    'border-radius:12px; font-size:0.75rem; font-weight:600;">'
                    'AWAITING WARRANTY REVIEW</span>',
                    unsafe_allow_html=True,
                )
            elif ticket.get("warranty_checked"):
                st.markdown(
                    '<span style="background-color:#1B5E20; color:white; padding:2px 8px; '
                    'border-radius:12px; font-size:0.75rem; font-weight:600;">'
                    'WARRANTY REVIEWED</span>',
                    unsafe_allow_html=True,
                )
            render_ticket_card(ticket)
        with col_action:
            if st.button("Manage", key=f"manage_{ticket['id']}", width="stretch"):
                st.session_state["dashboard_ticket_id"] = ticket["id"]
                st.rerun()


def _render_work_order_form(ticket: dict, ticket_id: str, client_id: str, user: dict):
    """Render the contractor selection and work order issue form."""
    store = ticket.get("stores") or {}
    category = ticket.get("category", "")
    equipment_name = (ticket.get("equipment") or {}).get("name", "")
    matched = find_matching_contractors(store, category, equipment_name=equipment_name)

    if matched:
        match_labels = {
            "city": "📍 city match",
            "zip": "📍 zip match",
            "state": "🗺 state match",
            "exception": "✅ exception",
        }
        contractor_options = {
            c["id"]: (
                f"{'★ ' if c.get('is_preferred') else ''}"
                f"{c['company_name']} "
                f"({c.get('avg_rating', 0):.1f}/5 · {match_labels.get(match_type, match_type)})"
            )
            for c, match_type in matched
        }
        match_term = equipment_name or category
        st.caption(f"{len(matched)} contractor(s) matched for **{match_term}** at **{store.get('city', '')}, {store.get('state', '')}**")
    else:
        all_contractors = get_contractors({"active_only": True})
        if all_contractors:
            st.warning(
                f"No contractors matched **{equipment_name or category}** "
                f"at **{store.get('city', '')}, {store.get('state', '')}**. "
                "Showing all active contractors — consider adding a matched contractor in the Contractor Directory."
            )
            contractor_options = {
                c["id"]: f"{'★ ' if c.get('is_preferred') else ''}{c['company_name']} ({c.get('avg_rating', 0):.1f}/5)"
                for c in all_contractors
            }
        else:
            st.info("No contractors found. Add contractors in the Contractor Directory.")
            return

    selected_contractor = st.selectbox(
        "Select Contractor",
        options=list(contractor_options.keys()),
        format_func=lambda x: contractor_options[x],
        key=f"wo_contractor_{ticket_id}",
    )
    wo_amount = st.number_input("Work Order Amount ($)", min_value=0.0, step=50.0, key=f"wo_amount_{ticket_id}")
    wo_notes = st.text_area("Notes", key=f"wo_notes_{ticket_id}", placeholder="Special instructions for the contractor...")

    if st.button("Issue Work Order", type="primary", width="stretch", key=f"wo_submit_{ticket_id}"):
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


def _render_management_view(ticket_id: str, user: dict, client_id: str):
    """Render the management/detail view for a ticket."""
    if st.button("< Back to Dashboard"):
        st.session_state.pop("dashboard_ticket_id", None)
        st.rerun()

    ticket = get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket not found.")
        return

    # Get photos
    photos = get_ticket_photos(ticket_id)
    comments = get_ticket_comments(ticket_id)
    approvals = get_ticket_approvals(ticket_id)

    render_ticket_detail(ticket, photos, comments, approvals)

    # ---- Warranty info display ----
    if ticket.get("warranty_checked"):
        # Show warranty details from comments
        warranty_comments = [
            c for c in comments
            if "warranty" in (c.get("comment") or "").lower()
            and "under warranty" in (c.get("comment") or "").lower()
            and not c.get("is_internal")
        ]
        if warranty_comments:
            st.markdown(
                '<div style="background-color:#1B5E20; color:white; padding:12px 16px; '
                'border-radius:8px; margin:8px 0;">'
                '<strong>Warranty Information</strong></div>',
                unsafe_allow_html=True,
            )
            for wc in warranty_comments:
                st.info(wc.get("comment", ""))
    elif ticket.get("status") == "warranty_check":
        st.markdown(
            '<div style="background-color:#C4A04D; color:white; padding:12px 16px; '
            'border-radius:8px; margin:8px 0;">'
            '<strong>Awaiting Warranty Review</strong><br>'
            'This ticket is pending warranty review by the PSP team.</div>',
            unsafe_allow_html=True,
        )

    # ---- Management Actions ----
    st.markdown("---")
    st.markdown("### Management Actions")

    tab_assign, tab_cost, tab_status, tab_workorder, tab_comment, tab_closeout = st.tabs(
        ["Assign", "Cost Estimate", "Status", "Work Order", "Comment", "Close Out"]
    )

    with tab_assign:
        # Assignment is PSP-only — PSP staff coordinate repairs, client users (DM/VP etc.) approve
        psp_users = []
        try:
            sb = get_client()
            psp_access = (
                sb.table("psp_client_access")
                .select("psp_user_id, users(id, full_name, psp_role)")
                .eq("client_id", client_id)
                .execute()
            )
            for row in (psp_access.data or []):
                u = row.get("users") or {}
                if u.get("id"):
                    psp_users.append({
                        "id": u["id"],
                        "full_name": u.get("full_name", "Unknown"),
                        "psp_role": u.get("psp_role", "psp"),
                    })
        except Exception:
            pass

        if psp_users:
            st.markdown("**Assign to PSP team member:**")
            user_options = {
                u["id"]: f"{u['full_name']} ({u['psp_role'].replace('_', ' ').title()})"
                for u in psp_users
            }
            selected_user = st.selectbox(
                "Select team member",
                options=list(user_options.keys()),
                format_func=lambda x: user_options[x],
                key="assign_user",
            )
            if st.button("Assign", key="do_assign", width="stretch"):
                result = update_ticket(ticket_id, {"assigned_to": selected_user, "status": "assigned"})
                if result:
                    log_action(client_id, user["id"], "update", "ticket", ticket_id,
                               {"action": "assigned", "assigned_to": selected_user})
                    st.success(f"Assigned to {user_options[selected_user]}")
                    st.rerun()
                else:
                    st.error("Failed to assign ticket.")
        else:
            st.info("No PSP team members are assigned to this client yet. Add PSP users in PSP Admin → Client Access.")

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
        if st.button("Update Estimate", width="stretch"):
            update_ticket(ticket_id, {"estimated_cost": new_estimate})
            # Trigger approval chain when estimate is first entered
            if new_estimate > 0:
                existing = get_ticket_approvals(ticket_id)
                if not existing:
                    chain = initiate_approval_chain(ticket_id, client_id, new_estimate)
                    if chain:
                        update_ticket(ticket_id, {"status": "pending_approval"})
                        st.info("Approval chain initiated — DM has been notified.")
            st.success(f"Estimate updated to {format_currency(new_estimate)}")
            st.rerun()

        new_actual = st.number_input(
            "Actual Cost ($)", min_value=0.0, value=float(actual), step=50.0,
        )
        if st.button("Update Actual Cost", width="stretch"):
            update_ticket(ticket_id, {"actual_cost": new_actual})
            st.success(f"Actual cost updated to {format_currency(new_actual)}")
            st.rerun()

        # Document attachments — estimates and invoices
        st.markdown("---")
        st.markdown("**Documents**")
        render_document_list(ticket_id)
        render_document_upload(
            ticket_id=ticket_id,
            client_id=client_id,
            user_id=user["id"],
            allowed_types=["estimate", "invoice", "other"],
            label="Attach Estimate or Invoice",
        )

    with tab_status:
        current_status = ticket.get("status", "submitted")
        new_status = st.selectbox(
            "Change Status",
            options=TICKET_STATUSES,
            index=TICKET_STATUSES.index(current_status) if current_status in TICKET_STATUSES else 0,
            format_func=lambda x: STATUS_LABELS.get(x, x),
        )
        if st.button("Update Status", width="stretch"):
            update_ticket(ticket_id, {"status": new_status})
            log_action(client_id, user["id"], "update", "ticket", ticket_id,
                       {"status_change": f"{current_status} -> {new_status}"})
            st.success(f"Status updated to {STATUS_LABELS.get(new_status, new_status)}")
            st.rerun()

    with tab_workorder:
        st.markdown("**Issue Work Order to Contractor**")

        # Check for existing work orders on this ticket
        existing_wos = get_work_orders(client_id, ticket_id=ticket_id)
        if existing_wos:
            for wo in existing_wos:
                contractor = wo.get("contractors") or {}
                st.markdown(
                    f'<div style="background:#F0FFF4; border:1px solid #27AE60; '
                    f'border-radius:8px; padding:12px 16px; margin-bottom:0.75rem;">'
                    f'<strong>Work Order Issued</strong><br>'
                    f'Contractor: <strong>{contractor.get("company_name", "N/A")}</strong>'
                    f'{(" · " + contractor.get("phone")) if contractor.get("phone") else ""}<br>'
                    f'Amount: <strong>${wo.get("amount") or 0:,.2f}</strong> · '
                    f'Status: <strong>{wo.get("status", "").replace("_", " ").title()}</strong> · '
                    f'Issued: {(wo.get("issued_at") or "")[:10]}'
                    f'{("<br>Notes: " + wo["notes"]) if wo.get("notes") else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with st.expander("⚠️ Issue an additional work order", expanded=False):
                st.caption("Only do this if a second contractor is needed for the same ticket.")
                _render_work_order_form(ticket, ticket_id, client_id, user)
            return

        _render_work_order_form(ticket, ticket_id, client_id, user)

    with tab_comment:
        new_comment = st.text_area(
            "Add Management Note", key="mgmt_comment",
            placeholder="Internal note or update...",
        )
        is_internal = st.checkbox("Internal note (visible to management only)", value=True, key="mgmt_internal")
        if st.button("Post Comment", key="post_mgmt_comment", width="stretch"):
            if new_comment and new_comment.strip():
                result = add_comment(ticket_id, user["id"], new_comment.strip(), is_internal=is_internal)
                if result:
                    st.success("Comment added!")
                    st.rerun()
                else:
                    st.error("Failed to add comment.")

    with tab_closeout:
        current_status = ticket.get("status", "")
        if current_status in ("completed", "closed"):
            st.success(f"This ticket is already **{STATUS_LABELS.get(current_status, current_status)}**.")
            st.markdown(f"**Resolution notes:** {ticket.get('resolution_notes') or '(none)'}")
            if ticket.get("resolved_at"):
                st.caption(f"Closed: {ticket['resolved_at'][:10]}")
            st.markdown("---")
            st.markdown("**Attachments**")
            render_document_list(ticket_id)
            return

        st.markdown("Complete this form to mark the repair as done and close the ticket.")
        st.markdown("---")

        # Actual cost (pre-fill from ticket)
        actual = ticket.get("actual_cost") or 0
        closeout_actual = st.number_input(
            "Final Actual Cost ($)",
            min_value=0.0,
            value=float(actual),
            step=50.0,
            key="closeout_actual",
            help="Enter the final invoiced amount. Updates the actual cost field.",
        )

        # Resolution notes
        resolution_notes = st.text_area(
            "Resolution Notes *",
            key="closeout_notes",
            placeholder="What was done? What was replaced or repaired? Any follow-up needed?",
            height=120,
        )

        # Contractor rating (optional)
        from database.contractors import get_contractor
        from database.work_orders import get_work_orders as _get_wos
        wos = _get_wos(client_id, ticket_id=ticket_id)
        contractor_id = None
        if wos:
            contractor_id = wos[0].get("contractor_id")
            contractor = get_contractor(contractor_id) if contractor_id else None
            if contractor:
                st.markdown("---")
                st.markdown(f"**Rate {contractor['company_name']}** (optional)")
                rating = st.slider("Overall Rating", 1, 5, 4, key="closeout_rating")
                timeliness = st.slider("Timeliness", 1, 5, 4, key="closeout_timeliness")
                quality = st.slider("Quality of Work", 1, 5, 4, key="closeout_quality")
                communication = st.slider("Communication", 1, 5, 4, key="closeout_communication")
                rating_comment = st.text_input("Comment (optional)", key="closeout_rating_comment")
                do_rate = st.checkbox("Submit rating with closeout", value=True, key="closeout_do_rate")

        # Invoice upload
        st.markdown("---")
        st.markdown("**Attach Final Invoice** (optional)")
        render_document_upload(
            ticket_id=ticket_id,
            client_id=client_id,
            user_id=user["id"],
            allowed_types=["invoice", "other"],
            label="Attach Invoice",
        )
        render_document_list(ticket_id)

        st.markdown("---")
        if st.button("✅ Close Out Ticket", type="primary", width="stretch", key="do_closeout"):
            if not resolution_notes or not resolution_notes.strip():
                st.error("Please enter resolution notes before closing out.")
            else:
                from datetime import datetime, timezone
                # Update ticket
                update_ticket(ticket_id, {
                    "status": "completed",
                    "actual_cost": closeout_actual,
                    "resolution_notes": resolution_notes.strip(),
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                })

                # Submit contractor rating if requested
                if contractor_id and wos and st.session_state.get("closeout_do_rate", True):
                    from database.contractors import add_review
                    add_review({
                        "contractor_id": contractor_id,
                        "ticket_id": ticket_id,
                        "reviewed_by": user["id"],
                        "rating": st.session_state.get("closeout_rating", 4),
                        "timeliness": st.session_state.get("closeout_timeliness", 4),
                        "quality": st.session_state.get("closeout_quality", 4),
                        "communication": st.session_state.get("closeout_communication", 4),
                        "comment": st.session_state.get("closeout_rating_comment") or None,
                    })

                log_action(client_id, user["id"], "closeout", "ticket", ticket_id,
                           {"actual_cost": closeout_actual, "resolution": resolution_notes.strip()})

                st.success("Ticket closed out successfully!")
                st.rerun()


