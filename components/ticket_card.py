"""Reusable ticket display component."""

import streamlit as st
from theme.branding import status_badge, urgency_badge
from utils.constants import STATUS_COLORS, URGENCY_COLORS
from utils.helpers import time_ago, format_currency, truncate


def render_ticket_card(ticket: dict, show_store: bool = True, on_click_key: str = None):
    """Render a compact ticket card for list views."""
    store = ticket.get("stores", {}) or {}
    status = ticket.get("status", "submitted")
    urgency = ticket.get("urgency", "")
    category = ticket.get("category", "")

    urgency_color = URGENCY_COLORS.get(urgency, "#9E9E9E")
    status_color = STATUS_COLORS.get(status, "#9E9E9E")

    store_label = f"{store.get('store_number', '')} - {store.get('name', '')}" if show_store else ""
    store_phone = store.get("phone", "") or ""
    phone_html = (
        f'<span>📞 <a href="tel:{store_phone}" style="color:#757575; text-decoration:none;">'
        f'{store_phone}</a></span>'
        if store_phone and show_store else ""
    )

    st.markdown(f"""
    <div class="ticket-card" style="border-left-color: {urgency_color};">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <span>
                <strong>#{ticket.get('ticket_number', 'N/A')}</strong>
                {"<span style='color:#757575; font-size:0.9rem; margin-left:0.5rem;'>" + store_label + "</span>" if store_label else ""}
            </span>
            {status_badge(status)}
        </div>
        <div style="font-size: 0.95rem; margin-bottom: 0.5rem;">
            {truncate(ticket.get('description', ''), 120)}
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 0.75rem; font-size: 0.8rem; color: #757575;">
            <span>{urgency_badge(urgency)}</span>
            <span>{category}</span>
            {"<span>" + store_label + "</span>" if store_label else ""}
            {phone_html}
            <span>{time_ago(ticket.get('created_at', ''))}</span>
        </div>
        {f'<div style="font-size: 0.8rem; color: #757575; margin-top: 0.25rem;">Est: {format_currency(ticket.get("estimated_cost"))}</div>' if ticket.get("estimated_cost") else ""}
    </div>
    """, unsafe_allow_html=True)

    if on_click_key:
        if st.button("View Details", key=on_click_key, width="stretch"):
            st.session_state["selected_ticket_id"] = ticket["id"]
            st.rerun()


def render_ticket_detail(ticket: dict, photos: list = None, comments: list = None, approvals: list = None):
    """Render full ticket detail view."""
    store = ticket.get("stores", {}) or {}
    submitter = ticket.get("users", {}) or {}
    equipment = ticket.get("equipment", {}) or {}

    st.markdown(f"### Ticket #{ticket.get('ticket_number', 'N/A')}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Status:** {status_badge(ticket.get('status', ''))}", unsafe_allow_html=True)
        st.markdown(f"**Urgency:** {urgency_badge(ticket.get('urgency', ''))}", unsafe_allow_html=True)
        st.markdown(f"**Category:** {ticket.get('category', 'N/A')}")
    with col2:
        store_phone = store.get("phone", "") or ""
        phone_display = (
            f' &nbsp;[📞 {store_phone}](tel:{store_phone})'
            if store_phone else ""
        )
        st.markdown(
            f"**Store:** {store.get('store_number', '')} - {store.get('name', '')}{phone_display}",
            unsafe_allow_html=True,
        )
        st.markdown(f"**Submitted by:** {submitter.get('full_name', 'N/A')}")
        st.markdown(f"**Submitted:** {time_ago(ticket.get('created_at', ''))}")

    if equipment:
        st.markdown(f"**Equipment:** {equipment.get('name', 'N/A')} (SN: {equipment.get('serial_number', 'N/A')})")

    st.markdown("---")
    st.markdown("**Description:**")
    st.markdown(ticket.get("description", "No description provided."))

    if ticket.get("estimated_cost") or ticket.get("actual_cost"):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Estimated Cost", format_currency(ticket.get("estimated_cost")))
        with col2:
            st.metric("Actual Cost", format_currency(ticket.get("actual_cost")))

    # Photos
    if photos:
        st.markdown("---")
        st.markdown("**Photos:**")
        cols = st.columns(min(len(photos), 3))
        for i, photo in enumerate(photos):
            with cols[i % 3]:
                st.image(photo["photo_url"], width="stretch")

    # Approval chain
    if approvals:
        st.markdown("---")
        st.markdown("**Approval Chain:**")
        for approval in approvals:
            approver = approval.get("users", {}) or {}
            level = approval.get("role_required", "").upper()
            a_status = approval.get("status", "pending")
            icon = {"approved": "✅", "rejected": "❌", "pending": "⏳"}.get(a_status, "⏳")
            approver_name = approver.get("full_name", "Awaiting approver")
            st.markdown(f"{icon} **{level}**: {approver_name} — {a_status.title()}")
            if approval.get("notes"):
                st.caption(f"  Note: {approval['notes']}")

    # Comments
    if comments:
        st.markdown("---")
        st.markdown("**Comments:**")
        for comment in comments:
            commenter = comment.get("users", {}) or {}
            st.markdown(
                f"**{commenter.get('full_name', 'Unknown')}** "
                f"({time_ago(comment.get('created_at', ''))})"
            )
            st.markdown(f"> {comment.get('comment', '')}")
