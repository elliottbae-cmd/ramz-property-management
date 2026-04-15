"""
Submit Repair Request -- Mobile-first repair request intake form.
All form options are loaded from the database (admin-configurable).
Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user, get_client
from database.tenant import get_effective_client_id
from database.stores import get_stores_for_user
from database.equipment import create_equipment
from database.tickets import create_ticket, get_ticket
from database.audit import log_action
from components.photo_upload import render_photo_upload, save_photos
from components.notifications import notify_new_ticket
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
def _get_brand_equipment_options(client_id: str, brand: str, category: str) -> list[dict]:
    """Load brand equipment options for a specific brand + category."""
    try:
        sb = get_client()
        result = (
            sb.table("brand_equipment_options")
            .select("*")
            .eq("client_id", client_id)
            .eq("brand", brand)
            .eq("category", category)
            .eq("is_active", True)
            .order("display_order")
            .execute()
        )
        return result.data or []
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

    # Load equipment options for this brand + category (cached)
    brand_equip_options = []
    if store_brand and category_name:
        brand_equip_options = _get_brand_equipment_options(client_id, store_brand, category_name)

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

    # ---- Photos ----
    st.markdown("---")
    uploaded_files = render_photo_upload()

    # ---- Submit ----
    st.markdown("---")

    if st.button("Submit Repair Request", type="primary", width="stretch"):
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
            result = create_ticket(ticket_data)

            if result:
                ticket_id = result["id"]

                # Upload photos
                if uploaded_files:
                    save_photos(uploaded_files, ticket_id)

                # Audit log
                log_action(
                    client_id=client_id,
                    user_id=user["id"],
                    action="create",
                    entity_type="ticket",
                    entity_id=ticket_id,
                    details={"category": category_name, "urgency": selected_urgency},
                )

                try:
                    # Build enriched ticket dict using data already in scope —
                    # avoids a second DB round-trip and works regardless of RLS.
                    notify_ticket = dict(result)
                    notify_ticket["stores"] = selected_store  # already fetched above
                    if new_equipment_name:
                        notify_ticket["equipment"] = {"name": new_equipment_name}
                    notify_new_ticket(notify_ticket, client_id)
                except Exception as notify_err:
                    st.warning(f"⚠️ Notification error: {notify_err}")

                st.success(
                    f"Repair request submitted! Ticket #{result.get('ticket_number', 'N/A')} — redirecting to My Tickets..."
                )
                st.balloons()

                import time
                time.sleep(2)
                st.session_state["nav_redirect"] = "My Tickets"
                st.rerun()
            else:
                st.error("Failed to create ticket. Please try again.")

        except Exception as e:
            st.error(f"Error submitting request: {str(e)}")


