"""Application-wide constants."""

# ------------------------------------------------------------------
# Role definitions — multi-tenant
# ------------------------------------------------------------------

# PSP (master tenant) roles ordered by privilege
PSP_ROLES = ["admin", "svp", "project_manager", "assistant_project_manager"]

PSP_ROLE_LABELS = {
    "admin": "PSP Admin",
    "svp": "Senior Vice President",
    "project_manager": "Project Manager",
    "assistant_project_manager": "Asst. Project Manager",
}

# Client (tenant) roles ordered by privilege
CLIENT_ROLES = ["coo", "admin", "vp", "doo", "dm", "gm"]

CLIENT_ROLE_LABELS = {
    "coo": "Chief Operating Officer",
    "admin": "Admin",
    "vp": "Vice President",
    "doo": "Director of Operations",
    "dm": "District Manager",
    "gm": "General Manager",
}

# Numeric hierarchy for client roles (higher = more authority)
CLIENT_ROLE_HIERARCHY = {
    "coo": 6,
    "admin": 5,
    "vp": 4,
    "doo": 3,
    "dm": 2,
    "gm": 1,
}

# Combined label lookup (kept for backward-compat convenience)
ROLE_LABELS = {**PSP_ROLE_LABELS, **CLIENT_ROLE_LABELS}

# Flat list of all roles (used by admin pages for dropdowns)
ROLES = list(ROLE_LABELS.keys())

# Approval role levels in order (client-side approval chain)
APPROVAL_LEVELS = ["gm", "dm", "doo", "vp", "coo"]

# ------------------------------------------------------------------
# Ticket statuses
# ------------------------------------------------------------------

TICKET_STATUSES = [
    "submitted",
    "assigned",
    "pending_approval",
    "approved",
    "in_progress",
    "completed",
    "closed",
    "rejected",
]

STATUS_LABELS = {
    "submitted": "Submitted",
    "assigned": "Assigned",
    "pending_approval": "Pending Approval",
    "approved": "Approved",
    "in_progress": "In Progress",
    "completed": "Completed",
    "closed": "Closed",
    "rejected": "Rejected",
}

STATUS_COLORS = {
    "submitted": "#1B3A4B",      # Navy (info)
    "assigned": "#9C27B0",       # Purple
    "pending_approval": "#FF9800",  # Orange (warning)
    "approved": "#4CAF50",       # Green (success)
    "in_progress": "#2196F3",    # Blue
    "completed": "#4CAF50",      # Green
    "closed": "#9E9E9E",         # Gray
    "rejected": "#F44336",       # Red (danger)
}

# ------------------------------------------------------------------
# Urgency levels
# ------------------------------------------------------------------

URGENCY_LEVELS = [
    "Not Urgent",
    "Somewhat Urgent",
    "Extremely Urgent",
    "911 Emergency",
]

URGENCY_COLORS = {
    "Not Urgent": "#4CAF50",
    "Somewhat Urgent": "#FF9800",
    "Extremely Urgent": "#F44336",
    "911 Emergency": "#A6863A",
}

# ------------------------------------------------------------------
# Approval statuses
# ------------------------------------------------------------------

APPROVAL_STATUSES = ["pending", "approved", "rejected"]

APPROVAL_STATUS_LABELS = {
    "pending": "Pending",
    "approved": "Approved",
    "rejected": "Rejected",
}

APPROVAL_STATUS_COLORS = {
    "pending": "#FF9800",
    "approved": "#4CAF50",
    "rejected": "#F44336",
}

# ------------------------------------------------------------------
# Work order statuses
# ------------------------------------------------------------------

WORK_ORDER_STATUSES = ["issued", "in_progress", "completed", "invoiced", "paid"]

# ------------------------------------------------------------------
# Contractor trade types
# ------------------------------------------------------------------

TRADE_TYPES = [
    "BOH (Back of House)",
    "FOH (Front of House)",
    "HVAC",
    "Roof",
    "Parking Lot",
    "Building Exterior",
    "Lighting",
    "Landscaping",
    "Plumbing",
    "Electrical",
    "Signage",
    "Other",
]

# ------------------------------------------------------------------
# US states for store management
# ------------------------------------------------------------------

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]
