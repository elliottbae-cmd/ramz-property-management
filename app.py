"""
PSP Property Management App
Main entry point — handles navigation and page routing.

Run with: streamlit run app.py
"""

import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="PSP Property Management",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="auto",
)

from components.auth import require_auth, render_user_sidebar
from components.client_switcher import render_client_switcher
from database.supabase_client import is_logged_in, get_current_user, is_psp_user
from theme.branding import apply_branding, render_logo, render_footer
from utils.permissions import (
    can_submit_tickets,
    can_approve,
    can_manage_tickets,
    can_manage_contractors,
    can_manage_users,
    can_view_reports,
    can_access_psp_admin,
)

# ------------------------------------------------------------------
# Apply branding on every page load
# ------------------------------------------------------------------
apply_branding()

# ------------------------------------------------------------------
# Auth gate — shows login page if not authenticated
# ------------------------------------------------------------------
require_auth()

# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------
render_logo()

# PSP users get the client switcher at the top of the sidebar
if is_psp_user():
    render_client_switcher()

render_user_sidebar()

# ------------------------------------------------------------------
# Build navigation based on tier + permissions
# ------------------------------------------------------------------
user = get_current_user()
tier = user.get("user_tier", "client") if user else "client"

nav_items: dict[str, str] = {}

if tier == "psp":
    # ---- PSP Navigation ----
    if can_access_psp_admin():
        nav_items["PSP Admin"] = "psp_admin"
        nav_items["📦 Closeout Importer"] = "closeout_import"

        # Warranty Review with pending indicator (uses cached ticket query)
        try:
            from database.tenant import get_effective_client_id as _get_eci
            _wr_client = _get_eci()
            if _wr_client:
                from database.tickets import get_tickets_for_client as _get_tfc
                _wr_tickets = _get_tfc(_wr_client, filters={"status": "warranty_check"})
                _wr_count = len(_wr_tickets)
                if _wr_count > 0:
                    nav_items[f"Warranty Review ({_wr_count})"] = "warranty_review"
                else:
                    nav_items["Warranty Review"] = "warranty_review"
            else:
                nav_items["Warranty Review"] = "warranty_review"
        except Exception:
            nav_items["Warranty Review"] = "warranty_review"

    nav_items["Submit Repair Request"] = "submit_request"
    nav_items["Ticket Dashboard"] = "ticket_dashboard"
    nav_items["Equipment Inventory"] = "equipment_inventory"

    if can_approve():
        nav_items["Approval Queue"] = "approval_queue"

    if can_manage_contractors():
        nav_items["Contractor Directory"] = "contractor_directory"

    if can_view_reports():
        nav_items["Reports Dashboard"] = "reports_dashboard"

    nav_items["Knowledge Base Admin"] = "knowledge_base_admin"
    nav_items["Warranty Management"] = "warranty_management"
    nav_items["Admin Settings"] = "admin_settings"

else:
    # ---- Client Navigation ----
    if can_submit_tickets():
        nav_items["Submit Repair Request"] = "submit_request"
        nav_items["My Tickets"] = "my_tickets"

    if can_approve():
        nav_items["Approval Queue"] = "approval_queue"

    if can_manage_tickets():
        nav_items["Ticket Dashboard"] = "ticket_dashboard"
        nav_items["Equipment Inventory"] = "equipment_inventory"

    role = user.get("client_role", "") if user else ""

    if role in ("admin", "coo", "vp"):
        nav_items["Contractor Directory"] = "contractor_directory"

    if can_view_reports():
        nav_items["Store History"] = "store_history"

    if role in ("admin", "coo"):
        nav_items["Client Settings"] = "client_settings"

# ------------------------------------------------------------------
# Sidebar navigation radio
# ------------------------------------------------------------------
st.sidebar.markdown("---")
if nav_items:
    selected = st.sidebar.radio(
        "Navigation",
        list(nav_items.keys()),
        label_visibility="collapsed",
    )
else:
    selected = None
    st.sidebar.info("No pages available for your role.")

# Footer — always present
render_footer()

# ------------------------------------------------------------------
# Page routing
# ------------------------------------------------------------------
if selected:
    page_key = nav_items[selected]

    if page_key == "submit_request":
        from pages import submit_request
        submit_request.render()

    elif page_key == "my_tickets":
        from pages import my_tickets
        my_tickets.render()

    elif page_key == "ticket_dashboard":
        from pages import ticket_dashboard
        ticket_dashboard.render()

    elif page_key == "equipment_inventory":
        from pages import equipment_inventory
        equipment_inventory.render()

    elif page_key == "approval_queue":
        from pages import approval_queue
        approval_queue.render()

    elif page_key == "contractor_directory":
        from pages import contractor_directory
        contractor_directory.render()

    elif page_key == "store_history":
        from pages import store_history
        store_history.render()

    elif page_key == "reports_dashboard":
        from pages import reports_dashboard
        reports_dashboard.render()

    elif page_key == "psp_admin":
        from pages import psp_admin
        psp_admin.render()

    elif page_key == "warranty_review":
        from pages import warranty_review
        warranty_review.render()

    elif page_key == "closeout_import":
        from pages import closeout_import
        closeout_import.render()

    elif page_key == "knowledge_base_admin":
        from pages import knowledge_base_admin
        knowledge_base_admin.render()

    elif page_key == "warranty_management":
        from pages import warranty_management
        warranty_management.render()

    elif page_key == "client_settings":
        from pages import client_settings
        client_settings.render()

    elif page_key == "admin_settings":
        from pages import admin_settings
        admin_settings.render()
