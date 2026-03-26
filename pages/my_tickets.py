"""
My Tickets — View tickets submitted by or assigned to the current user.
"""

import streamlit as st
from database.supabase_client import (
    get_current_user, get_tickets, get_ticket_by_id,
    get_ticket_photos, get_ticket_comments, get_approvals_for_ticket,
    add_ticket_comment
)
from components.ticket_card import render_ticket_card, render_ticket_detail
from components.photo_upload import render_photo_upload, save_photos
from theme.branding import render_header


def render():
    render_header("My Tickets", "Track your repair requests")

    user = get_current_user()
    if not user:
        return

    # Check if viewing a specific ticket
    if "selected_ticket_id" in st.session_state:
        _render_ticket_detail_view(st.session_state["selected_ticket_id"], user)
        return

    # Tabs for submitted vs assigned
    tab_submitted, tab_assigned = st.tabs(["Submitted by Me", "Assigned to Me"])

    with tab_submitted:
        tickets = get_tickets({"submitted_by": user["id"]})
        if not tickets:
            st.info("You haven't submitted any repair requests yet.")
        else:
            # Status filter
            status_filter = st.selectbox(
                "Filter by status",
                ["All"] + ["submitted", "assigned", "pending_approval", "approved",
                           "in_progress", "completed", "closed"],
                key="my_submitted_status"
            )
            if status_filter != "All":
                tickets = [t for t in tickets if t["status"] == status_filter]

            st.caption(f"{len(tickets)} ticket(s)")
            for ticket in tickets:
                render_ticket_card(ticket, on_click_key=f"view_submitted_{ticket['id']}")

    with tab_assigned:
        tickets = get_tickets({"assigned_to": user["id"]})
        if not tickets:
            st.info("No tickets are assigned to you.")
        else:
            st.caption(f"{len(tickets)} ticket(s)")
            for ticket in tickets:
                render_ticket_card(ticket, on_click_key=f"view_assigned_{ticket['id']}")


def _render_ticket_detail_view(ticket_id: str, user: dict):
    """Render the detail view for a single ticket."""
    # Back button
    if st.button("< Back to My Tickets"):
        del st.session_state["selected_ticket_id"]
        st.rerun()

    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        st.error("Ticket not found.")
        return

    photos = get_ticket_photos(ticket_id)
    comments = get_ticket_comments(ticket_id)
    approvals = get_approvals_for_ticket(ticket_id)

    render_ticket_detail(ticket, photos, comments, approvals)

    # Add comment
    st.markdown("---")
    st.markdown("**Add a Comment**")
    new_comment = st.text_area("Comment", key="new_comment", placeholder="Add an update or note...")
    if st.button("Post Comment", use_container_width=True):
        if new_comment and new_comment.strip():
            add_ticket_comment(ticket_id, user["id"], new_comment.strip())
            st.success("Comment added!")
            st.rerun()
        else:
            st.warning("Please enter a comment.")

    # Upload additional photos
    st.markdown("---")
    st.markdown("**Add More Photos**")
    additional_photos = render_photo_upload(ticket_id)
    if additional_photos and st.button("Upload Photos", use_container_width=True):
        save_photos(additional_photos, ticket_id)
        st.success("Photos uploaded!")
        st.rerun()
