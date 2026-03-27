"""Supabase client initialization and auth helpers for multi-tenant app."""

import streamlit as st
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY


# ------------------------------------------------------------------
# Client factory
# ------------------------------------------------------------------

@st.cache_resource
def get_supabase_client() -> Client:
    """Get a cached Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase credentials not configured. Check your .env file.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_client() -> Client:
    """Primary accessor used by all database modules.

    Returns the Supabase client with the current user's auth token
    attached when available, falling back to the anon client otherwise.
    """
    sb = get_supabase_client()
    token = st.session_state.get("access_token")
    if token:
        sb.postgrest.auth(token)
    return sb


# Alias kept for backward compatibility
get_authenticated_client = get_client


# ------------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------------

def sign_up(email: str, password: str, full_name: str, user_tier: str = "client",
            client_id: str = None, client_role: str = None, psp_role: str = None):
    """Create a new account and user profile.

    Parameters
    ----------
    user_tier : str
        'psp' (master) or 'client' (tenant).
    client_id : str | None
        Required when user_tier == 'client'.
    client_role : str | None
        Role within the client org (coo, admin, vp, doo, dm, gm).
    psp_role : str | None
        Role within PSP (admin, svp, project_manager, assistant_project_manager).
    """
    sb = get_supabase_client()
    result = sb.auth.sign_up({"email": email, "password": password})

    # Profile creation is handled by admin — sign_up only creates the auth account.
    # If tier/role info is provided (admin-created accounts), insert the profile now.
    if result.user and result.session and user_tier and (psp_role or client_role):
        sb.postgrest.auth(result.session.access_token)
        profile = {
            "id": result.user.id,
            "email": email,
            "full_name": full_name,
            "user_tier": user_tier,
        }
        if user_tier == "psp" and psp_role:
            profile["psp_role"] = psp_role
        if user_tier == "client" and client_id and client_role:
            profile["client_id"] = client_id
            profile["client_role"] = client_role
        sb.table("users").insert(profile).execute()
    return result


def try_restore_session() -> bool:
    """Attempt to restore a session from a saved refresh token.

    Returns True if session was restored, False otherwise.
    """
    import json, os
    token_file = os.path.join(os.path.dirname(__file__), "..", ".session_token")
    token_file = os.path.normpath(token_file)

    if not os.path.exists(token_file):
        return False

    try:
        with open(token_file, "r") as f:
            data = json.load(f)

        sb = get_supabase_client()
        result = sb.auth.refresh_session(data.get("refresh_token"))

        if result.user and result.session:
            st.session_state["user_id"] = result.user.id
            st.session_state["access_token"] = result.session.access_token
            sb.postgrest.auth(result.session.access_token)

            # Save updated refresh token
            _save_refresh_token(result.session.refresh_token)

            # Load profile
            try:
                profile = (
                    sb.table("users")
                    .select("*")
                    .eq("id", result.user.id)
                    .single()
                    .execute()
                )
                st.session_state["user_profile"] = profile.data
                _hydrate_client_context(profile.data)
                return True
            except Exception:
                return False
        return False
    except Exception:
        # Token expired or invalid — delete it
        try:
            os.remove(token_file)
        except Exception:
            pass
        return False


def _save_refresh_token(refresh_token: str):
    """Save refresh token to a local file for session persistence."""
    import json, os
    token_file = os.path.join(os.path.dirname(__file__), "..", ".session_token")
    token_file = os.path.normpath(token_file)
    with open(token_file, "w") as f:
        json.dump({"refresh_token": refresh_token}, f)


def _clear_refresh_token():
    """Remove saved refresh token."""
    import os
    token_file = os.path.join(os.path.dirname(__file__), "..", ".session_token")
    token_file = os.path.normpath(token_file)
    try:
        os.remove(token_file)
    except Exception:
        pass


def sign_in(email: str, password: str, remember: bool = False):
    """Sign in and hydrate session state with user profile."""
    sb = get_supabase_client()
    result = sb.auth.sign_in_with_password({"email": email, "password": password})

    if result.user:
        st.session_state["user_id"] = result.user.id
        st.session_state["access_token"] = result.session.access_token
        sb.postgrest.auth(result.session.access_token)

        # Save refresh token if "Remember me" is checked
        if remember and result.session:
            _save_refresh_token(result.session.refresh_token)

        try:
            profile = (
                sb.table("users")
                .select("*")
                .eq("id", result.user.id)
                .single()
                .execute()
            )
            st.session_state["user_profile"] = profile.data
        except Exception:
            # No profile exists yet — admin needs to set up this user
            st.session_state["user_profile"] = {
                "id": result.user.id,
                "email": result.user.email,
                "full_name": result.user.email.split("@")[0],
                "user_tier": "pending",
            }
            return result

        # Hydrate tenant context
        _hydrate_client_context(st.session_state["user_profile"])
    return result


def _hydrate_client_context(profile: dict):
    """Set effective_client_id in session state based on user tier."""
    if profile.get("user_tier") == "client":
        st.session_state["effective_client_id"] = profile.get("client_id")
    elif profile.get("user_tier") == "psp":
        # PSP users start with no active client; they pick one via tenant.switch_client()
        if "effective_client_id" not in st.session_state:
            st.session_state["effective_client_id"] = None


def sign_out():
    """Sign out and clear all session state keys."""
    _clear_refresh_token()
    sb = get_supabase_client()
    sb.auth.sign_out()
    keys_to_clear = [
        "user_id", "access_token", "user_profile",
        "effective_client_id", "current_client",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)


def get_current_user() -> dict | None:
    """Return the current user profile dict, or None if not logged in."""
    return st.session_state.get("user_profile")


def is_logged_in() -> bool:
    """Check if a user is currently logged in."""
    return "user_id" in st.session_state and "user_profile" in st.session_state


def has_role(*roles: str) -> bool:
    """Check if the current user has one of the specified roles.

    Works for both user_tier-level checks ('psp', 'client') and
    granular role checks ('admin', 'svp', 'gm', etc.).
    """
    user = get_current_user()
    if not user:
        return False
    tier = user.get("user_tier")
    if tier in roles:
        return True
    if tier == "psp":
        return user.get("psp_role") in roles
    if tier == "client":
        return user.get("client_role") in roles
    return False


def is_psp_user() -> bool:
    """Convenience: True when the current user is a PSP-tier user."""
    user = get_current_user()
    return bool(user and user.get("user_tier") == "psp")


# ------------------------------------------------------------------
# Photo upload helpers
# ------------------------------------------------------------------

def upload_photo(file_bytes: bytes, file_name: str, ticket_id: str) -> str:
    """Upload a photo to Supabase Storage and return the public URL."""
    sb = get_supabase_client()
    path = f"tickets/{ticket_id}/{file_name}"
    sb.storage.from_("ticket-photos").upload(path, file_bytes)
    url = sb.storage.from_("ticket-photos").get_public_url(path)
    return url
