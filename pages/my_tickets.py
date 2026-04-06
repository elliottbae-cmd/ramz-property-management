"""
My Tickets -- View tickets submitted by or assigned to the current user.
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user
from database.tickets import get_tickets_for_user, get_ticket, get_ticket_comments, get_ticket_photos, get_ticket_approvals, add_comment
from components.ticket_card import render_ticket_card, render_ticket_detail
from components.photo_upload import render_photo_upload, save_photos
from theme.branding import render_header
from utils.constants import STATUS_LABELS


def render():
    render_header("My Tickets", "Track your repair requests")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    # Check if viewing a specific ticket
    if "selected_ticket_id" in st.session_state:
        _render_ticket_detail_view(st.session_state["selected_ticket_id"], user)
        return

    # Fetch all tickets for this user (submitted + assigned)
    tickets = get_tickets_for_user(user["id"])

    if not tickets:
        st.info("You haven't submitted any repair requests yet.")
        return

    # Tabs for submitted vs assigned
    tab_submitted, tab_assigned = st.tabs(["Submitted by Me", "Assigned to Me"])

    with tab_submitted:
        submitted = [t for t in tickets if t.get("submitted_by") == user["id"]]
        if not submitted:
            st.info("You haven't submitted any repair requests yet.")
        else:
            # Status filter
            status_filter = st.selectbox(
                "Filter by status",
                ["All"] + list(STATUS_LABELS.keys()),
                format_func=lambda x: STATUS_LABELS.get(x, x) if x != "All" else "All Statuses",
                key="my_submitted_status",
            )
            if status_filter != "All":
                submitted = [t for t in submitted if t["status"] == status_filter]

            st.caption(f"{len(submitted)} ticket(s)")
            for ticket in submitted:
                if ticket.get("status") == "warranty_check":
                    st.markdown(
                        '<span style="background-color:#C4A04D; color:white; padding:2px 8px; '
                        'border-radius:12px; font-size:0.75rem; font-weight:600;">'
                        'UNDER WARRANTY REVIEW</span>',
                        unsafe_allow_html=True,
                    )
                render_ticket_card(ticket, on_click_key=f"view_submitted_{ticket['id']}")

    with tab_assigned:
        assigned = [t for t in tickets if t.get("assigned_to") == user["id"]]
        if not assigned:
            st.info("No tickets are assigned to you.")
        else:
            st.caption(f"{len(assigned)} ticket(s)")
            for ticket in assigned:
                render_ticket_card(ticket, on_click_key=f"view_assigned_{ticket['id']}")


def _render_ticket_detail_view(ticket_id: str, user: dict):
    """Render the detail view for a single ticket."""
    if st.button("< Back to My Tickets"):
        st.session_state.pop("selected_ticket_id", None)
        st.rerun()

    ticket = get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket not found.")
        return

    # Get photos from ticket_photos table
    photos = get_ticket_photos(ticket_id)
    comments = get_ticket_comments(ticket_id)

    # Get approvals if any
    approvals = get_ticket_approvals(ticket_id)

    render_ticket_detail(ticket, photos, comments, approvals)

    # ---- Warranty status messages ----
    if ticket.get("status") == "warranty_check":
        st.markdown(
            '<div style="background-color:#C4A04D; color:white; padding:12px 16px; '
            'border-radius:8px; margin:8px 0;">'
            '<strong>Warranty Review in Progress</strong><br>'
            'Your ticket is being reviewed for warranty coverage by the property management team.'
            '</div>',
            unsafe_allow_html=True,
        )
    elif ticket.get("warranty_checked"):
        # Show warranty details from public comments
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
                '<strong>Warranty Coverage Found</strong></div>',
                unsafe_allow_html=True,
            )
            for wc in warranty_comments:
                st.info(wc.get("comment", ""))

    # Add comment
    st.markdown("---")
    st.markdown("**Add a Comment**")
    new_comment = st.text_area("Comment", key="new_comment", placeholder="Add an update or note...")
    if st.button("Post Comment", use_container_width=True):
        if new_comment and new_comment.strip():
            result = add_comment(ticket_id, user["id"], new_comment.strip())
            if result:
                st.success("Comment added!")
                st.rerun()
            else:
                st.error("Failed to add comment.")
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


