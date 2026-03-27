"""
PSP Admin -- Master admin panel for Plaza Street Partners.
Client management, user management across all tenants, and system-wide controls.
Only accessible to PSP-tier users.
"""

import streamlit as st
from database.supabase_client import get_current_user, get_client, sign_up
from database.tenant import get_all_clients
from database.users import get_users_for_client, create_user_profile, update_user
from database.stores import get_stores, create_store
from database.audit import log_action, get_audit_log
from theme.branding import render_header
from utils.permissions import require_permission, can_access_psp_admin
from utils.constants import (
    PSP_ROLES, PSP_ROLE_LABELS, CLIENT_ROLES, CLIENT_ROLE_LABELS,
    ROLE_LABELS, US_STATES,
)
from utils.helpers import format_date


def render():
    render_header("PSP Admin", "System administration for Plaza Street Partners")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    require_permission(can_access_psp_admin, "PSP admin access required.")

    tab_clients, tab_users, tab_create_user, tab_audit = st.tabs(
        ["Clients", "Users", "Create User", "Audit Log"]
    )

    with tab_clients:
        _render_client_management(user)

    with tab_users:
        _render_user_management(user)

    with tab_create_user:
        _render_create_user(user)

    with tab_audit:
        _render_audit_log(user)


# ------------------------------------------------------------------
# Client Management
# ------------------------------------------------------------------

def _render_client_management(user: dict):
    st.markdown("### Client Management")

    clients = get_all_clients()

    if not clients:
        st.info("No clients found.")

    # Add new client
    with st.expander("+ Add New Client"):
        with st.form("add_client"):
            col1, col2 = st.columns(2)
            with col1:
                client_name = st.text_input("Client Name *", placeholder="e.g., Runza National")
                client_slug = st.text_input(
                    "Slug *",
                    placeholder="e.g., runza-national",
                    help="URL-friendly identifier (lowercase, hyphens)",
                )
            with col2:
                primary_color = st.color_picker("Primary Color", "#C4A04D")
                secondary_color = st.color_picker("Secondary Color", "#1B3A4B")

            logo_url = st.text_input("Logo URL (optional)", placeholder="https://...")
            tagline = st.text_input("Tagline (optional)", placeholder="e.g., Property Maintenance Portal")

            if st.form_submit_button("Create Client", use_container_width=True):
                if not client_name or not client_slug:
                    st.error("Client name and slug are required.")
                else:
                    try:
                        sb = get_client()
                        result = sb.table("clients").insert({
                            "name": client_name,
                            "slug": client_slug,
                            "primary_color": primary_color,
                            "secondary_color": secondary_color,
                            "logo_url": logo_url or None,
                            "tagline": tagline or None,
                        }).execute()

                        if result.data:
                            new_client = result.data[0]
                            log_action(
                                client_id=new_client["id"],
                                user_id=user["id"],
                                action="create",
                                entity_type="client",
                                entity_id=new_client["id"],
                                details={"name": client_name},
                            )

                            # Grant PSP user access to this client
                            sb.table("psp_client_access").insert({
                                "psp_user_id": user["id"],
                                "client_id": new_client["id"],
                            }).execute()

                            st.success(f"Client '{client_name}' created!")
                            st.rerun()
                        else:
                            st.error("Failed to create client.")
                    except Exception as e:
                        st.error(f"Error creating client: {str(e)}")

    # List clients
    if clients:
        st.caption(f"{len(clients)} client(s)")

        for client in clients:
            with st.expander(f"{client.get('name', 'Unknown')} ({client.get('slug', '')})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**ID:** `{client['id']}`")
                    st.markdown(f"**Slug:** {client.get('slug', 'N/A')}")
                    st.markdown(f"**Tagline:** {client.get('tagline', 'N/A')}")
                with col2:
                    primary = client.get("primary_color", "#C4A04D")
                    secondary = client.get("secondary_color", "#1B3A4B")
                    st.markdown(
                        f'**Primary Color:** <span style="color:{primary};">{primary}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'**Secondary Color:** <span style="color:{secondary};">{secondary}</span>',
                        unsafe_allow_html=True,
                    )
                    if client.get("logo_url"):
                        st.image(client["logo_url"], width=100)

                # Edit client branding
                with st.form(f"edit_client_{client['id']}"):
                    st.markdown("**Edit Client**")
                    new_name = st.text_input("Name", value=client.get("name", ""), key=f"cn_{client['id']}")
                    new_tagline = st.text_input("Tagline", value=client.get("tagline", "") or "", key=f"ct_{client['id']}")

                    ec1, ec2 = st.columns(2)
                    with ec1:
                        new_primary = st.color_picker(
                            "Primary Color",
                            value=client.get("primary_color", "#C4A04D"),
                            key=f"cp_{client['id']}",
                        )
                    with ec2:
                        new_secondary = st.color_picker(
                            "Secondary Color",
                            value=client.get("secondary_color", "#1B3A4B"),
                            key=f"cs_{client['id']}",
                        )

                    new_logo = st.text_input(
                        "Logo URL",
                        value=client.get("logo_url", "") or "",
                        key=f"cl_{client['id']}",
                    )

                    if st.form_submit_button("Save Changes", use_container_width=True):
                        try:
                            sb = get_client()
                            sb.table("clients").update({
                                "name": new_name,
                                "tagline": new_tagline or None,
                                "primary_color": new_primary,
                                "secondary_color": new_secondary,
                                "logo_url": new_logo or None,
                            }).eq("id", client["id"]).execute()
                            st.success(f"Client '{new_name}' updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating client: {str(e)}")

                # Quick stats
                users = get_users_for_client(client["id"], active_only=False)
                stores = get_stores(client["id"], active_only=False)
                st.caption(f"{len(users)} user(s) | {len(stores)} store(s)")


# ------------------------------------------------------------------
# User Management (across all clients)
# ------------------------------------------------------------------

def _render_user_management(user: dict):
    st.markdown("### User Management")

    clients = get_all_clients()
    if not clients:
        st.info("No clients found. Create a client first.")
        return

    # Client filter
    client_options = {"all": "All Clients", "psp": "PSP Users Only"} | {
        c["id"]: c["name"] for c in clients
    }
    selected_client = st.selectbox(
        "Filter by Client",
        list(client_options.keys()),
        format_func=lambda x: client_options[x],
        key="user_mgmt_client",
    )

    if selected_client == "psp":
        # Show PSP users
        try:
            sb = get_client()
            result = (
                sb.table("users")
                .select("*")
                .eq("user_tier", "psp")
                .order("full_name")
                .execute()
            )
            users = result.data or []
        except Exception:
            users = []
    elif selected_client == "all":
        users = []
        for c in clients:
            client_users = get_users_for_client(c["id"], active_only=False)
            for u in client_users:
                u["_client_name"] = c["name"]
            users.extend(client_users)
        # Also include PSP users
        try:
            sb = get_client()
            psp_result = (
                sb.table("users")
                .select("*")
                .eq("user_tier", "psp")
                .order("full_name")
                .execute()
            )
            for u in (psp_result.data or []):
                u["_client_name"] = "PSP"
            users.extend(psp_result.data or [])
        except Exception:
            pass
    else:
        users = get_users_for_client(selected_client, active_only=False)
        client_name = next((c["name"] for c in clients if c["id"] == selected_client), "")
        for u in users:
            u["_client_name"] = client_name

    if not users:
        st.info("No users found.")
        return

    st.caption(f"{len(users)} user(s)")

    for u in users:
        tier = u.get("user_tier", "")
        role = u.get("psp_role") if tier == "psp" else u.get("client_role", "")
        role_label = ROLE_LABELS.get(role, role)
        active_label = "" if u.get("is_active", True) else " (INACTIVE)"
        client_label = u.get("_client_name", "")

        with st.expander(f"{u.get('full_name', 'Unknown')}{active_label} -- {role_label} [{client_label}]"):
            st.markdown(f"**Email:** {u.get('email', 'N/A')}")
            st.markdown(f"**Tier:** {tier}")
            st.markdown(f"**Role:** {role_label}")
            if u.get("client_id"):
                st.markdown(f"**Client ID:** `{u['client_id']}`")

            # Edit role
            col1, col2 = st.columns(2)
            with col1:
                if tier == "psp":
                    role_options = PSP_ROLES
                    role_labels = PSP_ROLE_LABELS
                else:
                    role_options = CLIENT_ROLES
                    role_labels = CLIENT_ROLE_LABELS

                current_role = role or ""
                role_idx = list(role_options).index(current_role) if current_role in role_options else 0
                new_role = st.selectbox(
                    "Role",
                    role_options,
                    index=role_idx,
                    format_func=lambda x: role_labels.get(x, x),
                    key=f"role_{u['id']}",
                )

            with col2:
                is_active = st.checkbox("Active", value=u.get("is_active", True), key=f"active_{u['id']}")

            if st.button("Save Changes", key=f"save_{u['id']}", use_container_width=True):
                update_data = {"is_active": is_active}
                if tier == "psp":
                    update_data["psp_role"] = new_role
                else:
                    update_data["client_role"] = new_role

                result = update_user(u["id"], update_data)
                if result:
                    st.success(f"Updated {u['full_name']}!")
                    st.rerun()
                else:
                    st.error("Failed to update user.")


# ------------------------------------------------------------------
# Create User
# ------------------------------------------------------------------

def _render_create_user(admin_user: dict):
    st.markdown("### Create New User")

    clients = get_all_clients()

    with st.form("create_user"):
        email = st.text_input("Email *", placeholder="user@example.com")
        full_name = st.text_input("Full Name *", placeholder="John Doe")
        password = st.text_input("Temporary Password *", type="password")

        st.markdown("---")

        user_tier = st.selectbox("User Tier *", ["client", "psp"], format_func=lambda x: x.upper())

        if user_tier == "psp":
            psp_role = st.selectbox(
                "PSP Role *",
                PSP_ROLES,
                format_func=lambda x: PSP_ROLE_LABELS.get(x, x),
            )
            client_id = None
            client_role = None
            store_id = None
        else:
            psp_role = None
            if clients:
                client_options = {c["id"]: c["name"] for c in clients}
                client_id = st.selectbox(
                    "Client *",
                    list(client_options.keys()),
                    format_func=lambda x: client_options[x],
                )
            else:
                st.warning("No clients exist. Create a client first.")
                client_id = None

            client_role = st.selectbox(
                "Client Role *",
                CLIENT_ROLES,
                format_func=lambda x: CLIENT_ROLE_LABELS.get(x, x),
            )

            # Store assignment
            if client_id:
                stores = get_stores(client_id)
                if stores:
                    store_options = {"": "No Store Assignment"} | {
                        s["id"]: f"{s['store_number']} - {s['name']}" for s in stores
                    }
                    store_id = st.selectbox(
                        "Assign to Store",
                        list(store_options.keys()),
                        format_func=lambda x: store_options[x],
                    )
                else:
                    store_id = None
                    st.caption("No stores for this client yet.")
            else:
                store_id = None

        if st.form_submit_button("Create User", type="primary", use_container_width=True):
            # Validation
            errors = []
            if not email:
                errors.append("Email is required.")
            if not full_name:
                errors.append("Full name is required.")
            if not password or len(password) < 6:
                errors.append("Password must be at least 6 characters.")
            if user_tier == "client" and not client_id:
                errors.append("Client selection is required for client-tier users.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    # Create the auth account and profile
                    result = sign_up(
                        email=email,
                        password=password,
                        full_name=full_name,
                        user_tier=user_tier,
                        client_id=client_id,
                        client_role=client_role,
                        psp_role=psp_role,
                    )

                    if result and result.user:
                        # If sign_up did not create the profile (no session), create it manually
                        if not result.session:
                            profile_data = {
                                "id": result.user.id,
                                "email": email,
                                "full_name": full_name,
                                "user_tier": user_tier,
                            }
                            if user_tier == "psp" and psp_role:
                                profile_data["psp_role"] = psp_role
                            if user_tier == "client":
                                profile_data["client_id"] = client_id
                                profile_data["client_role"] = client_role
                            create_user_profile(profile_data)

                        # Assign store if applicable
                        if store_id and store_id != "":
                            sb = get_client()
                            sb.table("user_stores").insert({
                                "user_id": result.user.id,
                                "store_id": store_id,
                            }).execute()

                        # Grant PSP client access if PSP user
                        if user_tier == "psp":
                            sb = get_client()
                            for c in clients:
                                sb.table("psp_client_access").insert({
                                    "psp_user_id": result.user.id,
                                    "client_id": c["id"],
                                }).execute()

                        st.success(f"User '{full_name}' created successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to create user account.")
                except Exception as e:
                    st.error(f"Error creating user: {str(e)}")


# ------------------------------------------------------------------
# Audit Log
# ------------------------------------------------------------------

def _render_audit_log(user: dict):
    st.markdown("### Audit Log")

    clients = get_all_clients()
    if not clients:
        st.info("No clients found.")
        return

    client_options = {c["id"]: c["name"] for c in clients}
    selected_client = st.selectbox(
        "Select Client",
        list(client_options.keys()),
        format_func=lambda x: client_options[x],
        key="audit_client",
    )

    if not selected_client:
        return

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        action_filter = st.selectbox(
            "Action",
            ["All", "create", "update", "approve", "reject", "delete"],
            key="audit_action",
        )
    with col2:
        entity_filter = st.selectbox(
            "Entity Type",
            ["All", "ticket", "work_order", "equipment", "client", "user"],
            key="audit_entity",
        )

    filters = {"limit": 50}
    if action_filter != "All":
        filters["action"] = action_filter
    if entity_filter != "All":
        filters["entity_type"] = entity_filter

    logs = get_audit_log(selected_client, filters)

    if not logs:
        st.info("No audit log entries found.")
        return

    st.caption(f"Showing {len(logs)} entries")

    for entry in logs:
        entry_user = entry.get("users", {}) or {}
        st.markdown(
            f"**{entry_user.get('full_name', 'System')}** "
            f"-- {entry.get('action', '').upper()} "
            f"{entry.get('entity_type', '')} "
            f"({format_date(entry.get('created_at', ''))})"
        )
        if entry.get("details"):
            with st.expander("Details"):
                st.json(entry["details"])
