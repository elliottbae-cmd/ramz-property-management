"""Role-based access control helpers for multi-tenant permission checks."""

import streamlit as st
from database.supabase_client import get_current_user, is_psp_user as _is_psp_user


# ------------------------------------------------------------------
# Identity helpers
# ------------------------------------------------------------------

def is_psp_user() -> bool:
    """Check if the current user belongs to the PSP (master) tier."""
    return _is_psp_user()


def get_user_tier() -> str:
    """Return 'psp' or 'client' for the current user."""
    user = get_current_user()
    if not user:
        return ""
    return user.get("user_tier", "")


def get_user_role() -> str:
    """Return the granular role for the current user.

    PSP users  -> psp_role   (admin, svp, project_manager, assistant_project_manager)
    Client users -> client_role (coo, admin, vp, doo, dm, gm)
    """
    user = get_current_user()
    if not user:
        return ""
    tier = user.get("user_tier", "")
    if tier == "psp":
        return user.get("psp_role", "")
    if tier == "client":
        return user.get("client_role", "")
    return ""


# ------------------------------------------------------------------
# Permission checks
# ------------------------------------------------------------------

def can_submit_tickets() -> bool:
    """All authenticated users can submit tickets."""
    return get_current_user() is not None


def can_approve() -> bool:
    """Check if the user can approve tickets.

    Client: gm, dm, vp, doo, coo, admin
    PSP: all roles
    """
    if is_psp_user():
        return True
    role = get_user_role()
    return role in ("gm", "dm", "vp", "doo", "coo", "admin")


def can_manage_tickets() -> bool:
    """Check if the user can manage / triage tickets.

    Client: admin, coo, vp, doo
    PSP: all roles
    """
    if is_psp_user():
        return True
    role = get_user_role()
    return role in ("admin", "coo", "vp", "doo")


def can_manage_contractors() -> bool:
    """Only PSP users can manage the contractor directory."""
    return is_psp_user()


def can_manage_users() -> bool:
    """Check if the user can manage user accounts.

    PSP: admin, svp
    Client: admin, coo
    """
    user = get_current_user()
    if not user:
        return False
    tier = user.get("user_tier", "")
    if tier == "psp":
        return user.get("psp_role") in ("admin", "svp")
    if tier == "client":
        return user.get("client_role") in ("admin", "coo")
    return False


def can_view_reports() -> bool:
    """Check if the user can view reports and analytics.

    Client: dm and above (dm, doo, vp, coo, admin)
    PSP: all roles
    """
    if is_psp_user():
        return True
    role = get_user_role()
    return role in ("dm", "doo", "vp", "coo", "admin")


def can_access_psp_admin() -> bool:
    """Only PSP users can access the PSP admin panel."""
    return is_psp_user()


# ------------------------------------------------------------------
# Gate / decorator-style helper
# ------------------------------------------------------------------

def require_permission(permission_func, redirect_message: str = "Access denied"):
    """Gate that checks a permission function and stops rendering if denied.

    Usage:
        require_permission(can_manage_tickets, "You do not have access to this page.")
    """
    if not permission_func():
        st.error(redirect_message)
        st.stop()
