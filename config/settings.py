"""Application settings — loads from environment variables or .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# Supabase
# ------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ------------------------------------------------------------------
# App metadata
# ------------------------------------------------------------------
APP_NAME = "Plaza Street Property Management"
APP_VERSION = "2.0.0"

# ------------------------------------------------------------------
# Multi-tenant tiers
# ------------------------------------------------------------------
USER_TIERS = ("psp", "client")

PSP_ROLES = (
    "admin",
    "svp",
    "project_manager",
    "assistant_project_manager",
)

CLIENT_ROLES = (
    "coo",
    "admin",
    "vp",
    "doo",
    "dm",
    "gm",
)

# ------------------------------------------------------------------
# Approval defaults
# ------------------------------------------------------------------
DEFAULT_APPROVAL_THRESHOLD = 500.00  # USD — tickets above this need approval

# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 25
