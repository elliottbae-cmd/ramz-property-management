"""
Centralized branding — dynamically themed from the current client record.
Falls back to PSP defaults when no client is selected.
"""

import os
import streamlit as st
from utils.constants import STATUS_COLORS, URGENCY_COLORS

# ------------------------------------------------------------------
# PSP default brand identity (fallback)
# ------------------------------------------------------------------
_PSP_DEFAULTS = {
    "name": "Plaza Street Partners",
    "primary_color": "#C4A04D",
    "secondary_color": "#1B3A4B",
    "accent_color": "#C4A04D",
    "logo_url": None,
    "tagline": "Property Management & Repair Tracking",
}

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")


# ------------------------------------------------------------------
# Brand accessor
# ------------------------------------------------------------------

def get_brand() -> dict:
    """Return the active brand settings dict.

    Reads from st.session_state['current_client']; falls back to PSP
    defaults if no client is loaded or if the client record is missing
    color fields.
    """
    client = st.session_state.get("current_client") or {}
    return {
        "name": client.get("name") or _PSP_DEFAULTS["name"],
        "primary_color": client.get("primary_color") or _PSP_DEFAULTS["primary_color"],
        "secondary_color": client.get("secondary_color") or _PSP_DEFAULTS["secondary_color"],
        "accent_color": client.get("accent_color") or _PSP_DEFAULTS["accent_color"],
        "logo_url": client.get("logo_url") or _PSP_DEFAULTS["logo_url"],
        "tagline": client.get("tagline") or _PSP_DEFAULTS["tagline"],
    }


# ------------------------------------------------------------------
# Derived color helpers
# ------------------------------------------------------------------

def _darken(hex_color: str, factor: float = 0.15) -> str:
    """Darken a hex color by a factor (0-1)."""
    try:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def _lighten(hex_color: str, factor: float = 0.7) -> str:
    """Lighten a hex color by mixing with white."""
    try:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


# ------------------------------------------------------------------
# Convenience color accessors (used by other modules)
# ------------------------------------------------------------------

@property
def PRIMARY():
    return get_brand()["primary_color"]


@property
def SECONDARY():
    return get_brand()["secondary_color"]


# Provide module-level constants for backward compat import
# These are evaluated once at import time with PSP defaults
PRIMARY = _PSP_DEFAULTS["primary_color"]
PRIMARY_DARK = _darken(_PSP_DEFAULTS["primary_color"])
PRIMARY_LIGHT = _lighten(_PSP_DEFAULTS["primary_color"])
SECONDARY = _PSP_DEFAULTS["secondary_color"]
ACCENT = _PSP_DEFAULTS["accent_color"]
SUCCESS = "#4CAF50"
WARNING = "#FF9800"
DANGER = "#F44336"
INFO = _PSP_DEFAULTS["secondary_color"]
BACKGROUND = "#FFFFFF"
SURFACE = "#F7F4EE"
TEXT_PRIMARY = _PSP_DEFAULTS["secondary_color"]
TEXT_SECONDARY = "#6B7B8D"


# ------------------------------------------------------------------
# CSS injection — call on every page
# ------------------------------------------------------------------

def apply_branding():
    """Inject custom CSS using dynamic colors from the current client."""
    brand = get_brand()
    primary = brand["primary_color"]
    primary_dark = _darken(primary)
    primary_light = _lighten(primary)
    secondary = brand["secondary_color"]
    surface = SURFACE

    st.markdown(f"""
    <style>
        /* Mobile-first responsive tweaks */
        .stApp {{
            max-width: 100%;
        }}

        /* Header styling */
        .main-header {{
            background: linear-gradient(135deg, {primary}, {primary_dark});
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            text-align: center;
        }}
        .main-header h1 {{
            margin: 0;
            font-size: 1.5rem;
            font-weight: 700;
        }}
        .main-header p {{
            margin: 0.25rem 0 0 0;
            font-size: 0.85rem;
            opacity: 0.9;
        }}

        /* Status badges */
        .status-badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            color: white;
        }}

        /* Urgency indicators */
        .urgency-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }}

        /* Card styling */
        .ticket-card {{
            background: white;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            border-left: 4px solid {primary};
        }}
        .ticket-card:hover {{
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        /* Mobile-friendly buttons */
        .stButton > button {{
            width: 100%;
            border-radius: 8px;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
        }}

        /* Form inputs — larger for mobile */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div > div {{
            font-size: 16px !important;  /* Prevents iOS zoom on focus */
        }}

        /* Sidebar logo area */
        .sidebar-logo {{
            text-align: center;
            padding: 1rem 0;
        }}
        .sidebar-logo img {{
            max-width: 150px;
            margin-bottom: 0.5rem;
        }}

        /* Metric cards */
        .metric-card {{
            background: {surface};
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}
        .metric-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: {primary};
        }}
        .metric-card .label {{
            font-size: 0.85rem;
            color: {TEXT_SECONDARY};
        }}

        /* Hide Streamlit default elements for cleaner look */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Header / logo / footer
# ------------------------------------------------------------------

def render_header(title: str = None, subtitle: str = None):
    """Render the branded page header."""
    brand = get_brand()
    t = title or brand["name"]
    s = subtitle or brand["tagline"]
    st.markdown(f"""
    <div class="main-header">
        <h1>{t}</h1>
        <p>{s}</p>
    </div>
    """, unsafe_allow_html=True)


def render_logo():
    """Render the client logo in the sidebar, or fall back to PSP default."""
    brand = get_brand()
    logo_url = brand.get("logo_url")

    if logo_url:
        st.sidebar.image(logo_url, use_container_width=True)
    elif os.path.exists(_LOGO_PATH):
        st.sidebar.image(_LOGO_PATH, use_container_width=True)
    else:
        primary = brand["primary_color"]
        st.sidebar.markdown(f"""
        <div class="sidebar-logo">
            <h2 style="color: {primary}; margin: 0;">{brand['name']}</h2>
        </div>
        """, unsafe_allow_html=True)


# Backward-compat alias
render_sidebar_logo = render_logo


def render_footer():
    """Render footer — always shows PSP credit."""
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<div style='text-align:center; font-size:0.75rem; color:#9E9E9E;'>"
        "Powered by Plaza Street Partners, LLC</div>",
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------
# Badge helpers
# ------------------------------------------------------------------

def status_badge(status: str) -> str:
    """Return HTML for a colored status badge."""
    color = STATUS_COLORS.get(status, "#9E9E9E")
    label = status.replace("_", " ").title()
    return f'<span class="status-badge" style="background-color: {color};">{label}</span>'


def urgency_badge(urgency: str) -> str:
    """Return HTML for an urgency indicator."""
    color = URGENCY_COLORS.get(urgency, "#9E9E9E")
    return f'<span class="urgency-indicator" style="background-color: {color};"></span>{urgency}'
