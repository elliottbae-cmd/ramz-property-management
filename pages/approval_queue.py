"""
Approval Queue — GM/DM/Director approval workflow.
Shows pending approvals for the current user's role level.
"""

import streamlit as st
from database.supabase_client import (
    get_current_user, get_pending_approvals_for_role, get_approvals_for_ticket,
    update_approval, update_ticket, get_ticket_by_id,
    get_ticket_photos, get_ticket_comments
)
from components.ticket_card import render_ticket_detail
from components.approval_chain import render_approval_actions
from theme.branding import render_header, urgency_badge, status_badge
from utils.helpers import time_ago, format_currency
from utils.constants import APPROVAL_LEVELS


def render():
    render_header("Approval Queue", "Review and approve repair requests")

    user = get_current_user()
    if not user:
        return

    user_role = user.get("role", "")

    # Determine which approval levels this user can act on
    if user_role == "admin":
        # Admin can approve at any level
        viewable_levels = APPROVAL_LEVELS
    elif user_role in APPROVAL_LEVELS:
        viewable_levels = [user_role]
    else:
        st.info("You don't have any pending approvals.")
        return

    # Check if viewing a specific ticket
    if "approval_ticket_id" in st.session_state:
        _render_approval_detail(st.session_state["approval_ticket_id"], user)
        return

    # Show pending approvals for each applicable level
    total_pending = 0

    for level in viewable_levels:
        pending = get_pending_approvals_for_role(level)
        if not pending:
            continue

        # Filter: only show approvals where previous levels are already approved
        actionable = []
        for approval in pending:
            ticket_id = approval.get("ticket_id")
            if _is_ready_for_level(ticket_id, level):
                actionable.append(approval)

        if not actionable:
            continue

        total_pending += len(actionable)
        st.markdown(f"### {level.upper()} Approvals ({len(actionable)} pending)")

        for approval in actionable:
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
                    <div>{ticket.get('description', '')[:150]}</div>
                    <div style="font-size: 0.85rem; color: #757575; margin-top: 0.5rem;">
                        {urgency_badge(ticket.get('urgency', ''))} |
                        {ticket.get('category', '')} |
                        {store.get('store_number', '')} - {store.get('name', '')} |
                        Est: {format_currency(ticket.get('estimated_cost'))} |
                        {time_ago(ticket.get('created_at', ''))}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("Review", key=f"review_{approval['id']}", use_container_width=True):
                    st.session_state["approval_ticket_id"] = ticket.get("id")
                    st.rerun()

    if total_pending == 0:
        st.success("No pending approvals. You're all caught up!")


def _render_approval_detail(ticket_id: str, user: dict):
    """Render the approval detail view for a ticket."""
    if st.button("< Back to Queue"):
        del st.session_state["approval_ticket_id"]
        st.rerun()

    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        st.error("Ticket not found.")
        return

    photos = get_ticket_photos(ticket_id)
    comments = get_ticket_comments(ticket_id)
    approvals = get_approvals_for_ticket(ticket_id)

    render_ticket_detail(ticket, photos, comments, approvals)

    # Render approval actions
    render_approval_actions(ticket_id, ticket.get("status", ""))


def _is_ready_for_level(ticket_id: str, level: str) -> bool:
    """Check if all previous approval levels are approved."""
    if level not in APPROVAL_LEVELS:
        return True

    level_idx = APPROVAL_LEVELS.index(level)
    if level_idx == 0:
        return True  # GM is first, always ready

    approvals = get_approvals_for_ticket(ticket_id)
    for i in range(level_idx):
        prev_level = APPROVAL_LEVELS[i]
        prev = next((a for a in approvals if a["role_level"] == prev_level), None)
        if not prev or prev["status"] != "approved":
            return False

    return True
