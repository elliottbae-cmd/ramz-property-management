"""Email notification helpers.

This module provides a notification framework. Currently logs to console.
To enable email: add SendGrid credentials and uncomment the send_email function.
"""

import streamlit as st


def notify_new_ticket(ticket: dict, store_name: str):
    """Notify property managers about a new ticket."""
    _log_notification(
        f"New ticket #{ticket.get('ticket_number')} at {store_name}: "
        f"{ticket.get('category')} - {ticket.get('urgency')}"
    )


def notify_ticket_assigned(ticket_id: str, assignee_name: str):
    """Notify when a ticket is assigned."""
    _log_notification(f"Ticket assigned to {assignee_name}")


def notify_approval_needed(ticket_id: str, role_level: str):
    """Notify approvers that their approval is needed."""
    _log_notification(f"Approval needed at {role_level.upper()} level for ticket")


def notify_ticket_approved(ticket_id: str):
    """Notify when a ticket is fully approved."""
    _log_notification(f"Ticket fully approved — work order can be issued")


def notify_contractor_info(ticket_id: str, contractor_name: str, contractor_phone: str):
    """Send contractor contact info to the ticket submitter (for sub-$1K repairs)."""
    _log_notification(
        f"Contractor info sent: {contractor_name} - {contractor_phone}"
    )


def _log_notification(message: str):
    """Log notification (placeholder for email integration)."""
    # TODO: Replace with SendGrid email when ready
    # For now, notifications are displayed in the app
    print(f"[NOTIFICATION] {message}")
