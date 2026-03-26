"""
Contractor Directory — Browse, manage, rate, and review contractors.
"""

import streamlit as st
from database.supabase_client import (
    get_current_user, get_contractors, create_contractor, update_contractor,
    get_contractor_reviews, add_contractor_review, has_role
)
from theme.branding import render_header, PRIMARY
from utils.constants import TRADE_TYPES
from utils.helpers import format_date


def render():
    render_header("Contractor Directory", "Trusted contractors by trade")

    user = get_current_user()
    if not user:
        return

    can_manage = has_role("admin", "property_manager")

    # Check if viewing/editing a specific contractor
    if "selected_contractor_id" in st.session_state:
        _render_contractor_detail(st.session_state["selected_contractor_id"], user, can_manage)
        return

    # ---- Filters ----
    col1, col2, col3 = st.columns(3)
    with col1:
        trade_filter = st.selectbox("Filter by Trade", ["All"] + TRADE_TYPES)
    with col2:
        region_filter = st.text_input("Filter by Region", placeholder="e.g., Nebraska")
    with col3:
        show_inactive = st.checkbox("Show Inactive", value=False) if can_manage else False

    # Fetch contractors
    contractors = get_contractors(
        active_only=not show_inactive,
        trade=trade_filter if trade_filter != "All" else None,
        region=region_filter if region_filter else None,
    )

    # ---- Add New Contractor (admin/PM only) ----
    if can_manage:
        with st.expander("+ Add New Contractor"):
            _render_add_contractor_form()

    # ---- Contractor List ----
    st.markdown("---")

    if not contractors:
        st.info("No contractors found matching your filters.")
        return

    st.caption(f"{len(contractors)} contractor(s)")

    for c in contractors:
        col_info, col_action = st.columns([4, 1])
        with col_info:
            preferred = "⭐ " if c.get("is_preferred") else ""
            inactive = " (INACTIVE)" if not c.get("is_active") else ""
            rating = c.get("avg_rating", 0) or 0
            stars = "★" * int(rating) + "☆" * (5 - int(rating))

            st.markdown(f"""
            <div class="ticket-card" style="border-left-color: {'#FFD700' if c.get('is_preferred') else '#E0E0E0'};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong>{preferred}{c.get('company_name', '')}{inactive}</strong>
                    <span style="color: #FF9800;">{stars} ({rating:.1f})</span>
                </div>
                <div style="font-size: 0.9rem; margin-top: 0.5rem;">
                    <strong>Contact:</strong> {c.get('contact_name', 'N/A')} | {c.get('phone', 'N/A')} | {c.get('email', 'N/A')}
                </div>
                <div style="font-size: 0.85rem; color: #757575; margin-top: 0.25rem;">
                    <strong>Trades:</strong> {', '.join(c.get('trades', []))}
                </div>
                <div style="font-size: 0.85rem; color: #757575;">
                    <strong>Regions:</strong> {', '.join(c.get('service_regions', []))}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_action:
            if st.button("Details", key=f"contractor_{c['id']}", use_container_width=True):
                st.session_state["selected_contractor_id"] = c["id"]
                st.rerun()


def _render_add_contractor_form():
    """Render the add new contractor form."""
    with st.form("add_contractor"):
        company = st.text_input("Company Name *")
        contact = st.text_input("Contact Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        trades = st.multiselect("Trades *", TRADE_TYPES)
        regions = st.text_input("Service Regions (comma-separated)", placeholder="Nebraska, Missouri, Kansas")
        is_preferred = st.checkbox("Preferred Vendor")
        notes = st.text_area("Notes")

        if st.form_submit_button("Add Contractor", use_container_width=True):
            if not company or not trades:
                st.error("Company name and at least one trade are required.")
            else:
                region_list = [r.strip() for r in regions.split(",") if r.strip()] if regions else []
                create_contractor({
                    "company_name": company,
                    "contact_name": contact or None,
                    "phone": phone or None,
                    "email": email or None,
                    "trades": trades,
                    "service_regions": region_list,
                    "is_preferred": is_preferred,
                    "notes": notes or None,
                })
                st.success(f"Contractor '{company}' added!")
                st.rerun()


def _render_contractor_detail(contractor_id: str, user: dict, can_manage: bool):
    """Render contractor detail view with reviews and management options."""
    if st.button("< Back to Directory"):
        del st.session_state["selected_contractor_id"]
        st.rerun()

    contractors = get_contractors(active_only=False)
    contractor = next((c for c in contractors if c["id"] == contractor_id), None)
    if not contractor:
        st.error("Contractor not found.")
        return

    # Header
    st.markdown(f"### {'⭐ ' if contractor.get('is_preferred') else ''}{contractor.get('company_name', '')}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Contact:** {contractor.get('contact_name', 'N/A')}")
        st.markdown(f"**Phone:** {contractor.get('phone', 'N/A')}")
        st.markdown(f"**Email:** {contractor.get('email', 'N/A')}")
    with col2:
        st.markdown(f"**Trades:** {', '.join(contractor.get('trades', []))}")
        st.markdown(f"**Regions:** {', '.join(contractor.get('service_regions', []))}")
        rating = contractor.get("avg_rating", 0) or 0
        st.markdown(f"**Rating:** {'★' * int(rating)}{'☆' * (5 - int(rating))} ({rating:.1f}/5)")

    if contractor.get("notes"):
        st.markdown(f"**Notes:** {contractor['notes']}")

    # Management actions (admin/PM only)
    if can_manage:
        st.markdown("---")
        st.markdown("### Management")

        tab_edit, tab_status = st.tabs(["Edit", "Status"])

        with tab_edit:
            with st.form("edit_contractor"):
                company = st.text_input("Company Name", value=contractor.get("company_name", ""))
                contact = st.text_input("Contact Name", value=contractor.get("contact_name", ""))
                phone = st.text_input("Phone", value=contractor.get("phone", ""))
                email_val = st.text_input("Email", value=contractor.get("email", ""))
                trades = st.multiselect("Trades", TRADE_TYPES, default=contractor.get("trades", []))
                regions = st.text_input("Service Regions", value=", ".join(contractor.get("service_regions", [])))
                is_preferred = st.checkbox("Preferred Vendor", value=contractor.get("is_preferred", False))
                notes = st.text_area("Notes", value=contractor.get("notes", "") or "")

                if st.form_submit_button("Save Changes", use_container_width=True):
                    region_list = [r.strip() for r in regions.split(",") if r.strip()] if regions else []
                    update_contractor(contractor_id, {
                        "company_name": company,
                        "contact_name": contact or None,
                        "phone": phone or None,
                        "email": email_val or None,
                        "trades": trades,
                        "service_regions": region_list,
                        "is_preferred": is_preferred,
                        "notes": notes or None,
                    })
                    st.success("Contractor updated!")
                    st.rerun()

        with tab_status:
            if contractor.get("is_active"):
                st.warning("Deactivating a contractor hides them from suggestions but preserves their history.")
                reason = st.text_input("Reason for deactivation", placeholder="e.g., poor quality, went out of business")
                if st.button("Deactivate Contractor", use_container_width=True):
                    update_contractor(contractor_id, {
                        "is_active": False,
                        "deactivated_at": "now()",
                        "deactivated_reason": reason or None,
                    })
                    st.success("Contractor deactivated.")
                    st.rerun()
            else:
                st.info(f"This contractor was deactivated. Reason: {contractor.get('deactivated_reason', 'N/A')}")
                if st.button("Reactivate Contractor", type="primary", use_container_width=True):
                    update_contractor(contractor_id, {
                        "is_active": True,
                        "deactivated_at": None,
                        "deactivated_reason": None,
                    })
                    st.success("Contractor reactivated!")
                    st.rerun()

    # Reviews
    st.markdown("---")
    st.markdown("### Reviews")

    reviews = get_contractor_reviews(contractor_id)

    if reviews:
        for review in reviews:
            reviewer = review.get("users", {}) or {}
            st.markdown(
                f"**{reviewer.get('full_name', 'Anonymous')}** — "
                f"{'★' * review.get('rating', 0)}{'☆' * (5 - review.get('rating', 0))} "
                f"({format_date(review.get('created_at', ''))})"
            )
            if review.get("timeliness"):
                st.caption(
                    f"Timeliness: {review['timeliness']}/5 | "
                    f"Quality: {review.get('quality', 'N/A')}/5 | "
                    f"Communication: {review.get('communication', 'N/A')}/5"
                )
            if review.get("comment"):
                st.markdown(f"> {review['comment']}")
            st.markdown("")
    else:
        st.info("No reviews yet.")

    # Add review
    with st.expander("+ Leave a Review"):
        with st.form("add_review"):
            rating = st.slider("Overall Rating", 1, 5, 3)
            timeliness = st.slider("Timeliness", 1, 5, 3)
            quality = st.slider("Quality of Work", 1, 5, 3)
            communication = st.slider("Communication", 1, 5, 3)
            comment = st.text_area("Comment", placeholder="How was your experience?")

            if st.form_submit_button("Submit Review", use_container_width=True):
                add_contractor_review({
                    "contractor_id": contractor_id,
                    "reviewed_by": user["id"],
                    "rating": rating,
                    "timeliness": timeliness,
                    "quality": quality,
                    "communication": communication,
                    "comment": comment or None,
                })
                st.success("Review submitted!")
                st.rerun()
