"""PSP client switcher — allows PSP users to toggle between client contexts."""

import streamlit as st
from database.supabase_client import is_psp_user
from database.tenant import get_all_clients, switch_client


def render_client_switcher():
    """Render a client selector dropdown in the sidebar (PSP users only).

    On change the effective_client_id and current_client session state
    keys are updated, and the page is reloaded so all downstream
    components pick up the new tenant context.
    """
    if not is_psp_user():
        return

    # Fetch available clients (cached in session state after login)
    clients = st.session_state.get("psp_client_list")
    if clients is None:
        clients = get_all_clients()
        st.session_state["psp_client_list"] = clients

    if not clients:
        st.sidebar.warning("No clients assigned to your account.")
        return

    # Build option list
    client_map = {c["id"]: c.get("name", c["id"]) for c in clients}
    client_ids = list(client_map.keys())
    client_names = list(client_map.values())

    # Determine current index
    current_id = st.session_state.get("effective_client_id")
    try:
        current_idx = client_ids.index(current_id)
    except (ValueError, TypeError):
        current_idx = 0

    # Render dropdown
    selected_name = st.sidebar.selectbox(
        "Active Client",
        client_names,
        index=current_idx,
        key="client_switcher_select",
    )

    # Resolve back to id
    selected_idx = client_names.index(selected_name)
    selected_id = client_ids[selected_idx]

    # Switch if changed
    if selected_id != current_id:
        result = switch_client(selected_id)
        if result:
            st.rerun()
        else:
            st.sidebar.error("Could not switch to that client.")

    # Show current client name prominently
    current_client = st.session_state.get("current_client")
    if current_client:
        st.sidebar.markdown(
            f"<div style='text-align:center; font-weight:600; padding:0.25rem 0;'>"
            f"{current_client.get('name', '')}</div>",
            unsafe_allow_html=True,
        )
