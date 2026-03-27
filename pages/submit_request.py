"""
Submit Repair Request -- Mobile-first repair request intake form.
All form options are loaded from the database (admin-configurable).
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user, get_client, upload_photo
from database.tenant import get_effective_client_id
from database.stores import get_stores
from database.equipment import get_equipment, create_equipment
from database.tickets import create_ticket
from database.approvals import initiate_approval_chain, get_threshold
from database.audit import log_action
from components.photo_upload import render_photo_upload, save_photos
from theme.branding import render_header


def _get_form_categories(client_id: str | None) -> list[dict]:
    """Load form categories for the client (or global defaults)."""
    try:
        sb = get_client()
        query = (
            sb.table("form_categories")
            .select("*")
            .eq("is_active", True)
            .order("display_order")
        )
        # Client-specific or global (client_id IS NULL)
        if client_id:
            result_client = query.eq("client_id", client_id).execute()
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


def _get_form_urgency_levels(client_id: str | None) -> list[dict]:
    """Load urgency levels for the client (or global defaults)."""
    try:
        sb = get_client()
        query = (
            sb.table("form_urgency_levels")
            .select("*")
            .eq("is_active", True)
            .order("display_order")
        )
        if client_id:
            result_client = query.eq("client_id", client_id).execute()
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
    stores = get_stores(client_id)
    if not stores:
        st.warning("No stores found for this client.")
        return

    store_options = {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}
    store_ids = list(store_options.keys())

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

    # ---- Equipment ----
    equipment_list = get_equipment(selected_store_id) if selected_store_id else []
    equipment_options = {"": "-- Select Equipment --", "new": "+ Add New Equipment"}
    for eq in equipment_list:
        label = eq["name"]
        if eq.get("serial_number"):
            label += f" (SN: {eq['serial_number']})"
        equipment_options[eq["id"]] = label

    selected_equipment_id = st.selectbox(
        "Equipment",
        options=list(equipment_options.keys()),
        format_func=lambda x: equipment_options[x],
    )

    # New equipment form
    new_equipment_name = None
    new_manufacturer = None
    new_brand = None
    new_serial = None

    if selected_equipment_id == "new":
        new_equipment_name = st.text_input("Equipment Name *", placeholder="e.g., Walk-in Cooler")

        col_m, col_b, col_s = st.columns(3)
        with col_m:
            na_manufacturer = st.checkbox("N/A", key="na_mfg", help="Check if not applicable")
            new_manufacturer = "" if na_manufacturer else st.text_input(
                "Manufacturer", placeholder="e.g., Carrier", key="mfg_input"
            )
        with col_b:
            na_brand = st.checkbox("N/A", key="na_brand", help="Check if not applicable")
            new_brand = "" if na_brand else st.text_input(
                "Brand", placeholder="e.g., Trane", key="brand_input"
            )
        with col_s:
            na_serial = st.checkbox("N/A", key="na_serial", help="Check if not applicable")
            new_serial = "" if na_serial else st.text_input(
                "Serial Number", placeholder="e.g., ABC-12345", key="serial_input"
            )
    elif selected_equipment_id and selected_equipment_id != "":
        # Show existing equipment info
        selected_eq = next((eq for eq in equipment_list if eq["id"] == selected_equipment_id), None)
        if selected_eq:
            eq_cols = st.columns(3)
            with eq_cols[0]:
                st.caption(f"Manufacturer: {selected_eq.get('make', 'N/A')}")
            with eq_cols[1]:
                st.caption(f"Brand: {selected_eq.get('model', 'N/A')}")
            with eq_cols[2]:
                st.caption(f"Serial: {selected_eq.get('serial_number', 'N/A')}")

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
        if selected_equipment_id == "new" and not new_equipment_name:
            errors.append("Please enter the equipment name.")

        if errors:
            for e in errors:
                st.error(e)
            return

        try:
            # Create new equipment if needed
            equipment_id = None
            if selected_equipment_id == "new":
                eq_data = {
                    "store_id": selected_store_id,
                    "name": new_equipment_name,
                    "category": category_name,
                }
                if new_serial:
                    eq_data["serial_number"] = new_serial
                if new_manufacturer:
                    eq_data["make"] = new_manufacturer
                if new_brand:
                    eq_data["model"] = new_brand

                new_eq = create_equipment(eq_data)
                if new_eq:
                    equipment_id = new_eq["id"]
                else:
                    st.error("Failed to create equipment record.")
                    return
            elif selected_equipment_id:
                equipment_id = selected_equipment_id

            # Build ticket data
            ticket_data = {
                "client_id": client_id,
                "store_id": selected_store_id,
                "equipment_id": equipment_id,
                "category": category_name,
                "description": description.strip(),
                "urgency": selected_urgency,
                "submitted_by": user["id"],
                "status": "submitted",
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
