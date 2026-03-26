"""
Ram-Z Property Management App
Main entry point — handles navigation and page routing.

Run with: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Ram-Z Property Management",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="auto",
)

from components.auth import require_auth, render_user_sidebar
from database.supabase_client import is_logged_in, get_current_user, has_role
from theme.branding import apply_branding, render_sidebar_logo

# Apply branding on every page load
apply_branding()

# Auth gate — shows login page if not authenticated
require_auth()

# Sidebar
render_sidebar_logo()
render_user_sidebar()

# Navigation based on role
user = get_current_user()
role = user.get("role", "staff") if user else "staff"

# Build navigation options based on role
nav_items = {}

# Everyone can submit and view their tickets
nav_items["Submit Repair Request"] = "pages/1_submit_request"
nav_items["My Tickets"] = "pages/2_my_tickets"

# GM, DM, Director, Admin, Property Manager — approval queue
if role in ("gm", "dm", "director", "admin"):
    nav_items["Approval Queue"] = "pages/4_approval_queue"

# Property Manager, Admin, Director — ticket dashboard
if role in ("property_manager", "admin", "director"):
    nav_items["Ticket Dashboard"] = "pages/3_ticket_dashboard"

# Property Manager, Admin — contractor directory
if role in ("property_manager", "admin", "director"):
    nav_items["Contractor Directory"] = "pages/5_contractor_directory"

# Admin, Director, Property Manager, DM — store history
if role in ("admin", "director", "property_manager", "dm"):
    nav_items["Store History & Reports"] = "pages/6_store_history"

# Admin only — settings
if role == "admin":
    nav_items["Admin Settings"] = "pages/7_admin_settings"

# Sidebar navigation
st.sidebar.markdown("---")
selected = st.sidebar.radio("Navigation", list(nav_items.keys()), label_visibility="collapsed")

# Route to selected page
page_module = nav_items[selected]

if page_module == "pages/1_submit_request":
    from pages import submit_request
    submit_request.render()
elif page_module == "pages/2_my_tickets":
    from pages import my_tickets
    my_tickets.render()
elif page_module == "pages/3_ticket_dashboard":
    from pages import ticket_dashboard
    ticket_dashboard.render()
elif page_module == "pages/4_approval_queue":
    from pages import approval_queue
    approval_queue.render()
elif page_module == "pages/5_contractor_directory":
    from pages import contractor_directory
    contractor_directory.render()
elif page_module == "pages/6_store_history":
    from pages import store_history
    store_history.render()
elif page_module == "pages/7_admin_settings":
    from pages import admin_settings
    admin_settings.render()
