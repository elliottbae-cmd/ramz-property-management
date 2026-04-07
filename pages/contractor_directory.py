"""
Contractor Directory -- Browse, manage, rate, and review contractors.
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user
from database.contractors import (
    get_contractors, get_contractor, create_contractor,
    update_contractor, get_contractor_reviews, add_review,
)
from theme.branding import render_header
from utils.constants import TRADE_TYPES, US_STATES
from utils.permissions import can_manage_contractors


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
                    <strong>States:</strong> {', '.join(c.get('service_states', []) or ['N/A'])}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_action:
            if st.button("Details", key=f"contractor_{c['id']}", width="stretch"):
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

        service_cities = st.text_input(
            "Service Cities (comma-separated)",
            placeholder="Omaha, Lincoln, Kansas City",
        )
        service_states = st.multiselect("Service States", US_STATES, key="new_contractor_states")
        service_zips = st.text_input(
            "Service ZIP Codes (comma-separated)",
            placeholder="68101, 68102",
        )
        is_preferred = st.checkbox("Preferred Vendor")
        notes = st.text_area("Notes")

        if st.form_submit_button("Add Contractor", width="stretch"):
            if not company or not trades:
                st.error("Company name and at least one trade are required.")
            else:
                city_list = [c.strip() for c in service_cities.split(",") if c.strip()] if service_cities else []
                zip_list = [z.strip() for z in service_zips.split(",") if z.strip()] if service_zips else []
                result = create_contractor({
                    "company_name": company,
                    "contact_name": contact or None,
                    "phone": phone or None,
                    "email": email or None,
                    "trades": trades,
                    "service_cities": city_list,
                    "service_states": service_states,
                    "service_zip_codes": zip_list,
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
        st.session_state.pop("selected_contractor_id", None)
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
        cities = contractor.get("service_cities", []) or []
        cities_str = ", ".join(cities) if isinstance(cities, list) else str(cities)
        st.markdown(f"**Service Cities:** {cities_str or 'N/A'}")
        states = contractor.get("service_states", []) or []
        states_str = ", ".join(states) if isinstance(states, list) else str(states)
        st.markdown(f"**Service States:** {states_str or 'N/A'}")
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
                cities_val = st.text_input(
                    "Service Cities (comma-separated)",
                    value=", ".join(contractor.get("service_cities", []) or []),
                    key="edit_cities",
                )
                states_val = st.multiselect(
                    "Service States", US_STATES,
                    default=contractor.get("service_states", []) or [],
                    key="edit_states",
                )
                zips_val = st.text_input(
                    "Service ZIP Codes (comma-separated)",
                    value=", ".join(contractor.get("service_zip_codes", []) or []),
                    key="edit_zips",
                )
                is_preferred = st.checkbox(
                    "Preferred Vendor",
                    value=contractor.get("is_preferred", False),
                )
                notes = st.text_area("Notes", value=contractor.get("notes", "") or "")

                if st.form_submit_button("Save Changes", width="stretch"):
                    city_list = [c.strip() for c in cities_val.split(",") if c.strip()] if cities_val else []
                    zip_list = [z.strip() for z in zips_val.split(",") if z.strip()] if zips_val else []
                    result = update_contractor(contractor_id, {
                        "company_name": company,
                        "contact_name": contact or None,
                        "phone": phone or None,
                        "email": email_val or None,
                        "trades": trades_val,
                        "service_cities": city_list,
                        "service_states": states_val,
                        "service_zip_codes": zip_list,
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
                if st.button("Deactivate Contractor", width="stretch"):
                    update_data = {"is_active": False}
                    if reason:
                        update_data["notes"] = f"[DEACTIVATED] {reason}"
                    update_contractor(contractor_id, update_data)
                    st.success("Contractor deactivated.")
                    st.rerun()
            else:
                st.info("This contractor is currently inactive.")
                if st.button("Reactivate Contractor", type="primary", width="stretch"):
                    update_contractor(contractor_id, {"is_active": True})
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
                f"{r_rating}/5"
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

            if st.form_submit_button("Submit Review", width="stretch"):
                result = add_review({
                    "contractor_id": contractor_id,
                    "reviewed_by": user["id"],
                    "rating": rating,
                    "comment": comment or None,
                })
                if result:
                    st.success("Review submitted!")
                    st.rerun()
                else:
                    st.error("Failed to submit review.")
