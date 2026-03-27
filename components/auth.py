"""Authentication component — multi-tenant login/signup/logout UI."""

import streamlit as st
from database.supabase_client import (
    sign_in, sign_up, sign_out, is_logged_in, get_current_user, is_psp_user,
    try_restore_session,
)
from database.tenant import get_all_clients, get_current_client
from utils.constants import ROLE_LABELS, PSP_ROLE_LABELS, CLIENT_ROLE_LABELS


# ------------------------------------------------------------------
# Defaults used before any client branding is loaded
# ------------------------------------------------------------------
_PSP_PRIMARY = "#C4A04D"
_PSP_PRIMARY_DARK = "#A6863A"


def require_auth():
    """Gate that requires authentication. Shows login if not authenticated."""
    if not is_logged_in():
        # Try to restore a saved session first
        if try_restore_session():
            _post_login_setup()
            st.rerun()
            return
        render_login_page()
        st.stop()


def render_login_page():
    """Render the multi-tenant login / create-account page."""
    # Use branding-safe import to avoid circular refs at page load
    try:
        from theme.branding import apply_branding
        apply_branding()
    except Exception:
        pass

    # Determine display name from current client or PSP default
    client = st.session_state.get("current_client")
    app_title = (client.get("name") if client else None) or "PSP Property Management"

    st.markdown(f"""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 style="color: {_PSP_PRIMARY}; font-size: 2rem;">{app_title}</h1>
        <p style="color: #757575; font-size: 1rem;">Repair Request & Maintenance Tracking</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    # ------------------------------------------------------------------
    # Sign In
    # ------------------------------------------------------------------
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="your.email@company.com")
            password = st.text_input("Password", type="password")
            remember = st.checkbox("Remember me", value=True)
            submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    try:
                        result = sign_in(email, password, remember=remember)
                        if result.user:
                            # Post-login hydration
                            _post_login_setup()
                            st.success("Signed in successfully!")
                            st.rerun()
                        else:
                            st.error("Invalid email or password.")
                    except Exception as e:
                        st.error(f"Login failed: {str(e)}")

    # ------------------------------------------------------------------
    # Create Account
    # ------------------------------------------------------------------
    with tab_signup:
        with st.form("signup_form"):
            new_name = st.text_input("Full Name", placeholder="John Smith")
            new_email = st.text_input(
                "Email", placeholder="your.email@company.com", key="signup_email",
            )
            new_password = st.text_input(
                "Password", type="password", key="signup_password",
                help="Minimum 6 characters",
            )
            confirm_password = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Create Account", use_container_width=True)

            if submitted:
                if not new_name or not new_email or not new_password:
                    st.error("Please fill in all fields.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        # Sign-up creates auth account + minimal profile.
                        # Tier and role assignment is handled later by an admin.
                        result = sign_up(new_email, new_password, new_name)
                        if result.user:
                            st.success(
                                "Account created! An administrator will assign your "
                                "role. Please sign in."
                            )
                        else:
                            st.error("Could not create account. Email may already be in use.")
                    except Exception as e:
                        st.error(f"Sign up failed: {str(e)}")

    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; color: #9E9E9E; font-size: 0.8rem;">
        Contact your administrator if you need an account or role change.
    </div>
    """, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Post-login session setup
# ------------------------------------------------------------------

def _post_login_setup():
    """Hydrate session state after a successful sign-in.

    For PSP users: preload accessible clients and set a default.
    For client users: load client branding.
    """
    profile = st.session_state.get("user_profile")
    if not profile:
        return

    tier = profile.get("user_tier")

    if tier == "psp":
        # Preload client list for the switcher
        clients = get_all_clients()
        st.session_state["psp_client_list"] = clients
        # Auto-select the first client if none is set
        if not st.session_state.get("effective_client_id") and clients:
            from database.tenant import switch_client
            switch_client(clients[0]["id"])

    elif tier == "client":
        # Load client branding record into session state
        _ = get_current_client()


# ------------------------------------------------------------------
# Sidebar user info
# ------------------------------------------------------------------

def render_user_sidebar():
    """Render user info and logout in the sidebar."""
    user = get_current_user()
    if not user:
        return

    tier = user.get("user_tier", "")
    if tier == "psp":
        role_key = user.get("psp_role", "")
        role_label = PSP_ROLE_LABELS.get(role_key, role_key)
        tier_badge = "PSP"
    else:
        role_key = user.get("client_role", "")
        role_label = CLIENT_ROLE_LABELS.get(role_key, role_key)
        tier_badge = ""

    st.sidebar.markdown("---")
    name_display = user.get("full_name", "User")
    if tier_badge:
        st.sidebar.markdown(f"**{name_display}** &nbsp; `{tier_badge}`", unsafe_allow_html=True)
    else:
        st.sidebar.markdown(f"**{name_display}**")
    st.sidebar.caption(role_label)

    if st.sidebar.button("Sign Out", use_container_width=True):
        sign_out()
        st.rerun()
