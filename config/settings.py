"""Application settings — loads from environment variables, .env file, or Streamlit secrets."""

import os
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available (e.g., Streamlit Cloud)


def _get_secret(key: str, default: str = "") -> str:
    """Get a secret from st.secrets, then env vars, then default."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, default)


# ------------------------------------------------------------------
# Supabase
# ------------------------------------------------------------------
SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = _get_secret("SUPABASE_SERVICE_KEY")  # service_role key for admin operations

# ------------------------------------------------------------------
# App metadata
# ------------------------------------------------------------------
APP_NAME = "Plaza Street Property Management"
APP_VERSION = "2.0.0"
APP_URL = _get_secret("APP_URL", "")  # e.g. https://your-app.streamlit.app

# ------------------------------------------------------------------
# SendGrid
# ------------------------------------------------------------------
SENDGRID_API_KEY = _get_secret("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = _get_secret("SENDGRID_FROM_EMAIL", "noreply@plazastreetpartners.com")
SENDGRID_FROM_NAME = _get_secret("SENDGRID_FROM_NAME", "Plaza Street Partners")

# ------------------------------------------------------------------
# Approval defaults
# ------------------------------------------------------------------
DEFAULT_APPROVAL_THRESHOLD = 500.00  # USD — tickets above this need approval

# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 25
