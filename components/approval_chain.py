"""Approval workflow display and action components."""

import streamlit as st
from database.supabase_client import get_current_user, get_client
from database.approvals import (
    approve_ticket, reject_ticket, check_all_approved,
    initiate_approval_chain, get_pending_approvals,
)
from database.tickets import update_ticket
from utils.constants import APPROVAL_LEVELS


def _get_approvals_for_ticket(ticket_id: str) -> list[dict]:
    """Fetch all approval records for a specific ticket."""
    try:
        sb = get_client()
        result = (
            sb.table("approvals")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("step_order")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def render_approval_actions(ticket_id: str, ticket_status: str):
    """Render approval action buttons for the current user's role level."""
    user = get_current_user()
    if not user:
        return

    tier = user.get("user_tier", "")
    if tier == "psp":
        user_role = user.get("psp_role", "")
    else:
        user_role = user.get("client_role", "")

    approvals = _get_approvals_for_ticket(ticket_id)

    if not approvals:
        return

    # Find the current user's relevant approval
    my_approval = None
    for a in approvals:
        if a.get("role_required") == user_role and a["status"] == "pending":
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
    role_required = my_approval.get("role_required", "")
    level_idx = APPROVAL_LEVELS.index(role_required) if role_required in APPROVAL_LEVELS else -1
    for i in range(level_idx):
        prev_level = APPROVAL_LEVELS[i]
        prev_approval = next((a for a in approvals if a.get("role_required") == prev_level), None)
        if prev_approval and prev_approval["status"] != "approved":
            st.info(f"Waiting for {prev_level.upper()} approval before you can approve.")
            return

    st.markdown("---")
    st.markdown("### Your Approval")

    notes = st.text_area("Notes (optional)", key=f"approval_notes_{ticket_id}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve", key=f"approve_{ticket_id}", type="primary", width="stretch"):
            approve_ticket(my_approval["id"], user["id"], notes=notes or None)
            _check_all_approved(ticket_id)
            st.success("Approved!")
            st.rerun()
    with col2:
        if st.button("Reject", key=f"reject_{ticket_id}", width="stretch"):
            reject_ticket(my_approval["id"], user["id"], notes=notes or None)
            update_ticket(ticket_id, {"status": "rejected"})
            st.error("Rejected.")
            st.rerun()


def initiate_approval(ticket_id: str, client_id: str, estimated_cost: float):
    """Create the approval chain and update ticket status."""
    initiate_approval_chain(ticket_id, client_id, estimated_cost)
    update_ticket(ticket_id, {"status": "pending_approval"})


def _check_all_approved(ticket_id: str):
    """Check if all approval levels are approved and update ticket status."""
    if check_all_approved(ticket_id):
        update_ticket(ticket_id, {"status": "approved"})
