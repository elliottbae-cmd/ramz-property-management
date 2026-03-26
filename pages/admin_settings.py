"""
Admin Settings — Manage users, stores, equipment, form config, and approval settings.
Admin-only page.
"""

import streamlit as st
from database.supabase_client import (
    get_current_user, has_role, get_users, update_user,
    get_stores, get_equipment, get_form_categories, get_form_urgency_levels,
    get_form_fields, get_approval_settings, update_approval_settings,
    get_user_stores
)
from theme.branding import render_header
from utils.constants import ROLES, ROLE_LABELS, TRADE_TYPES, US_STATES
from utils.helpers import format_currency


def render():
    render_header("Admin Settings", "System configuration")

    user = get_current_user()
    if not user or not has_role("admin"):
        st.error("Admin access required.")
        return

    tab_users, tab_stores, tab_categories, tab_urgency, tab_fields, tab_approvals = st.tabs(
        ["Users", "Stores", "Form Categories", "Urgency Levels", "Custom Fields", "Approval Settings"]
    )

    with tab_users:
        _render_user_management()

    with tab_stores:
        _render_store_management()

    with tab_categories:
        _render_category_management()

    with tab_urgency:
        _render_urgency_management()

    with tab_fields:
        _render_field_management()

    with tab_approvals:
        _render_approval_settings()


# ------------------------------------------------------------------
# User Management
# ------------------------------------------------------------------

def _render_user_management():
    st.markdown("### Manage Users")

    # Filter by role
    role_filter = st.selectbox(
        "Filter by Role",
        ["All"] + ROLES,
        format_func=lambda x: ROLE_LABELS.get(x, x) if x != "All" else "All Roles"
    )

    users = get_users(role=role_filter if role_filter != "All" else None, active_only=False)

    if not users:
        st.info("No users found.")
        return

    st.caption(f"{len(users)} user(s)")

    for u in users:
        store = u.get("stores", {}) or {}
        store_label = f"{store.get('store_number', '')} - {store.get('name', '')}" if store else "None"
        active_label = "" if u.get("is_active") else " (INACTIVE)"

        with st.expander(f"{u.get('full_name', 'Unknown')}{active_label} — {ROLE_LABELS.get(u.get('role', ''), u.get('role', ''))}"):
            st.markdown(f"**Email:** {u.get('email', 'N/A')}")
            st.markdown(f"**Phone:** {u.get('phone', 'N/A')}")
            st.markdown(f"**Primary Store:** {store_label}")

            col1, col2 = st.columns(2)
            with col1:
                new_role = st.selectbox(
                    "Role",
                    ROLES,
                    index=ROLES.index(u["role"]) if u.get("role") in ROLES else 0,
                    format_func=lambda x: ROLE_LABELS.get(x, x),
                    key=f"role_{u['id']}"
                )
            with col2:
                stores = get_stores()
                store_ids = [""] + [s["id"] for s in stores]
                store_labels = {"": "None"} | {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}
                current_store = u.get("store_id", "")
                new_store = st.selectbox(
                    "Primary Store",
                    store_ids,
                    index=store_ids.index(current_store) if current_store in store_ids else 0,
                    format_func=lambda x: store_labels.get(x, x),
                    key=f"store_{u['id']}"
                )

            col_save, col_toggle = st.columns(2)
            with col_save:
                if st.button("Save Changes", key=f"save_{u['id']}", use_container_width=True):
                    update_data = {"role": new_role}
                    if new_store:
                        update_data["store_id"] = new_store
                    else:
                        update_data["store_id"] = None
                    update_user(u["id"], update_data)
                    st.success(f"Updated {u['full_name']}!")
                    st.rerun()
            with col_toggle:
                if u.get("is_active"):
                    if st.button("Deactivate", key=f"deact_{u['id']}", use_container_width=True):
                        update_user(u["id"], {"is_active": False})
                        st.success(f"Deactivated {u['full_name']}.")
                        st.rerun()
                else:
                    if st.button("Reactivate", key=f"react_{u['id']}", use_container_width=True):
                        update_user(u["id"], {"is_active": True})
                        st.success(f"Reactivated {u['full_name']}.")
                        st.rerun()


# ------------------------------------------------------------------
# Store Management
# ------------------------------------------------------------------

def _render_store_management():
    st.markdown("### Manage Stores")

    stores = get_stores(active_only=False)

    # Add new store
    with st.expander("+ Add New Store"):
        with st.form("add_store"):
            col1, col2 = st.columns(2)
            with col1:
                store_num = st.text_input("Store Number *", placeholder="006")
                name = st.text_input("Store Name *", placeholder="Ram-Z #006 - Downtown")
                address = st.text_input("Address")
            with col2:
                city = st.text_input("City")
                state = st.selectbox("State", [""] + US_STATES)
                region = st.text_input("Region", placeholder="e.g., Nebraska")

            if st.form_submit_button("Add Store", use_container_width=True):
                if not store_num or not name:
                    st.error("Store number and name are required.")
                else:
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("stores").insert({
                        "store_number": store_num,
                        "name": name,
                        "address": address or None,
                        "city": city or None,
                        "state": state or None,
                        "region": region or None,
                    }).execute()
                    st.success(f"Store '{name}' added!")
                    st.rerun()

    # List stores
    st.caption(f"{len(stores)} store(s)")
    for s in stores:
        active = "" if s.get("is_active") else " (INACTIVE)"
        with st.expander(f"{s['store_number']} - {s['name']}{active}"):
            st.markdown(f"**Address:** {s.get('address', 'N/A')}")
            st.markdown(f"**City:** {s.get('city', 'N/A')}, {s.get('state', 'N/A')}")
            st.markdown(f"**Region:** {s.get('region', 'N/A')}")

            if s.get("is_active"):
                if st.button("Deactivate Store", key=f"deact_store_{s['id']}"):
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("stores").update({"is_active": False}).eq("id", s["id"]).execute()
                    st.rerun()
            else:
                if st.button("Reactivate Store", key=f"react_store_{s['id']}"):
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("stores").update({"is_active": True}).eq("id", s["id"]).execute()
                    st.rerun()


# ------------------------------------------------------------------
# Form Categories
# ------------------------------------------------------------------

def _render_category_management():
    st.markdown("### Form Categories")
    st.caption("These appear as options in the repair request category dropdown.")

    categories = get_form_categories(active_only=False)

    # Add new
    with st.expander("+ Add Category"):
        with st.form("add_category"):
            cat_name = st.text_input("Category Name *")
            cat_icon = st.text_input("Icon (emoji)", placeholder="🔧")
            cat_order = st.number_input("Display Order", min_value=0, value=len(categories) + 1)
            req_serial = st.checkbox("Requires Serial Number")

            if st.form_submit_button("Add Category", use_container_width=True):
                if not cat_name:
                    st.error("Category name is required.")
                else:
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_categories").insert({
                        "name": cat_name,
                        "icon": cat_icon or None,
                        "display_order": cat_order,
                        "requires_serial": req_serial,
                    }).execute()
                    st.success(f"Category '{cat_name}' added!")
                    st.rerun()

    # List
    for cat in categories:
        active = "" if cat.get("is_active") else " (INACTIVE)"
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"{cat.get('icon', '')} {cat['name']}{active} (Order: {cat.get('display_order', 0)})")
        with col2:
            st.caption(f"Serial: {'Yes' if cat.get('requires_serial') else 'No'}")
        with col3:
            if cat.get("is_active"):
                if st.button("Disable", key=f"dis_cat_{cat['id']}"):
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_categories").update({"is_active": False}).eq("id", cat["id"]).execute()
                    st.rerun()
            else:
                if st.button("Enable", key=f"en_cat_{cat['id']}"):
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_categories").update({"is_active": True}).eq("id", cat["id"]).execute()
                    st.rerun()


# ------------------------------------------------------------------
# Urgency Levels
# ------------------------------------------------------------------

def _render_urgency_management():
    st.markdown("### Urgency Levels")
    st.caption("These appear as options in the repair request urgency selection.")

    levels = get_form_urgency_levels(active_only=False)

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
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_urgency_levels").insert({
                        "name": urg_name,
                        "color": urg_color,
                        "display_order": urg_order,
                        "sla_hours": urg_sla if urg_sla > 0 else None,
                    }).execute()
                    st.success(f"Urgency level '{urg_name}' added!")
                    st.rerun()

    # List
    for lvl in levels:
        active = "" if lvl.get("is_active") else " (INACTIVE)"
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(
                f'<span style="color: {lvl.get("color", "#757575")};">●</span> '
                f'{lvl["name"]}{active} (SLA: {lvl.get("sla_hours", "N/A")}h)',
                unsafe_allow_html=True
            )
        with col2:
            st.caption(f"Order: {lvl.get('display_order', 0)}")
        with col3:
            if lvl.get("is_active"):
                if st.button("Disable", key=f"dis_urg_{lvl['id']}"):
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_urgency_levels").update({"is_active": False}).eq("id", lvl["id"]).execute()
                    st.rerun()
            else:
                if st.button("Enable", key=f"en_urg_{lvl['id']}"):
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_urgency_levels").update({"is_active": True}).eq("id", lvl["id"]).execute()
                    st.rerun()


# ------------------------------------------------------------------
# Custom Form Fields
# ------------------------------------------------------------------

def _render_field_management():
    st.markdown("### Custom Form Fields")
    st.caption("Add extra fields to the repair request form. Fields can be scoped to specific categories.")

    fields = get_form_fields(active_only=False)
    categories = get_form_categories(active_only=False)
    cat_options = {"": "All Categories"} | {c["id"]: c["name"] for c in categories}

    # Add new
    with st.expander("+ Add Custom Field"):
        with st.form("add_field"):
            field_name = st.text_input("Field Key *", placeholder="e.g., brand_name")
            field_label = st.text_input("Display Label *", placeholder="e.g., Equipment Brand")
            field_type = st.selectbox("Field Type", ["text", "textarea", "dropdown", "number", "date", "checkbox"])
            is_required = st.checkbox("Required")
            field_order = st.number_input("Display Order", min_value=0, value=len(fields) + 1)
            cat_filter = st.selectbox("Category (leave blank for all)", list(cat_options.keys()),
                                       format_func=lambda x: cat_options[x])
            options_str = ""
            if field_type == "dropdown":
                options_str = st.text_input("Dropdown Options (comma-separated)", placeholder="Option A, Option B, Option C")

            if st.form_submit_button("Add Field", use_container_width=True):
                if not field_name or not field_label:
                    st.error("Field key and label are required.")
                else:
                    opts = [o.strip() for o in options_str.split(",") if o.strip()] if options_str else None
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_fields").insert({
                        "field_name": field_name,
                        "label": field_label,
                        "field_type": field_type,
                        "is_required": is_required,
                        "display_order": field_order,
                        "options": opts,
                        "category_filter": cat_filter or None,
                    }).execute()
                    st.success(f"Field '{field_label}' added!")
                    st.rerun()

    # List
    for f in fields:
        active = "" if f.get("is_active") else " (INACTIVE)"
        cat_name = next((c["name"] for c in categories if c["id"] == f.get("category_filter")), "All")
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"{f['label']}{active} ({f['field_type']}) — Category: {cat_name}")
        with col2:
            st.caption(f"{'Required' if f.get('is_required') else 'Optional'}")
        with col3:
            if f.get("is_active"):
                if st.button("Disable", key=f"dis_field_{f['id']}"):
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_fields").update({"is_active": False}).eq("id", f["id"]).execute()
                    st.rerun()
            else:
                if st.button("Enable", key=f"en_field_{f['id']}"):
                    from database.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    client.table("form_fields").update({"is_active": True}).eq("id", f["id"]).execute()
                    st.rerun()


# ------------------------------------------------------------------
# Approval Settings
# ------------------------------------------------------------------

def _render_approval_settings():
    st.markdown("### Approval Settings")
    st.caption("Configure approval thresholds and requirements by role level.")

    settings = get_approval_settings()

    if not settings:
        st.info("No approval settings found. Run the seed_data.sql to initialize.")
        return

    for setting in settings:
        role = setting.get("role", "")
        st.markdown(f"#### {role.upper()} Level")

        col1, col2 = st.columns(2)
        with col1:
            max_approve = st.number_input(
                f"Max auto-approve amount ($) for {role.upper()}",
                min_value=0.0,
                value=float(setting.get("max_auto_approve", 0)),
                step=500.0,
                key=f"max_{setting['id']}",
                help="Tickets below this amount can be approved at this level without escalation (when enabled)"
            )
        with col2:
            is_active = st.checkbox(
                f"{role.upper()} approval required",
                value=setting.get("is_active", True),
                key=f"active_{setting['id']}",
                help="Uncheck to skip this approval level"
            )

        if st.button(f"Save {role.upper()} Settings", key=f"save_approval_{setting['id']}", use_container_width=True):
            update_approval_settings(setting["id"], {
                "max_auto_approve": max_approve,
                "is_active": is_active,
            })
            st.success(f"{role.upper()} approval settings updated!")
            st.rerun()

        st.markdown("---")

    st.info(
        "**Current mode:** All three approval levels are required for every ticket. "
        "To enable cost-based auto-approval, set a max amount and uncheck levels that should be skipped "
        "for tickets below that threshold."
    )
