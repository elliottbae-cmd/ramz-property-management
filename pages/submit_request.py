"""
Submit Repair Request -- Mobile-first repair request intake form.
All form options are loaded from the database (admin-configurable).
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user, get_client, upload_photo
from database.tenant import get_effective_client_id
from database.stores import get_stores, get_stores_for_user
from database.equipment import get_equipment, create_equipment
from database.warranty_lookup import check_warranty_status, save_warranty_from_ai
from database.tickets import create_ticket
from database.approvals import initiate_approval_chain, get_threshold
from database.audit import log_action
from database.cost_estimation import get_cost_estimate_details
from components.photo_upload import render_photo_upload, save_photos
from theme.branding import render_header


@st.cache_data(ttl=300)
def _get_form_categories(client_id: str | None) -> list[dict]:
    """Load form categories for the client (or global defaults)."""
    try:
        sb = get_client()
        # Client-specific first
        if client_id:
            result_client = (
                sb.table("form_categories")
                .select("*")
                .eq("is_active", True)
                .eq("client_id", client_id)
                .order("display_order")
                .execute()
            )
            if result_client.data:
                return result_client.data
        # Fall back to global categories
        result_global = (
            sb.table("form_categories")
            .select("*")
            .eq("is_active", True)
            .is_("client_id", "null")
            .order("display_order")
            .execute()
        )
        return result_global.data or []
    except Exception:
        return []


@st.cache_data(ttl=300)
def _get_form_urgency_levels(client_id: str | None) -> list[dict]:
    """Load urgency levels for the client (or global defaults)."""
    try:
        sb = get_client()
        if client_id:
            result_client = (
                sb.table("form_urgency_levels")
                .select("*")
                .eq("is_active", True)
                .eq("client_id", client_id)
                .order("display_order")
                .execute()
            )
            if result_client.data:
                return result_client.data
        result_global = (
            sb.table("form_urgency_levels")
            .select("*")
            .eq("is_active", True)
            .is_("client_id", "null")
            .order("display_order")
            .execute()
        )
        return result_global.data or []
    except Exception:
        return []


def render():
    render_header("Submit Repair Request", "Report an issue at your store")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    client_id = get_effective_client_id()
    if not client_id:
        st.warning("No client context selected. Please select a client first.")
        return

    # Load form configuration from database
    categories = _get_form_categories(client_id)
    urgency_levels = _get_form_urgency_levels(client_id)

    if not categories:
        st.warning("No categories configured. Contact your administrator.")
        return

    # ---- Store Selection ----
    stores = get_stores_for_user(user, client_id)
    if not stores:
        st.warning("No stores found for your account. Contact your administrator.")
        return

    store_options = {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}
    store_ids = list(store_options.keys())

    # Auto-select for GMs with only one store
    if len(stores) == 1:
        selected_store_id = store_ids[0]
        st.info(f"📍 **Store: {store_options[selected_store_id]}**")
    else:
        # Try to pre-select user's assigned store
        user_store_id = user.get("store_id")
        default_idx = 0
        if user_store_id and user_store_id in store_ids:
            default_idx = store_ids.index(user_store_id)

        selected_store_id = st.selectbox(
            "Store Location *",
            options=store_ids,
            format_func=lambda x: store_options[x],
            index=default_idx,
            help="Select the store where the repair is needed",
        )

    # ---- Category ----
    category_options = {c["id"]: f"{c.get('icon', '')} {c['name']}" for c in categories}
    category_ids = list(category_options.keys())

    selected_category_id = st.selectbox(
        "Category *",
        options=category_ids,
        format_func=lambda x: category_options[x],
        help="What type of repair is needed?",
    )

    selected_category = next((c for c in categories if c["id"] == selected_category_id), {})
    category_name = selected_category.get("name", "")

    # ---- Equipment Type (from brand_equipment_options) ----
    # Look up the store's brand
    selected_store = next((s for s in stores if s["id"] == selected_store_id), {})
    store_brand = selected_store.get("brand", "")

    # Load equipment options for this brand + category
    brand_equip_options = []
    if store_brand and category_name:
        try:
            sb = get_client()
            result = (
                sb.table("brand_equipment_options")
                .select("*")
                .eq("client_id", client_id)
                .eq("brand", store_brand)
                .eq("category", category_name)
                .eq("is_active", True)
                .order("display_order")
                .execute()
            )
            brand_equip_options = result.data or []
        except Exception:
            brand_equip_options = []

    equipment_choices = {"": "-- Select Equipment --"}
    for opt in brand_equip_options:
        equipment_choices[opt["equipment_name"]] = opt["equipment_name"]
    equipment_choices["other"] = "Other (not listed)"

    selected_equipment_type = st.selectbox(
        "Equipment Type",
        options=list(equipment_choices.keys()),
        format_func=lambda x: equipment_choices[x],
        help="Select the type of equipment that needs repair",
    )

    # Equipment name (from selection or manual entry)
    new_equipment_name = None
    new_manufacturer = None
    new_brand = None
    new_serial = None

    if selected_equipment_type == "other":
        new_equipment_name = st.text_input("Equipment Name *", placeholder="e.g., Walk-in Cooler")
    elif selected_equipment_type:
        new_equipment_name = selected_equipment_type

    # Show manufacturer/brand/serial fields when equipment is selected
    if selected_equipment_type and selected_equipment_type != "":
        st.caption("Enter equipment details (optional — select N/A if not applicable)")
        col_m, col_b, col_s = st.columns(3)
        with col_m:
            na_manufacturer = st.checkbox("N/A", key="na_mfg", help="Check if not applicable")
            new_manufacturer = "" if na_manufacturer else st.text_input(
                "Make/Manufacturer", placeholder="e.g., Henny Penny", key="mfg_input"
            )
        with col_b:
            na_brand = st.checkbox("N/A", key="na_brand", help="Check if not applicable")
            new_brand = "" if na_brand else st.text_input(
                "Model", placeholder="e.g., OFE-322", key="brand_input"
            )
        with col_s:
            na_serial = st.checkbox("N/A", key="na_serial", help="Check if not applicable")
            new_serial = "" if na_serial else st.text_input(
                "Serial Number", placeholder="e.g., ABC-12345", key="serial_input"
            )

    # ---- Warranty Check ----
    if selected_equipment_type and selected_equipment_type != "":
        _render_warranty_check(
            equipment_name=new_equipment_name,
            manufacturer=new_manufacturer,
            model=new_brand,  # model field is labeled "Model" but stored in new_brand var
            serial_number=new_serial,
            category=category_name,
        )

    # ---- Cost Estimation Hint ----
    cost_details = None
    if category_name and client_id:
        equip_for_estimate = new_equipment_name if new_equipment_name else None
        cost_details = get_cost_estimate_details(client_id, category_name, equip_for_estimate)
        if cost_details:
            est = cost_details["estimate"]
            if est["count"] >= 3:
                st.info(f"{cost_details['display']}\n\n*Based on historical repair data*")
            elif est["count"] >= 1:
                st.info(
                    f"{cost_details['display']}\n\n"
                    "*Limited data -- estimate may not be representative*"
                )

    # ---- Description ----
    description = st.text_area(
        "What's going on? *",
        placeholder="Describe the issue in detail. What's broken? When did it start? Is it affecting operations?",
        height=120,
    )

    # ---- Urgency ----
    if urgency_levels:
        urgency_names = [u["name"] for u in urgency_levels]
        selected_urgency = st.radio(
            "Urgency Level *",
            options=urgency_names,
            horizontal=True,
            help="How urgent is this repair?",
        )
    else:
        selected_urgency = "Not Urgent"

    # Show SLA info
    if urgency_levels:
        urgency_obj = next((u for u in urgency_levels if u["name"] == selected_urgency), None)
        if urgency_obj and urgency_obj.get("sla_hours"):
            hours = urgency_obj["sla_hours"]
            if hours >= 24:
                st.caption(f"Target response time: {hours // 24} day(s)")
            else:
                st.caption(f"Target response time: {hours} hour(s)")

    # ---- Estimated Cost (optional) ----
    if cost_details:
        est = cost_details["estimate"]
        st.caption(
            f"Suggested range: ${est['min']:,.0f} - ${est['max']:,.0f} "
            f"based on {est['count']} similar repair{'s' if est['count'] != 1 else ''}"
        )
    estimated_cost = st.number_input(
        "Estimated Cost ($)", min_value=0.0, step=50.0, value=0.0,
        help="Optional - rough cost estimate for this repair",
    )

    # ---- Photos ----
    st.markdown("---")
    uploaded_files = render_photo_upload()

    # ---- Submit ----
    st.markdown("---")

    if st.button("Submit Repair Request", type="primary", use_container_width=True):
        # Validation
        errors = []
        if not selected_store_id:
            errors.append("Please select a store.")
        if not description or not description.strip():
            errors.append("Please describe the issue.")
        if selected_equipment_type == "other" and not new_equipment_name:
            errors.append("Please enter the equipment name.")

        if errors:
            for e in errors:
                st.error(e)
            return

        try:
            # Create equipment record for this ticket
            equipment_id = None
            if new_equipment_name:
                eq_data = {
                    "store_id": selected_store_id,
                    "name": new_equipment_name,
                    "category": category_name,
                }
                if new_serial:
                    eq_data["serial_number"] = new_serial
                if new_manufacturer:
                    eq_data["manufacturer"] = new_manufacturer
                if new_brand:
                    eq_data["brand"] = new_brand

                new_eq = create_equipment(eq_data)
                if new_eq:
                    equipment_id = new_eq["id"]

            # Build ticket data
            ticket_data = {
                "client_id": client_id,
                "store_id": selected_store_id,
                "equipment_id": equipment_id,
                "category": category_name,
                "description": description.strip(),
                "urgency": selected_urgency,
                "submitted_by": user["id"],
                "status": "warranty_check",
            }
            if estimated_cost > 0:
                ticket_data["estimated_cost"] = estimated_cost

            result = create_ticket(ticket_data)

            if result:
                ticket_id = result["id"]

                # Upload photos
                if uploaded_files:
                    save_photos(uploaded_files, ticket_id)

                # Initiate approval chain if cost exceeds threshold
                if estimated_cost > 0:
                    initiate_approval_chain(ticket_id, client_id, estimated_cost)

                # Audit log
                log_action(
                    client_id=client_id,
                    user_id=user["id"],
                    action="create",
                    entity_type="ticket",
                    entity_id=ticket_id,
                    details={"category": category_name, "urgency": selected_urgency},
                )

                st.success(
                    f"Repair request submitted successfully! "
                    f"Ticket #{result.get('ticket_number', 'N/A')}"
                )
                st.balloons()
                st.info("You can submit another request or check 'My Tickets' to track this one.")
            else:
                st.error("Failed to create ticket. Please try again.")

        except Exception as e:
            st.error(f"Error submitting request: {str(e)}")


# ------------------------------------------------------------------
# Warranty check widget
# ------------------------------------------------------------------

def _render_warranty_check(
    equipment_name: str | None,
    manufacturer: str | None,
    model: str | None,
    serial_number: str | None,
    category: str | None,
):
    """Render a 'Check Warranty' button and display results."""
    if st.button("Check Warranty", key="warranty_check_btn"):
        equipment_data = {
            "equipment_name": equipment_name or "",
            "manufacturer": manufacturer or "",
            "model": model or "",
            "serial_number": serial_number or "",
            "category": category or "",
        }

        with st.spinner("Checking warranty status..."):
            result = check_warranty_status(equipment_data)

        st.session_state["warranty_check_result"] = result

    # Display result if available
    result = st.session_state.get("warranty_check_result")
    if not result:
        return

    recommendation = result.get("recommendation", "")

    if result.get("has_db_warranty"):
        # GREEN -- active warranty on file
        st.markdown(
            f'<div style="background-color: #1B5E20; color: white; padding: 12px 16px; '
            f'border-radius: 8px; margin: 8px 0;">'
            f'<strong>Under Warranty</strong><br>{recommendation}</div>',
            unsafe_allow_html=True,
        )
        st.info(
            "This may be covered under warranty. Consider contacting the "
            "manufacturer before requesting repairs."
        )
    elif result.get("ai_lookup_performed") and result.get("ai_result"):
        ai = result["ai_result"]
        confidence = ai.get("confidence", "low")

        # Confidence badge
        conf_colors = {"high": "#1B5E20", "medium": "#F57F17", "low": "#B71C1C"}
        conf_color = conf_colors.get(confidence, "#616161")

        if ai.get("likely_under_warranty") and confidence in ("high", "medium"):
            # GREEN/YELLOW -- AI thinks under warranty
            bg = "#1B5E20" if confidence == "high" else "#F57F17"
            label = "Likely Under Warranty" if confidence == "high" else "Warranty Status Uncertain"
            st.markdown(
                f'<div style="background-color: {bg}; color: white; padding: 12px 16px; '
                f'border-radius: 8px; margin: 8px 0;">'
                f'<strong>{label}</strong> '
                f'<span style="background-color: {conf_color}; color: white; '
                f'padding: 2px 8px; border-radius: 12px; font-size: 0.8em; '
                f'margin-left: 8px;">{confidence.upper()} confidence</span>'
                f'<br>{recommendation}</div>',
                unsafe_allow_html=True,
            )
            if confidence == "high":
                st.info(
                    "This may be covered under warranty. Consider contacting the "
                    "manufacturer before requesting repairs."
                )
            else:
                st.warning("PSP should verify warranty status with the manufacturer.")
        else:
            # RED -- warranty likely expired or low confidence
            st.markdown(
                f'<div style="background-color: #B71C1C; color: white; padding: 12px 16px; '
                f'border-radius: 8px; margin: 8px 0;">'
                f'<strong>Warranty Likely Expired</strong> '
                f'<span style="background-color: {conf_color}; color: white; '
                f'padding: 2px 8px; border-radius: 12px; font-size: 0.8em; '
                f'margin-left: 8px;">{confidence.upper()} confidence</span>'
                f'<br>{recommendation}</div>',
                unsafe_allow_html=True,
            )

        # Show AI details in expander
        with st.expander("View AI Research Details"):
            warranty_period = ai.get("warranty_period") or ai.get("typical_warranty_period", "N/A")
            st.write(f"**Warranty Period:** {warranty_period}")
            st.write(f"**Coverage Type:** {ai.get('coverage_type', 'N/A')}")
            st.write(f"**Estimated Expiry:** {ai.get('estimated_expiry', 'N/A')}")
            st.write(f"**Manufacturer Contact:** {ai.get('manufacturer_contact', 'N/A')}")
            st.write(f"**Claim Process:** {ai.get('claim_process', 'N/A')}")
            if ai.get("notes"):
                st.write(f"**Notes:** {ai['notes']}")

            # Web search indicator
            if ai.get("web_search_used"):
                st.caption("Results based on live web search + AI analysis")
            else:
                st.caption("Results based on AI training data only")

            # Source URLs
            source_urls = ai.get("source_urls", [])
            if source_urls:
                st.markdown("**Sources:**")
                for url in source_urls:
                    display_url = url if len(url) <= 80 else url[:77] + "..."
                    st.markdown(f"- [{display_url}]({url})")
    else:
        # No warranty info at all
        st.markdown(
            f'<div style="background-color: #616161; color: white; padding: 12px 16px; '
            f'border-radius: 8px; margin: 8px 0;">'
            f'<strong>No Warranty Info</strong><br>{recommendation}</div>',
            unsafe_allow_html=True,
        )
