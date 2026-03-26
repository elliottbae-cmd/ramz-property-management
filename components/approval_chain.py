"""Approval workflow display and action components."""

import streamlit as st
from database.supabase_client import (
    get_approvals_for_ticket, update_approval, update_ticket,
    get_current_user, create_approval_chain
)
from utils.constants import APPROVAL_LEVELS


def render_approval_actions(ticket_id: str, ticket_status: str):
    """Render approval action buttons for the current user's role level."""
    user = get_current_user()
    if not user:
        return

    user_role = user.get("role", "")
    approvals = get_approvals_for_ticket(ticket_id)

    if not approvals:
        return

    # Find the current user's relevant approval
    my_approval = None
    for a in approvals:
        if a["role_level"] == user_role and a["status"] == "pending":
            my_approval = a
            break

    # Admin can approve at any level
    if user_role == "admin":
        for a in approvals:
            if a["status"] == "pending":
                my_approval = a
                break

    if not my_approval:
        return

    # Check if previous levels are approved (must be sequential)
    level_idx = APPROVAL_LEVELS.index(my_approval["role_level"]) if my_approval["role_level"] in APPROVAL_LEVELS else -1
    for i in range(level_idx):
        prev_level = APPROVAL_LEVELS[i]
        prev_approval = next((a for a in approvals if a["role_level"] == prev_level), None)
        if prev_approval and prev_approval["status"] != "approved":
            st.info(f"Waiting for {prev_level.upper()} approval before you can approve.")
            return

    st.markdown("---")
    st.markdown("### Your Approval")

    notes = st.text_area("Notes (optional)", key=f"approval_notes_{ticket_id}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve", key=f"approve_{ticket_id}", type="primary", use_container_width=True):
            update_approval(my_approval["id"], "approved", user["id"], notes)
            _check_all_approved(ticket_id)
            st.success("Approved!")
            st.rerun()
    with col2:
        if st.button("Reject", key=f"reject_{ticket_id}", use_container_width=True):
            update_approval(my_approval["id"], "rejected", user["id"], notes)
            update_ticket(ticket_id, {"status": "rejected"})
            st.error("Rejected.")
            st.rerun()


def initiate_approval(ticket_id: str):
    """Create the approval chain and update ticket status."""
    create_approval_chain(ticket_id)
    update_ticket(ticket_id, {"status": "pending_approval"})


def _check_all_approved(ticket_id: str):
    """Check if all approval levels are approved and update ticket status."""
    approvals = get_approvals_for_ticket(ticket_id)
    all_approved = all(a["status"] == "approved" for a in approvals)
    if all_approved:
        update_ticket(ticket_id, {"status": "approved"})
