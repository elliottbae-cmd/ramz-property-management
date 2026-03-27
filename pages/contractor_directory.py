"""
Contractor Directory -- Browse, manage, rate, and review contractors.
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user, is_psp_user
from database.contractors import (
    get_contractors, get_contractor, create_contractor,
    update_contractor, get_contractor_reviews, add_review,
)
from theme.branding import render_header
from utils.constants import TRADE_TYPES, US_STATES
from utils.permissions import can_manage_contractors
from utils.helpers import format_date


def render():
    render_header("Contractor Directory", "Trusted contractors by trade")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    can_manage = can_manage_contractors()

    # Check if viewing/editing a specific contractor
    if "selected_contractor_id" in st.session_state:
        _render_contractor_detail(st.session_state["selected_contractor_id"], user, can_manage)
        return

    # ---- Filters ----
    col1, col2, col3 = st.columns(3)
    with col1:
        trade_filter = st.selectbox("Filter by Trade", ["All"] + TRADE_TYPES)
    with col2:
        state_filter = st.selectbox("Filter by State", ["All"] + US_STATES)
    with col3:
        city_filter = st.text_input("Filter by City", placeholder="e.g., Omaha")

    # Build filters dict
    filters = {"active_only": True}
    if trade_filter != "All":
        filters["trade"] = trade_filter
    if state_filter != "All":
        filters["state"] = state_filter
    if city_filter:
        filters["city"] = city_filter

    if can_manage:
        show_inactive = st.checkbox("Show Inactive", value=False)
        if show_inactive:
            filters["active_only"] = False

    contractors = get_contractors(filters)

    # ---- Add New Contractor (PSP users only) ----
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
            preferred = "* " if c.get("is_preferred") else ""
            inactive = " (INACTIVE)" if not c.get("is_active") else ""
            rating = c.get("avg_rating", 0) or 0
            stars = "+" * int(rating) + "-" * (5 - int(rating))
            trades = c.get("trades", []) or []
            trades_str = ", ".join(trades) if isinstance(trades, list) else str(trades)

            st.markdown(f"""
            <div class="ticket-card" style="border-left-color: {'#FFD700' if c.get('is_preferred') else '#E0E0E0'};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong>{preferred}{c.get('company_name', '')}{inactive}</strong>
                    <span style="color: #FF9800;">({rating:.1f}/5)</span>
                </div>
                <div style="font-size: 0.9rem; margin-top: 0.5rem;">
                    <strong>Contact:</strong> {c.get('contact_name', 'N/A')} |
                    {c.get('phone', 'N/A')} | {c.get('email', 'N/A')}
                </div>
                <div style="font-size: 0.85rem; color: #757575; margin-top: 0.25rem;">
                    <strong>Trades:</strong> {trades_str}
                </div>
                <div style="font-size: 0.85rem; color: #757575;">
                    <strong>Location:</strong> {c.get('city', 'N/A')}, {c.get('state', 'N/A')}
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

        col_city, col_state = st.columns(2)
        with col_city:
            city = st.text_input("City")
        with col_state:
            state = st.selectbox("State", [""] + US_STATES, key="new_contractor_state")

        service_regions = st.text_input(
            "Service Regions (comma-separated)",
            placeholder="Nebraska, Missouri, Kansas",
        )
        is_preferred = st.checkbox("Preferred Vendor")
        notes = st.text_area("Notes")

        if st.form_submit_button("Add Contractor", use_container_width=True):
            if not company or not trades:
                st.error("Company name and at least one trade are required.")
            else:
                region_list = [r.strip() for r in service_regions.split(",") if r.strip()] if service_regions else []
                result = create_contractor({
                    "company_name": company,
                    "contact_name": contact or None,
                    "phone": phone or None,
                    "email": email or None,
                    "trades": trades,
                    "city": city or None,
                    "state": state or None,
                    "service_regions": region_list,
                    "is_preferred": is_preferred,
                    "notes": notes or None,
                })
                if result:
                    st.success(f"Contractor '{company}' added!")
                    st.rerun()
                else:
                    st.error("Failed to add contractor.")


def _render_contractor_detail(contractor_id: str, user: dict, can_manage: bool):
    """Render contractor detail view with reviews and management options."""
    if st.button("< Back to Directory"):
        del st.session_state["selected_contractor_id"]
        st.rerun()

    contractor = get_contractor(contractor_id)
    if not contractor:
        st.error("Contractor not found.")
        return

    # Header
    preferred_label = "* " if contractor.get("is_preferred") else ""
    st.markdown(f"### {preferred_label}{contractor.get('company_name', '')}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Contact:** {contractor.get('contact_name', 'N/A')}")
        st.markdown(f"**Phone:** {contractor.get('phone', 'N/A')}")
        st.markdown(f"**Email:** {contractor.get('email', 'N/A')}")
    with col2:
        trades = contractor.get("trades", []) or []
        trades_str = ", ".join(trades) if isinstance(trades, list) else str(trades)
        st.markdown(f"**Trades:** {trades_str}")
        st.markdown(f"**Location:** {contractor.get('city', 'N/A')}, {contractor.get('state', 'N/A')}")
        regions = contractor.get("service_regions", []) or []
        regions_str = ", ".join(regions) if isinstance(regions, list) else str(regions)
        st.markdown(f"**Service Regions:** {regions_str}")
        rating = contractor.get("avg_rating", 0) or 0
        st.markdown(f"**Rating:** {rating:.1f}/5")

    if contractor.get("notes"):
        st.markdown(f"**Notes:** {contractor['notes']}")

    # Management actions (PSP users only)
    if can_manage:
        st.markdown("---")
        st.markdown("### Management")

        tab_edit, tab_status = st.tabs(["Edit", "Status"])

        with tab_edit:
            with st.form("edit_contractor"):
                company = st.text_input("Company Name", value=contractor.get("company_name", ""))
                contact = st.text_input("Contact Name", value=contractor.get("contact_name", "") or "")
                phone = st.text_input("Phone", value=contractor.get("phone", "") or "")
                email_val = st.text_input("Email", value=contractor.get("email", "") or "")
                trades_val = st.multiselect(
                    "Trades", TRADE_TYPES,
                    default=contractor.get("trades", []) or [],
                )
                col_c, col_s = st.columns(2)
                with col_c:
                    city_val = st.text_input("City", value=contractor.get("city", "") or "")
                with col_s:
                    current_state = contractor.get("state", "") or ""
                    state_idx = US_STATES.index(current_state) + 1 if current_state in US_STATES else 0
                    state_val = st.selectbox("State", [""] + US_STATES, index=state_idx, key="edit_state")

                regions_val = st.text_input(
                    "Service Regions",
                    value=", ".join(contractor.get("service_regions", []) or []),
                )
                is_preferred = st.checkbox(
                    "Preferred Vendor",
                    value=contractor.get("is_preferred", False),
                )
                notes = st.text_area("Notes", value=contractor.get("notes", "") or "")

                if st.form_submit_button("Save Changes", use_container_width=True):
                    region_list = [r.strip() for r in regions_val.split(",") if r.strip()] if regions_val else []
                    result = update_contractor(contractor_id, {
                        "company_name": company,
                        "contact_name": contact or None,
                        "phone": phone or None,
                        "email": email_val or None,
                        "trades": trades_val,
                        "city": city_val or None,
                        "state": state_val or None,
                        "service_regions": region_list,
                        "is_preferred": is_preferred,
                        "notes": notes or None,
                    })
                    if result:
                        st.success("Contractor updated!")
                        st.rerun()
                    else:
                        st.error("Failed to update contractor.")

        with tab_status:
            if contractor.get("is_active"):
                st.warning("Deactivating a contractor hides them from suggestions but preserves their history.")
                reason = st.text_input(
                    "Reason for deactivation",
                    placeholder="e.g., poor quality, went out of business",
                )
                if st.button("Deactivate Contractor", use_container_width=True):
                    update_contractor(contractor_id, {
                        "is_active": False,
                        "deactivated_reason": reason or None,
                    })
                    st.success("Contractor deactivated.")
                    st.rerun()
            else:
                st.info(
                    f"This contractor was deactivated. "
                    f"Reason: {contractor.get('deactivated_reason', 'N/A')}"
                )
                if st.button("Reactivate Contractor", type="primary", use_container_width=True):
                    update_contractor(contractor_id, {
                        "is_active": True,
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
            r_rating = review.get("rating", 0)
            st.markdown(
                f"**{reviewer.get('full_name', 'Anonymous')}** -- "
                f"{r_rating}/5 "
                f"({format_date(review.get('created_at', ''))})"
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
            comment = st.text_area("Comment", placeholder="How was your experience?")

            if st.form_submit_button("Submit Review", use_container_width=True):
                result = add_review({
                    "contractor_id": contractor_id,
                    "user_id": user["id"],
                    "rating": rating,
                    "comment": comment or None,
                })
                if result:
                    st.success("Review submitted!")
                    st.rerun()
                else:
                    st.error("Failed to submit review.")
