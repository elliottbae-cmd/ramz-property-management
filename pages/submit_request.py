"""
Submit Repair Request — Mobile-first repair request intake form.
This is the primary page for field staff (GMs, staff).
All form options are loaded from the database (admin-configurable).
"""

import streamlit as st
from database.supabase_client import (
    get_current_user, get_stores, get_equipment, create_equipment,
    get_form_categories, get_form_urgency_levels, get_form_fields,
    create_ticket, get_user_stores
)
from components.photo_upload import render_photo_upload, save_photos
from components.notifications import notify_new_ticket
from components.approval_chain import initiate_approval
from theme.branding import render_header


def render():
    render_header("Submit Repair Request", "Report an issue at your store")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    # Load form configuration from database
    categories = get_form_categories()
    urgency_levels = get_form_urgency_levels()

    if not categories:
        st.warning("No categories configured. Contact your administrator.")
        return

    # ---- Store Selection ----
    # Auto-select user's store if they have one assigned
    stores = get_stores()
    store_options = {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}

    user_store_id = user.get("store_id")
    default_idx = 0
    store_ids = list(store_options.keys())
    if user_store_id and user_store_id in store_ids:
        default_idx = store_ids.index(user_store_id)

    selected_store_id = st.selectbox(
        "Store Location *",
        options=store_ids,
        format_func=lambda x: store_options[x],
        index=default_idx,
        help="Select the store where the repair is needed"
    )

    # ---- Category ----
    category_options = {c["id"]: f"{c.get('icon', '')} {c['name']}" for c in categories}
    category_ids = list(category_options.keys())

    selected_category_id = st.selectbox(
        "Category *",
        options=category_ids,
        format_func=lambda x: category_options[x],
        help="What type of repair is needed?"
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
        "Equipment" + (" *" if selected_category.get("requires_serial") else ""),
        options=list(equipment_options.keys()),
        format_func=lambda x: equipment_options[x],
    )

    # New equipment form
    new_equipment_name = None
    new_serial = None
    if selected_equipment_id == "new":
        new_equipment_name = st.text_input("Equipment Name *", placeholder="e.g., Walk-in Cooler")
        if selected_category.get("requires_serial"):
            new_serial = st.text_input("Serial Number", placeholder="e.g., ABC-12345")
        else:
            new_serial = st.text_input("Serial Number (optional)", placeholder="e.g., ABC-12345")

    # ---- Description ----
    description = st.text_area(
        "What's going on? *",
        placeholder="Describe the issue in detail. What's broken? When did it start? Is it affecting operations?",
        height=120,
    )

    # ---- Custom Fields (admin-configurable) ----
    custom_field_values = {}
    custom_fields = get_form_fields(selected_category_id) if selected_category_id else []
    for field in custom_fields:
        field_key = f"custom_{field['field_name']}"
        if field["field_type"] == "text":
            custom_field_values[field["field_name"]] = st.text_input(
                field["label"] + (" *" if field["is_required"] else ""),
                key=field_key
            )
        elif field["field_type"] == "textarea":
            custom_field_values[field["field_name"]] = st.text_area(
                field["label"] + (" *" if field["is_required"] else ""),
                key=field_key
            )
        elif field["field_type"] == "dropdown":
            options = field.get("options", []) or []
            custom_field_values[field["field_name"]] = st.selectbox(
                field["label"] + (" *" if field["is_required"] else ""),
                options=[""] + options,
                key=field_key
            )
        elif field["field_type"] == "number":
            custom_field_values[field["field_name"]] = st.number_input(
                field["label"] + (" *" if field["is_required"] else ""),
                min_value=0,
                key=field_key
            )
        elif field["field_type"] == "date":
            custom_field_values[field["field_name"]] = str(st.date_input(
                field["label"] + (" *" if field["is_required"] else ""),
                key=field_key
            ))
        elif field["field_type"] == "checkbox":
            custom_field_values[field["field_name"]] = st.checkbox(
                field["label"],
                key=field_key
            )

    # ---- Urgency ----
    if urgency_levels:
        urgency_names = [u["name"] for u in urgency_levels]
        selected_urgency = st.radio(
            "Urgency Level *",
            options=urgency_names,
            horizontal=True,
            help="How urgent is this repair?"
        )
    else:
        selected_urgency = "Not Urgent"

    # Show SLA info
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

    if st.button("Submit Repair Request", type="primary", use_container_width=True):
        # Validation
        errors = []
        if not selected_store_id:
            errors.append("Please select a store.")
        if not description or not description.strip():
            errors.append("Please describe the issue.")
        if selected_equipment_id == "new" and not new_equipment_name:
            errors.append("Please enter the equipment name.")
        if selected_category.get("requires_serial") and selected_equipment_id == "new" and not new_serial:
            errors.append("Serial number is required for this category.")

        # Validate required custom fields
        for field in custom_fields:
            if field["is_required"] and not custom_field_values.get(field["field_name"]):
                errors.append(f"{field['label']} is required.")

        if errors:
            for e in errors:
                st.error(e)
            return

        try:
            # Create new equipment if needed
            equipment_id = None
            if selected_equipment_id == "new":
                new_eq = create_equipment(
                    selected_store_id, new_equipment_name, new_serial, category_name
                )
                if new_eq:
                    equipment_id = new_eq[0]["id"]
            elif selected_equipment_id:
                equipment_id = selected_equipment_id

            # Create the ticket
            ticket_data = {
                "store_id": selected_store_id,
                "equipment_id": equipment_id,
                "category": category_name,
                "description": description.strip(),
                "urgency": selected_urgency,
                "submitted_by": user["id"],
                "custom_fields": custom_field_values if custom_field_values else {},
            }

            result = create_ticket(ticket_data)

            if result:
                ticket = result[0]
                ticket_id = ticket["id"]

                # Upload photos
                if uploaded_files:
                    save_photos(uploaded_files, ticket_id)

                # Initiate approval chain
                initiate_approval(ticket_id)

                # Send notification
                store_name = store_options.get(selected_store_id, "")
                notify_new_ticket(ticket, store_name)

                st.success(
                    f"Repair request submitted successfully! "
                    f"Ticket #{ticket.get('ticket_number', 'N/A')}"
                )
                st.balloons()

                # Reset form
                st.info("You can submit another request or check 'My Tickets' to track this one.")
            else:
                st.error("Failed to create ticket. Please try again.")

        except Exception as e:
            st.error(f"Error submitting request: {str(e)}")
