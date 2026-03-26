"""
Centralized branding — edit this one file to restyle the entire app.
Colors, fonts, logo path, and app name all live here.
"""

import os
import streamlit as st

# ------------------------------------------------------------------
# Brand identity
# ------------------------------------------------------------------
APP_NAME = "Ram-Z Restaurant Group"
APP_TAGLINE = "Property Management & Repair Tracking"

# Path to logo (relative to project root)
LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")

# ------------------------------------------------------------------
# Color palette — Ram-Z Restaurant Group brand colors
# ------------------------------------------------------------------
PRIMARY = "#C4A04D"        # Gold/tan — primary actions, headers (from logo)
PRIMARY_DARK = "#A6863A"   # Dark gold — hover states
PRIMARY_LIGHT = "#F0E6CC"  # Light gold — backgrounds, highlights
SECONDARY = "#1B3A4B"     # Dark navy — text, secondary elements (from logo)
ACCENT = "#C4A04D"        # Gold — accent matches brand
SUCCESS = "#4CAF50"        # Green — success states
WARNING = "#FF9800"        # Orange — warning states
DANGER = "#F44336"         # Red — danger/emergency
INFO = "#1B3A4B"           # Navy — informational (brand-aligned)
BACKGROUND = "#FFFFFF"
SURFACE = "#F7F4EE"        # Warm light — cards, sidebars
TEXT_PRIMARY = "#1B3A4B"   # Navy — primary text
TEXT_SECONDARY = "#6B7B8D" # Muted navy — secondary text

# Urgency colors
URGENCY_COLORS = {
    "Not Urgent": SUCCESS,
    "Somewhat Urgent": WARNING,
    "Extremely Urgent": DANGER,
    "911 Emergency": PRIMARY_DARK,
}

# Status colors
STATUS_COLORS = {
    "submitted": INFO,
    "assigned": "#9C27B0",      # Purple
    "pending_approval": WARNING,
    "approved": SUCCESS,
    "in_progress": "#2196F3",   # Blue
    "completed": "#4CAF50",     # Green
    "closed": "#9E9E9E",        # Gray
    "rejected": DANGER,
}

# ------------------------------------------------------------------
# CSS injection — call this on every page
# ------------------------------------------------------------------

def apply_branding():
    """Inject custom CSS to style the Streamlit app with Ram-Z branding."""
    st.markdown(f"""
    <style>
        /* Mobile-first responsive tweaks */
        .stApp {{
            max-width: 100%;
        }}

        /* Header styling */
        .main-header {{
            background: linear-gradient(135deg, {PRIMARY}, {PRIMARY_DARK});
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
            border-left: 4px solid {PRIMARY};
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

        /* Form inputs - larger for mobile */
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
            background: {SURFACE};
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}
        .metric-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: {PRIMARY};
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


def render_header(title: str = None, subtitle: str = None):
    """Render the branded page header."""
    t = title or APP_NAME
    s = subtitle or APP_TAGLINE
    st.markdown(f"""
    <div class="main-header">
        <h1>{t}</h1>
        <p>{s}</p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_logo():
    """Render the logo in the sidebar."""
    if os.path.exists(LOGO_PATH):
        st.sidebar.image(LOGO_PATH, use_container_width=True)
    else:
        st.sidebar.markdown(f"""
        <div class="sidebar-logo">
            <h2 style="color: {PRIMARY}; margin: 0;">{APP_NAME}</h2>
        </div>
        """, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Return HTML for a colored status badge."""
    color = STATUS_COLORS.get(status, "#9E9E9E")
    label = status.replace("_", " ").title()
    return f'<span class="status-badge" style="background-color: {color};">{label}</span>'


def urgency_badge(urgency: str) -> str:
    """Return HTML for an urgency indicator."""
    color = URGENCY_COLORS.get(urgency, "#9E9E9E")
    return f'<span class="urgency-indicator" style="background-color: {color};"></span>{urgency}'
