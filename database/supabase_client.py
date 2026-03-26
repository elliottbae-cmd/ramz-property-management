"""Supabase client initialization and helper functions."""

import streamlit as st
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY


@st.cache_resource
def get_supabase_client() -> Client:
    """Get a cached Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase credentials not configured. Check your .env file.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_authenticated_client() -> Client:
    """Get a Supabase client with the current user's session token."""
    client = get_supabase_client()
    if "access_token" in st.session_state:
        client.postgrest.auth(st.session_state["access_token"])
    return client


# ------------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------------

def sign_up(email: str, password: str, full_name: str):
    """Create a new account and user profile."""
    client = get_supabase_client()
    result = client.auth.sign_up({"email": email, "password": password})
    if result.user:
        # Create profile in users table
        client.table("users").insert({
            "id": result.user.id,
            "email": email,
            "full_name": full_name,
            "role": "staff",
        }).execute()
    return result


def sign_in(email: str, password: str):
    """Sign in and store session in Streamlit session state."""
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    if result.user:
        st.session_state["user_id"] = result.user.id
        st.session_state["access_token"] = result.session.access_token
        # Fetch user profile
        profile = (
            client.table("users")
            .select("*")
            .eq("id", result.user.id)
            .single()
            .execute()
        )
        st.session_state["user_profile"] = profile.data
    return result


def sign_out():
    """Sign out and clear session state."""
    client = get_supabase_client()
    client.auth.sign_out()
    for key in ["user_id", "access_token", "user_profile"]:
        st.session_state.pop(key, None)


def get_current_user():
    """Return the current user profile dict, or None if not logged in."""
    return st.session_state.get("user_profile")


def is_logged_in() -> bool:
    """Check if a user is currently logged in."""
    return "user_id" in st.session_state and "user_profile" in st.session_state


def has_role(*roles: str) -> bool:
    """Check if the current user has one of the specified roles."""
    user = get_current_user()
    if not user:
        return False
    return user.get("role") in roles


# ------------------------------------------------------------------
# Store helpers
# ------------------------------------------------------------------

def get_stores(active_only: bool = True):
    """Fetch all stores."""
    client = get_supabase_client()
    query = client.table("stores").select("*").order("store_number")
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def get_user_stores(user_id: str):
    """Get stores assigned to a user (via user_stores table)."""
    client = get_supabase_client()
    return (
        client.table("user_stores")
        .select("store_id, stores(*)")
        .eq("user_id", user_id)
        .execute()
        .data
    )


# ------------------------------------------------------------------
# Equipment helpers
# ------------------------------------------------------------------

def get_equipment(store_id: str, active_only: bool = True):
    """Fetch equipment for a specific store."""
    client = get_supabase_client()
    query = (
        client.table("equipment")
        .select("*")
        .eq("store_id", store_id)
        .order("name")
    )
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def create_equipment(store_id: str, name: str, serial_number: str, category: str):
    """Create a new equipment record."""
    client = get_supabase_client()
    return (
        client.table("equipment")
        .insert({
            "store_id": store_id,
            "name": name,
            "serial_number": serial_number or None,
            "category": category,
        })
        .execute()
        .data
    )


# ------------------------------------------------------------------
# Form config helpers
# ------------------------------------------------------------------

def get_form_categories(active_only: bool = True):
    """Fetch form categories (admin-configurable)."""
    client = get_supabase_client()
    query = client.table("form_categories").select("*").order("display_order")
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def get_form_urgency_levels(active_only: bool = True):
    """Fetch urgency levels (admin-configurable)."""
    client = get_supabase_client()
    query = client.table("form_urgency_levels").select("*").order("display_order")
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def get_form_fields(category_id: str = None, active_only: bool = True):
    """Fetch custom form fields, optionally filtered by category."""
    client = get_supabase_client()
    query = client.table("form_fields").select("*").order("display_order")
    if active_only:
        query = query.eq("is_active", True)
    if category_id:
        query = query.or_(f"category_filter.is.null,category_filter.eq.{category_id}")
    return query.execute().data


# ------------------------------------------------------------------
# Ticket helpers
# ------------------------------------------------------------------

def create_ticket(data: dict):
    """Create a new ticket."""
    client = get_supabase_client()
    return client.table("tickets").insert(data).execute().data


def get_tickets(filters: dict = None):
    """Fetch tickets with optional filters."""
    client = get_supabase_client()
    query = (
        client.table("tickets")
        .select("*, stores(store_number, name), users!tickets_submitted_by_fkey(full_name)")
        .order("created_at", desc=True)
    )
    if filters:
        if filters.get("store_id"):
            query = query.eq("store_id", filters["store_id"])
        if filters.get("status"):
            query = query.eq("status", filters["status"])
        if filters.get("urgency"):
            query = query.eq("urgency", filters["urgency"])
        if filters.get("category"):
            query = query.eq("category", filters["category"])
        if filters.get("submitted_by"):
            query = query.eq("submitted_by", filters["submitted_by"])
        if filters.get("assigned_to"):
            query = query.eq("assigned_to", filters["assigned_to"])
    return query.execute().data


def get_ticket_by_id(ticket_id: str):
    """Fetch a single ticket with all related data."""
    client = get_supabase_client()
    ticket = (
        client.table("tickets")
        .select(
            "*, stores(store_number, name), "
            "users!tickets_submitted_by_fkey(full_name, email), "
            "equipment(name, serial_number)"
        )
        .eq("id", ticket_id)
        .single()
        .execute()
        .data
    )
    return ticket


def update_ticket(ticket_id: str, data: dict):
    """Update a ticket."""
    client = get_supabase_client()
    return (
        client.table("tickets")
        .update(data)
        .eq("id", ticket_id)
        .execute()
        .data
    )


def get_ticket_photos(ticket_id: str):
    """Get photos for a ticket."""
    client = get_supabase_client()
    return (
        client.table("ticket_photos")
        .select("*")
        .eq("ticket_id", ticket_id)
        .order("uploaded_at")
        .execute()
        .data
    )


def add_ticket_photo(ticket_id: str, photo_url: str):
    """Add a photo to a ticket."""
    client = get_supabase_client()
    return (
        client.table("ticket_photos")
        .insert({"ticket_id": ticket_id, "photo_url": photo_url})
        .execute()
        .data
    )


def get_ticket_comments(ticket_id: str):
    """Get comments for a ticket."""
    client = get_supabase_client()
    return (
        client.table("ticket_comments")
        .select("*, users(full_name)")
        .eq("ticket_id", ticket_id)
        .order("created_at")
        .execute()
        .data
    )


def add_ticket_comment(ticket_id: str, user_id: str, comment: str):
    """Add a comment to a ticket."""
    client = get_supabase_client()
    return (
        client.table("ticket_comments")
        .insert({"ticket_id": ticket_id, "user_id": user_id, "comment": comment})
        .execute()
        .data
    )


# ------------------------------------------------------------------
# Approval helpers
# ------------------------------------------------------------------

def get_approvals_for_ticket(ticket_id: str):
    """Get all approvals for a ticket."""
    client = get_supabase_client()
    return (
        client.table("approvals")
        .select("*, users(full_name, role)")
        .eq("ticket_id", ticket_id)
        .order("created_at")
        .execute()
        .data
    )


def create_approval_chain(ticket_id: str):
    """Create the three-tier approval chain for a ticket."""
    client = get_supabase_client()
    levels = ["gm", "dm", "director"]
    for level in levels:
        client.table("approvals").insert({
            "ticket_id": ticket_id,
            "role_level": level,
            "status": "pending",
        }).execute()


def update_approval(approval_id: str, status: str, approver_id: str, notes: str = None):
    """Update an approval decision."""
    client = get_supabase_client()
    data = {
        "status": status,
        "approver_id": approver_id,
        "decided_at": "now()",
    }
    if notes:
        data["notes"] = notes
    return (
        client.table("approvals")
        .update(data)
        .eq("id", approval_id)
        .execute()
        .data
    )


def get_pending_approvals_for_role(role_level: str):
    """Get pending approvals for a specific role level."""
    client = get_supabase_client()
    return (
        client.table("approvals")
        .select("*, tickets(*, stores(store_number, name))")
        .eq("role_level", role_level)
        .eq("status", "pending")
        .order("created_at")
        .execute()
        .data
    )


# ------------------------------------------------------------------
# Contractor helpers
# ------------------------------------------------------------------

def get_contractors(active_only: bool = True, trade: str = None, region: str = None):
    """Fetch contractors with optional filters."""
    client = get_supabase_client()
    query = client.table("contractors").select("*").order("is_preferred", desc=True).order("avg_rating", desc=True)
    if active_only:
        query = query.eq("is_active", True)
    if trade:
        query = query.contains("trades", [trade])
    if region:
        query = query.contains("service_regions", [region])
    return query.execute().data


def create_contractor(data: dict):
    """Create a new contractor."""
    client = get_supabase_client()
    return client.table("contractors").insert(data).execute().data


def update_contractor(contractor_id: str, data: dict):
    """Update a contractor."""
    client = get_supabase_client()
    return (
        client.table("contractors")
        .update(data)
        .eq("id", contractor_id)
        .execute()
        .data
    )


def get_contractor_reviews(contractor_id: str):
    """Get reviews for a contractor."""
    client = get_supabase_client()
    return (
        client.table("contractor_reviews")
        .select("*, users(full_name)")
        .eq("contractor_id", contractor_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )


def add_contractor_review(data: dict):
    """Add a review for a contractor and update avg rating."""
    client = get_supabase_client()
    result = client.table("contractor_reviews").insert(data).execute().data
    # Recalculate average rating
    reviews = (
        client.table("contractor_reviews")
        .select("rating")
        .eq("contractor_id", data["contractor_id"])
        .execute()
        .data
    )
    if reviews:
        avg = sum(r["rating"] for r in reviews) / len(reviews)
        client.table("contractors").update({"avg_rating": round(avg, 2)}).eq(
            "id", data["contractor_id"]
        ).execute()
    return result


# ------------------------------------------------------------------
# Work order helpers
# ------------------------------------------------------------------

def create_work_order(data: dict):
    """Create a work order."""
    client = get_supabase_client()
    return client.table("work_orders").insert(data).execute().data


def get_work_orders(ticket_id: str = None):
    """Get work orders, optionally for a specific ticket."""
    client = get_supabase_client()
    query = (
        client.table("work_orders")
        .select("*, contractors(company_name, phone, email), tickets(ticket_number)")
        .order("issued_at", desc=True)
    )
    if ticket_id:
        query = query.eq("ticket_id", ticket_id)
    return query.execute().data


def update_work_order(work_order_id: str, data: dict):
    """Update a work order."""
    client = get_supabase_client()
    return (
        client.table("work_orders")
        .update(data)
        .eq("id", work_order_id)
        .execute()
        .data
    )


# ------------------------------------------------------------------
# User management helpers
# ------------------------------------------------------------------

def get_users(role: str = None, active_only: bool = True):
    """Fetch users with optional role filter."""
    client = get_supabase_client()
    query = client.table("users").select("*, stores(store_number, name)").order("full_name")
    if role:
        query = query.eq("role", role)
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def update_user(user_id: str, data: dict):
    """Update a user profile."""
    client = get_supabase_client()
    return (
        client.table("users")
        .update(data)
        .eq("id", user_id)
        .execute()
        .data
    )


def get_approval_settings():
    """Get current approval settings."""
    client = get_supabase_client()
    return (
        client.table("approval_settings")
        .select("*")
        .order("role")
        .execute()
        .data
    )


def update_approval_settings(setting_id: str, data: dict):
    """Update approval settings."""
    client = get_supabase_client()
    return (
        client.table("approval_settings")
        .update(data)
        .eq("id", setting_id)
        .execute()
        .data
    )


# ------------------------------------------------------------------
# Photo upload helpers
# ------------------------------------------------------------------

def upload_photo(file_bytes: bytes, file_name: str, ticket_id: str) -> str:
    """Upload a photo to Supabase Storage and return the public URL."""
    client = get_supabase_client()
    path = f"tickets/{ticket_id}/{file_name}"
    client.storage.from_("ticket-photos").upload(path, file_bytes)
    url = client.storage.from_("ticket-photos").get_public_url(path)
    return url


# ------------------------------------------------------------------
# Reporting helpers
# ------------------------------------------------------------------

def get_store_spend_summary(store_id: str = None):
    """Get ticket spend summary by store."""
    client = get_supabase_client()
    query = (
        client.table("tickets")
        .select("store_id, stores(store_number, name), actual_cost, estimated_cost, created_at")
        .in_("status", ["completed", "closed"])
    )
    if store_id:
        query = query.eq("store_id", store_id)
    return query.execute().data


def get_equipment_history(equipment_id: str):
    """Get full repair history for a piece of equipment."""
    client = get_supabase_client()
    return (
        client.table("tickets")
        .select("*, work_orders(amount, status, contractors(company_name))")
        .eq("equipment_id", equipment_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )


def get_property_team_workload():
    """Get open ticket counts per property team member (for round-robin)."""
    client = get_supabase_client()
    team = (
        client.table("users")
        .select("id, full_name")
        .eq("role", "property_manager")
        .eq("is_active", True)
        .execute()
        .data
    )
    workload = []
    for member in team:
        count_result = (
            client.table("tickets")
            .select("id", count="exact")
            .eq("assigned_to", member["id"])
            .in_("status", ["submitted", "assigned", "pending_approval", "approved", "in_progress"])
            .execute()
        )
        workload.append({
            "id": member["id"],
            "full_name": member["full_name"],
            "open_tickets": count_result.count or 0,
        })
    workload.sort(key=lambda x: x["open_tickets"])
    return workload
