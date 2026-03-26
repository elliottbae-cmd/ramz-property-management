"""Application-wide constants."""

# User roles (ordered by privilege level)
ROLES = ["admin", "director", "dm", "gm", "property_manager", "staff"]

ROLE_LABELS = {
    "admin": "Admin",
    "director": "Director",
    "dm": "District Manager (DM)",
    "gm": "General Manager (GM)",
    "property_manager": "Property Manager",
    "staff": "Staff",
}

# Approval role levels in order
APPROVAL_LEVELS = ["gm", "dm", "director"]

# Ticket statuses
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

# Work order statuses
WORK_ORDER_STATUSES = ["issued", "in_progress", "completed", "invoiced", "paid"]

# Contractor trade types
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

# US states for store management
US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]
