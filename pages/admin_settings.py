"""
Admin Settings -- Manage form categories, urgency levels, approval thresholds
for the current client. Uses new multi-tenant module imports.
"""

import streamlit as st
from database.supabase_client import get_current_user, get_client, has_role
from database.tenant import get_effective_client_id, get_current_client
from database.stores import get_stores, create_store, update_store
from database.users import get_users_for_client, update_user
from database.approvals import get_approval_config, get_threshold
from database.audit import log_action
from theme.branding import render_header
from utils.permissions import require_permission, can_manage_users
from utils.constants import CLIENT_ROLES, CLIENT_ROLE_LABELS, US_STATES
from utils.helpers import format_currency


def render():
    render_header("Admin Settings", "Client configuration")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    # Allow both PSP users and client admins
    if not (has_role("psp", "admin", "coo")):
        st.error("Admin access required.")
        return

    client_id = get_effective_client_id()
    if not client_id:
        st.warning("No client context selected.")
        return

    client = get_current_client()
    if client:
        st.caption(f"Managing: {client.get('name', 'Unknown')}")

    tab_users, tab_stores, tab_categories, tab_urgency, tab_approvals, tab_equipment = st.tabs(
        ["Users", "Stores", "Form Categories", "Urgency Levels", "Approval Settings", "Equipment Options"]
    )

    with tab_users:
        _render_user_management(client_id, user)

    with tab_stores:
        _render_store_management(client_id, user)

    with tab_categories:
        _render_category_management(client_id)

    with tab_urgency:
        _render_urgency_management(client_id)

    with tab_approvals:
        _render_approval_settings(client_id)

    with tab_equipment:
        _render_equipment_options(client_id)


# ------------------------------------------------------------------
# User Management (scoped to current client)
# ------------------------------------------------------------------

def _render_user_management(client_id: str, admin_user: dict):
    st.markdown("### Manage Users")

    users = get_users_for_client(client_id, active_only=False)

    if not users:
        st.info("No users found for this client.")
        return

    # Role filter
    role_filter = st.selectbox(
        "Filter by Role",
        ["All"] + list(CLIENT_ROLES),
        format_func=lambda x: CLIENT_ROLE_LABELS.get(x, x) if x != "All" else "All Roles",
        key="admin_role_filter",
    )

    if role_filter != "All":
        users = [u for u in users if u.get("client_role") == role_filter]

    st.caption(f"{len(users)} user(s)")

    for u in users:
        role = u.get("client_role", "")
        role_label = CLIENT_ROLE_LABELS.get(role, role)
        active_label = "" if u.get("is_active", True) else " (INACTIVE)"

        with st.expander(f"{u.get('full_name', 'Unknown')}{active_label} -- {role_label}"):
            st.markdown(f"**Email:** {u.get('email', 'N/A')}")

            col1, col2 = st.columns(2)
            with col1:
                role_idx = list(CLIENT_ROLES).index(role) if role in CLIENT_ROLES else 0
                new_role = st.selectbox(
                    "Role",
                    CLIENT_ROLES,
                    index=role_idx,
                    format_func=lambda x: CLIENT_ROLE_LABELS.get(x, x),
                    key=f"role_{u['id']}",
                )
            with col2:
                is_active = st.checkbox("Active", value=u.get("is_active", True), key=f"active_{u['id']}")

            col_save, col_toggle = st.columns(2)
            with col_save:
                if st.button("Save Changes", key=f"save_{u['id']}", use_container_width=True):
                    result = update_user(u["id"], {
                        "client_role": new_role,
                        "is_active": is_active,
                    })
                    if result:
                        log_action(client_id, admin_user["id"], "update", "user", u["id"],
                                   {"role_change": f"{role} -> {new_role}"})
                        st.success(f"Updated {u['full_name']}!")
                        st.rerun()
                    else:
                        st.error("Failed to update user.")


# ------------------------------------------------------------------
# Store Management
# ------------------------------------------------------------------

def _render_store_management(client_id: str, admin_user: dict):
    st.markdown("### Manage Stores")

    stores = get_stores(client_id, active_only=False)

    # Add new store
    with st.expander("+ Add New Store"):
        with st.form("add_store"):
            col1, col2 = st.columns(2)
            with col1:
                store_num = st.text_input("Store Number *", placeholder="112-0039")
                name = st.text_input("Store Name *", placeholder="Store Name (State)")
                phone = st.text_input("Phone Number *", placeholder="(555) 867-5309")
                address = st.text_input("Address")
            with col2:
                city = st.text_input("City")
                state = st.selectbox("State", [""] + US_STATES, key="new_store_state")
                region = st.text_input("Region", placeholder="e.g., Nebraska")

            if st.form_submit_button("Add Store", use_container_width=True):
                if not store_num or not name:
                    st.error("Store number and name are required.")
                elif not phone or not phone.strip():
                    st.error("Phone number is required.")
                else:
                    result = create_store({
                        "client_id": client_id,
                        "store_number": store_num,
                        "name": name,
                        "phone": phone.strip(),
                        "address": address or None,
                        "city": city or None,
                        "state": state or None,
                        "region": region or None,
                    })
                    if result:
                        log_action(client_id, admin_user["id"], "create", "store", result["id"],
                                   {"name": name})
                        st.success(f"Store '{name}' added!")
                        st.rerun()
                    else:
                        st.error("Failed to add store.")

    # List stores
    st.caption(f"{len(stores)} store(s)")
    for s in stores:
        active = "" if s.get("is_active") else " (INACTIVE)"
        with st.expander(f"{s['store_number']} - {s['name']}{active}"):
            st.markdown(f"**Phone:** {s.get('phone') or 'Not set'}")
            st.markdown(f"**Address:** {s.get('address', 'N/A')}")
            st.markdown(f"**City:** {s.get('city', 'N/A')}, {s.get('state', 'N/A')}")
            st.markdown(f"**Region:** {s.get('region', 'N/A')}")

            if s.get("is_active"):
                if st.button("Deactivate Store", key=f"deact_store_{s['id']}"):
                    update_store(s["id"], {"is_active": False})
                    st.rerun()
            else:
                if st.button("Reactivate Store", key=f"react_store_{s['id']}"):
                    update_store(s["id"], {"is_active": True})
                    st.rerun()


# ------------------------------------------------------------------
# Form Categories
# ------------------------------------------------------------------

def _render_category_management(client_id: str):
    st.markdown("### Form Categories")
    st.caption("These appear as options in the repair request category dropdown.")

    try:
        sb = get_client()
        # Get categories for this client AND global ones
        result = (
            sb.table("form_categories")
            .select("*")
            .or_(f"client_id.eq.{client_id},client_id.is.null")
            .order("display_order")
            .execute()
        )
        categories = result.data or []
    except Exception:
        categories = []

    # Add new
    with st.expander("+ Add Category"):
        with st.form("add_category"):
            cat_name = st.text_input("Category Name *")
            cat_icon = st.text_input("Icon (emoji)", placeholder="wrench icon")
            cat_order = st.number_input("Display Order", min_value=0, value=len(categories) + 1)
            req_serial = st.checkbox("Requires Serial Number")

            if st.form_submit_button("Add Category", use_container_width=True):
                if not cat_name:
                    st.error("Category name is required.")
                else:
                    try:
                        sb = get_client()
                        sb.table("form_categories").insert({
                            "client_id": client_id,
                            "name": cat_name,
                            "icon": cat_icon or None,
                            "display_order": cat_order,
                            "requires_serial": req_serial,
                        }).execute()
                        st.success(f"Category '{cat_name}' added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding category: {str(e)}")

    # List
    for cat in categories:
        is_global = cat.get("client_id") is None
        scope_label = " [GLOBAL]" if is_global else ""
        active = "" if cat.get("is_active") else " (INACTIVE)"
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"{cat.get('icon', '')} {cat['name']}{active}{scope_label} (Order: {cat.get('display_order', 0)})")
        with col2:
            st.caption(f"Serial: {'Yes' if cat.get('requires_serial') else 'No'}")
        with col3:
            # Only allow toggling client-owned categories
            if not is_global:
                if cat.get("is_active"):
                    if st.button("Disable", key=f"dis_cat_{cat['id']}"):
                        try:
                            sb = get_client()
                            sb.table("form_categories").update({"is_active": False}).eq("id", cat["id"]).execute()
                            st.rerun()
                        except Exception:
                            st.error("Failed to disable category.")
                else:
                    if st.button("Enable", key=f"en_cat_{cat['id']}"):
                        try:
                            sb = get_client()
                            sb.table("form_categories").update({"is_active": True}).eq("id", cat["id"]).execute()
                            st.rerun()
                        except Exception:
                            st.error("Failed to enable category.")
            else:
                st.caption("Global")


# ------------------------------------------------------------------
# Urgency Levels
# ------------------------------------------------------------------

def _render_urgency_management(client_id: str):
    st.markdown("### Urgency Levels")
    st.caption("These appear as options in the repair request urgency selection.")

    try:
        sb = get_client()
        result = (
            sb.table("form_urgency_levels")
            .select("*")
            .or_(f"client_id.eq.{client_id},client_id.is.null")
            .order("display_order")
            .execute()
        )
        levels = result.data or []
    except Exception:
        levels = []

    # Add new
    with st.expander("+ Add Urgency Level"):
        with st.form("add_urgency"):
            urg_name = st.text_input("Level Name *")
            urg_color = st.color_picker("Color", "#FF9800")
            urg_order = st.number_input("Display Order", min_value=0, value=len(levels) + 1)
            urg_sla = st.number_input("SLA Hours (target response time)", min_value=0, value=24)

            if st.form_submit_button("Add Urgency Level", use_container_width=True):
                if not urg_name:
                    st.error("Level name is required.")
                else:
                    try:
                        sb = get_client()
                        sb.table("form_urgency_levels").insert({
                            "client_id": client_id,
                            "name": urg_name,
                            "color": urg_color,
                            "display_order": urg_order,
                            "sla_hours": urg_sla if urg_sla > 0 else None,
                        }).execute()
                        st.success(f"Urgency level '{urg_name}' added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding urgency level: {str(e)}")

    # List
    for lvl in levels:
        is_global = lvl.get("client_id") is None
        scope_label = " [GLOBAL]" if is_global else ""
        active = "" if lvl.get("is_active") else " (INACTIVE)"
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(
                f'<span style="color: {lvl.get("color", "#757575")};">o</span> '
                f'{lvl["name"]}{active}{scope_label} (SLA: {lvl.get("sla_hours", "N/A")}h)',
                unsafe_allow_html=True,
            )
        with col2:
            st.caption(f"Order: {lvl.get('display_order', 0)}")
        with col3:
            if not is_global:
                if lvl.get("is_active"):
                    if st.button("Disable", key=f"dis_urg_{lvl['id']}"):
                        try:
                            sb = get_client()
                            sb.table("form_urgency_levels").update({"is_active": False}).eq("id", lvl["id"]).execute()
                            st.rerun()
                        except Exception:
                            st.error("Failed to disable urgency level.")
                else:
                    if st.button("Enable", key=f"en_urg_{lvl['id']}"):
                        try:
                            sb = get_client()
                            sb.table("form_urgency_levels").update({"is_active": True}).eq("id", lvl["id"]).execute()
                            st.rerun()
                        except Exception:
                            st.error("Failed to enable urgency level.")
            else:
                st.caption("Global")


# ------------------------------------------------------------------
# Approval Settings
# ------------------------------------------------------------------

def _render_approval_settings(client_id: str):
    st.markdown("### Approval Settings")

    # Show current threshold
    threshold = get_threshold(client_id)
    st.markdown(f"**Current Approval Threshold:** {format_currency(threshold)}")
    st.caption("Tickets with estimated costs above this amount require approval.")

    # Update threshold
    new_threshold = st.number_input(
        "New Approval Threshold ($)",
        min_value=0.0,
        value=float(threshold),
        step=100.0,
        key="new_threshold",
    )
    if st.button("Update Threshold", use_container_width=True):
        try:
            sb = get_client()
            user = get_current_user()
            sb.table("approval_thresholds").insert({
                "client_id": client_id,
                "threshold_amount": new_threshold,
                "updated_by": user["id"] if user else None,
            }).execute()
            st.success(f"Threshold updated to {format_currency(new_threshold)}")
            st.rerun()
        except Exception as e:
            st.error(f"Error updating threshold: {str(e)}")

    # Show approval chain configuration
    st.markdown("---")
    st.markdown("### Approval Chain Configuration")

    config = get_approval_config(client_id)
    if not config:
        st.info("No approval chain configured for this client. Default single-step approval will be used.")
    else:
        for step in config:
            st.markdown(
                f"**Step {step.get('step_order', '?')}:** "
                f"Role = {step.get('role_required', 'N/A').upper()}"
            )

    # Add approval step
    with st.expander("+ Add Approval Step"):
        with st.form("add_approval_step"):
            role_required = st.selectbox(
                "Role Required",
                CLIENT_ROLES,
                format_func=lambda x: CLIENT_ROLE_LABELS.get(x, x),
            )
            step_order = st.number_input("Step Order", min_value=1, value=len(config) + 1)

            if st.form_submit_button("Add Step", use_container_width=True):
                try:
                    sb = get_client()
                    sb.table("approval_chain_config").insert({
                        "client_id": client_id,
                        "role_required": role_required,
                        "step_order": step_order,
                    }).execute()
                    st.success(f"Approval step added for {CLIENT_ROLE_LABELS.get(role_required, role_required)}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding approval step: {str(e)}")


# ------------------------------------------------------------------
# Equipment Options by Brand
# ------------------------------------------------------------------

def _render_equipment_options(client_id: str):
    st.markdown("### Equipment Options by Brand")
    st.caption("Manage the equipment dropdown options that appear when submitting a ticket. Filtered by store brand and category.")

    # Get existing options
    try:
        sb = get_client()
        result = (
            sb.table("brand_equipment_options")
            .select("*")
            .eq("client_id", client_id)
            .order("brand")
            .order("category")
            .order("display_order")
            .execute()
        )
        options = result.data or []
    except Exception:
        options = []

    # Get unique brands from stores
    try:
        stores_result = (
            sb.table("stores")
            .select("brand")
            .eq("client_id", client_id)
            .execute()
        )
        brands = sorted(set(s["brand"] for s in (stores_result.data or []) if s.get("brand")))
    except Exception:
        brands = []

    # Get categories
    try:
        cat_result = (
            sb.table("form_categories")
            .select("name")
            .or_(f"client_id.eq.{client_id},client_id.is.null")
            .eq("is_active", True)
            .order("display_order")
            .execute()
        )
        categories = [c["name"] for c in (cat_result.data or [])]
    except Exception:
        categories = []

    # Add new equipment option
    with st.expander("+ Add Equipment Option"):
        with st.form("add_equipment_option"):
            eq_brand = st.selectbox("Brand *", brands if brands else ["No brands found"])
            eq_category = st.selectbox("Category *", categories if categories else ["No categories found"])
            eq_name = st.text_input("Equipment Name *", placeholder="e.g., Fryer, Grill, Ice Machine")
            eq_order = st.number_input("Display Order", min_value=0, value=len(options) + 1)

            if st.form_submit_button("Add Equipment Option", use_container_width=True):
                if not eq_name:
                    st.error("Equipment name is required.")
                elif eq_brand == "No brands found" or eq_category == "No categories found":
                    st.error("Please ensure brands and categories exist first.")
                else:
                    try:
                        sb = get_client()
                        sb.table("brand_equipment_options").insert({
                            "client_id": client_id,
                            "brand": eq_brand,
                            "category": eq_category,
                            "equipment_name": eq_name,
                            "display_order": eq_order,
                        }).execute()
                        st.success(f"'{eq_name}' added to {eq_brand} / {eq_category}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding equipment option: {str(e)}")

    # Filter view
    if brands:
        filter_brand = st.selectbox("Filter by Brand", ["All Brands"] + brands, key="eq_filter_brand")
    else:
        filter_brand = "All Brands"

    # Display grouped by brand and category
    filtered = options
    if filter_brand != "All Brands":
        filtered = [o for o in options if o.get("brand") == filter_brand]

    if not filtered:
        st.info("No equipment options configured yet. Add some above.")
        return

    # Group by brand then category
    current_brand = None
    current_category = None
    for opt in filtered:
        brand = opt.get("brand", "Unknown")
        category = opt.get("category", "Uncategorized")

        if brand != current_brand:
            st.markdown(f"---")
            st.markdown(f"#### {brand}")
            current_brand = brand
            current_category = None

        if category != current_category:
            st.markdown(f"**{category}**")
            current_category = category

        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            active_label = "" if opt.get("is_active", True) else " *(INACTIVE)*"
            st.write(f"  {opt['equipment_name']}{active_label}")
        with col2:
            st.caption(f"Order: {opt.get('display_order', 0)}")
        with col3:
            if opt.get("is_active", True):
                if st.button("Disable", key=f"dis_eq_{opt['id']}"):
                    try:
                        sb = get_client()
                        sb.table("brand_equipment_options").update({"is_active": False}).eq("id", opt["id"]).execute()
                        st.rerun()
                    except Exception:
                        st.error("Failed to disable.")
            else:
                if st.button("Enable", key=f"en_eq_{opt['id']}"):
                    try:
                        sb = get_client()
                        sb.table("brand_equipment_options").update({"is_active": True}).eq("id", opt["id"]).execute()
                        st.rerun()
                    except Exception:
                        st.error("Failed to enable.")
