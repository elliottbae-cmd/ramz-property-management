"""Application settings — loads from environment variables or .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

APP_NAME = "Ram-Z Property Management"
APP_VERSION = "1.0.0"
