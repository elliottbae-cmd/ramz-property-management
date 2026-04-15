"""
Approval Queue -- GM/DM/Director approval workflow.
Shows pending approvals for the current user's role level.
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user
from database.approvals import get_pending_approvals, approve_ticket, reject_ticket, check_all_approved
from database.tickets import get_ticket, get_ticket_comments, get_ticket_photos, get_ticket_approvals, update_ticket
from database.audit import log_action
from database.tenant import get_effective_client_id
from components.ticket_card import render_ticket_detail
from theme.branding import render_header, urgency_badge, status_badge
from utils.helpers import time_ago, format_currency
from utils.permissions import require_permission, can_approve
from components.notifications import notify_ticket_approved


def render():
    render_header("Approval Queue", "Review and approve repair requests")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    require_permission(can_approve, "You do not have access to the approval queue.")

    # Check if viewing a specific approval
    if "approval_ticket_id" in st.session_state:
        _render_approval_detail(st.session_state["approval_ticket_id"], user)
        return

    # Get pending approvals — PSP users see all for active client
    client_id = get_effective_client_id()
    pending = get_pending_approvals(user["id"], client_id=client_id)

    if not pending:
        st.success("No pending approvals. You're all caught up!")
        return

    st.markdown(f"### {len(pending)} Pending Approval(s)")

    for approval in pending:
        ticket = approval.get("tickets", {}) or {}
        store = ticket.get("stores", {}) or {}

        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"""
            <div class="ticket-card">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                    <strong>Ticket #{ticket.get('ticket_number', 'N/A')}</strong>
                    {status_badge(ticket.get('status', ''))}
                </div>
                <div>{(ticket.get('description', '') or '')[:150]}</div>
                <div style="font-size: 0.85rem; color: #757575; margin-top: 0.5rem;">
                    {urgency_badge(ticket.get('urgency', ''))} |
                    {ticket.get('category', '')} |
                    {store.get('store_number', '')} - {store.get('name', '')} |
                    Est: {format_currency(ticket.get('estimated_cost'))} |
                    {time_ago(ticket.get('created_at', ''))}
                </div>
                <div style="font-size: 0.8rem; color: #9E9E9E; margin-top: 0.25rem;">
                    Approval level: <strong>{approval.get('role_required', '').upper()}</strong>
                    (Step {approval.get('step_order', '?')})
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("Review", key=f"review_{approval['id']}", width="stretch"):
                st.session_state["approval_ticket_id"] = ticket.get("id")
                st.session_state["approval_record_id"] = approval["id"]
                st.rerun()


def _render_approval_detail(ticket_id: str, user: dict):
    """Render the approval detail view for a ticket."""
    if st.button("< Back to Queue"):
        st.session_state.pop("approval_ticket_id", None)
        st.session_state.pop("approval_record_id", None)
        st.rerun()

    ticket = get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket not found.")
        return

    # Get photos and comments
    photos = get_ticket_photos(ticket_id)
    comments = get_ticket_comments(ticket_id)
    approvals = get_ticket_approvals(ticket_id)

    render_ticket_detail(ticket, photos, comments, approvals)

    # ---- Approval Actions ----
    st.markdown("---")
    st.markdown("### Approval Decision")

    approval_id = st.session_state.get("approval_record_id")
    if not approval_id:
        st.warning("No approval record found for this review.")
        return

    notes = st.text_area("Notes (optional)", placeholder="Reason for your decision...", key="approval_notes")

    col_approve, col_reject = st.columns(2)

    client_id = get_effective_client_id()

    with col_approve:
        if st.button("Approve", type="primary", width="stretch"):
            result = approve_ticket(approval_id, user["id"], notes=notes or None)
            if result:
                # Check if all approvals are done
                if check_all_approved(ticket_id):
                    update_ticket(ticket_id, {"status": "approved"})
                    if client_id:
                        notify_ticket_approved(ticket, client_id)

                if client_id:
                    log_action(client_id, user["id"], "approve", "ticket", ticket_id,
                               {"approval_id": approval_id})

                st.success("Approved!")
                st.session_state.pop("approval_ticket_id", None)
                st.session_state.pop("approval_record_id", None)
                st.rerun()
            else:
                st.error("Failed to approve.")

    with col_reject:
        if st.button("Reject", width="stretch"):
            result = reject_ticket(approval_id, user["id"], notes=notes or None)
            if result:
                update_ticket(ticket_id, {"status": "rejected"})

                if client_id:
                    log_action(client_id, user["id"], "reject", "ticket", ticket_id,
                               {"approval_id": approval_id, "notes": notes})

                st.success("Rejected.")
                st.session_state.pop("approval_ticket_id", None)
                st.session_state.pop("approval_record_id", None)
                st.rerun()
            else:
                st.error("Failed to reject.")


