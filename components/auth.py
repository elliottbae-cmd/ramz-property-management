"""Authentication component — login/signup/logout UI."""

import streamlit as st
from database.supabase_client import sign_in, sign_up, sign_out, is_logged_in, get_current_user
from theme.branding import apply_branding, render_header, PRIMARY, PRIMARY_DARK
from utils.constants import ROLE_LABELS


def require_auth():
    """Gate that requires authentication. Shows login if not authenticated."""
    if not is_logged_in():
        render_login_page()
        st.stop()


def require_role(*roles):
    """Gate that requires specific role(s). Shows error if unauthorized."""
    require_auth()
    user = get_current_user()
    if user and user.get("role") not in roles:
        st.error(f"Access denied. This page requires one of: {', '.join(ROLE_LABELS.get(r, r) for r in roles)}")
        st.stop()


def render_login_page():
    """Render the login/signup page."""
    apply_branding()

    st.markdown(f"""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 style="color: {PRIMARY}; font-size: 2rem;">Ram-Z Property Management</h1>
        <p style="color: #757575; font-size: 1rem;">Repair Request & Maintenance Tracking</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="your.email@ramz.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    try:
                        result = sign_in(email, password)
                        if result.user:
                            st.success("Signed in successfully!")
                            st.rerun()
                        else:
                            st.error("Invalid email or password.")
                    except Exception as e:
                        st.error(f"Login failed: {str(e)}")

    with tab_signup:
        with st.form("signup_form"):
            new_name = st.text_input("Full Name", placeholder="John Smith")
            new_email = st.text_input("Email", placeholder="your.email@ramz.com", key="signup_email")
            new_password = st.text_input("Password", type="password", key="signup_password",
                                         help="Minimum 6 characters")
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
                        result = sign_up(new_email, new_password, new_name)
                        if result.user:
                            st.success("Account created! Please sign in.")
                        else:
                            st.error("Could not create account. Email may already be in use.")
                    except Exception as e:
                        st.error(f"Sign up failed: {str(e)}")

    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; color: #9E9E9E; font-size: 0.8rem;">
        Contact your administrator if you need an account or role change.
    </div>
    """, unsafe_allow_html=True)


def render_user_sidebar():
    """Render user info and logout in the sidebar."""
    user = get_current_user()
    if not user:
        return

    role_label = ROLE_LABELS.get(user.get("role", ""), user.get("role", ""))

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{user.get('full_name', 'User')}**")
    st.sidebar.caption(f"{role_label}")

    if st.sidebar.button("Sign Out", use_container_width=True):
        sign_out()
        st.rerun()
