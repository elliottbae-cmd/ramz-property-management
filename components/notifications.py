"""Email notification helpers — SendGrid integration.

Notification flow (in order):

  1. notify_new_ticket          GM submits       → PSP notified to start warranty check
  2. notify_warranty_complete   Warranty done    → DM notified ticket is in their queue
  3. notify_approval_needed     Bid saved        → DM notified with bid amount to approve
  4. notify_ticket_approved     Final approval   → DM + GM both notified
  5. notify_ticket_rejected     DM rejects       → PSP notified with reason
  6. notify_work_order_issued   WO issued        → GM notified contractor is coming

Falls back to console logging if SENDGRID_API_KEY is not configured.
"""

import traceback
from config.settings import (
    SENDGRID_API_KEY,
    SENDGRID_FROM_EMAIL,
    SENDGRID_FROM_NAME,
    APP_URL,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _send_email(to_emails: list[dict], subject: str, html_body: str) -> bool:
    """Send an HTML email via SendGrid.

    Args:
        to_emails: list of {"email": "...", "name": "..."} dicts
        subject:   email subject line
        html_body: full HTML body string

    Returns True on success, False on failure/misconfiguration.
    """
    if not SENDGRID_API_KEY:
        print(f"[NOTIFICATION - no key] {subject} → {[r['email'] for r in to_emails]}")
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, To

        message = Mail(
            from_email=(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
            subject=subject,
            html_content=html_body,
        )
        for recipient in to_emails:
            message.to = To(email=recipient["email"], name=recipient.get("name", ""))

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        success = response.status_code in (200, 202)
        if not success:
            print(f"[NOTIFICATION] SendGrid returned {response.status_code} for '{subject}'")
        return success
    except Exception:
        print(f"[NOTIFICATION] SendGrid error:\n{traceback.format_exc()}")
        return False


def _base_html(title: str, body_rows: str, cta_url: str = "", cta_label: str = "") -> str:
    """Wrap content in a clean branded HTML email template."""
    cta_block = ""
    if cta_url and cta_label:
        cta_block = f"""
        <tr>
          <td style="padding:24px 32px 0;">
            <a href="{cta_url}"
               style="display:inline-block; background:#C4A04D; color:#fff;
                      text-decoration:none; padding:12px 28px; border-radius:6px;
                      font-weight:bold; font-size:15px;">
              {cta_label}
            </a>
          </td>
        </tr>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0; padding:0; background:#f4f4f4; font-family:Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td align="center" style="padding:32px 16px;">
            <table width="600" cellpadding="0" cellspacing="0"
                   style="background:#fff; border-radius:8px; overflow:hidden;
                          box-shadow:0 2px 8px rgba(0,0,0,.1);">
              <!-- Header -->
              <tr>
                <td style="background:#C4A04D; padding:24px 32px;">
                  <span style="color:#fff; font-size:20px; font-weight:bold;">
                    Plaza Street Partners
                  </span>
                </td>
              </tr>
              <!-- Title -->
              <tr>
                <td style="padding:24px 32px 8px;">
                  <h2 style="margin:0; color:#333; font-size:18px;">{title}</h2>
                </td>
              </tr>
              <!-- Body rows -->
              {body_rows}
              {cta_block}
              <!-- Footer -->
              <tr>
                <td style="padding:32px; color:#888; font-size:12px;
                           border-top:1px solid #eee; margin-top:24px;">
                  This is an automated notification from the Plaza Street Partners
                  Property Management system. Please do not reply to this email.
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>"""


def _detail_row(label: str, value: str) -> str:
    return (
        f'<tr>'
        f'<td style="padding:4px 32px; color:#555; font-size:14px; width:140px; vertical-align:top;">'
        f'<strong>{label}</strong></td>'
        f'<td style="padding:4px 8px; color:#333; font-size:14px;">{value}</td>'
        f'</tr>'
    )


def _intro_row(text: str) -> str:
    return (
        f'<tr><td colspan="2" style="padding:8px 32px 16px; color:#555; font-size:14px;">'
        f'{text}</td></tr>'
    )


def _ticket_core_rows(ticket: dict) -> str:
    """Return detail rows common to every notification — store, equipment, issue, urgency."""
    store = ticket.get("stores") or {}
    equipment = ticket.get("equipment") or {}
    store_num = store.get("store_number", "")
    store_name_str = store.get("name", "")
    store_display = f"{store_num} – {store_name_str}".strip(" –") or "—"
    equip_name = equipment.get("name") or ticket.get("category") or "—"
    description = ticket.get("description") or "—"
    urgency = (ticket.get("urgency") or "").replace("_", " ").title()
    desc_display = description[:200] + ("…" if len(description) > 200 else "")

    return "".join([
        _detail_row("Store", store_display),
        _detail_row("Equipment", equip_name),
        _detail_row("Issue", desc_display),
        _detail_row("Urgency", urgency or "—"),
    ])


def _get_psp_recipients(client_id: str) -> list[dict]:
    """Return PSP project managers for a client, falling back to PSP admins."""
    from database.users import get_users_by_role
    users = get_users_by_role(client_id, "project_manager")
    if not users:
        users = get_users_by_role(client_id, "admin")
    return [
        {"email": u["email"], "name": u.get("full_name", "")}
        for u in users if u.get("email")
    ]


def _get_dm_recipients(client_id: str) -> list[dict]:
    """Return all active DMs for a client."""
    from database.users import get_users_by_role
    users = get_users_by_role(client_id, "dm")
    return [
        {"email": u["email"], "name": u.get("full_name", "")}
        for u in users if u.get("email")
    ]


def _get_store_gm_recipients(client_id: str, store_id: str) -> list[dict]:
    """Return the GM(s) assigned to a specific store."""
    from database.users import get_users_by_role
    users = get_users_by_role(client_id, "gm")
    return [
        {"email": u["email"], "name": u.get("full_name", "")}
        for u in users
        if u.get("email") and u.get("store_id") == store_id
    ]


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------

def notify_new_ticket(ticket: dict, client_id: str) -> bool:
    """Email PSP when a GM submits a new repair request.

    Triggered: pages/submit_request.py after create_ticket succeeds.
    """
    recipients = _get_psp_recipients(client_id)
    if not recipients:
        print(f"[NOTIFICATION] No PSP recipients for new ticket — skipping")
        return False

    ticket_num = ticket.get("ticket_number", "—")
    store = ticket.get("stores") or {}
    store_num = store.get("store_number", "")
    store_name_str = store.get("name", "")
    store_display = f"{store_num} – {store_name_str}".strip(" –") or "—"
    urgency = (ticket.get("urgency") or "").replace("_", " ").title()
    app_link = APP_URL or "#"

    body_rows = "".join([
        _intro_row("A new repair request has been submitted and is awaiting warranty review."),
        _detail_row("Ticket #", ticket_num),
        _ticket_core_rows(ticket),
    ])

    html = _base_html(
        title=f"New Repair Request — Ticket #{ticket_num}",
        body_rows=body_rows,
        cta_url=app_link,
        cta_label="Review Ticket →",
    )

    return _send_email(
        to_emails=recipients,
        subject=f"New Ticket #{ticket_num} — {store_display} ({urgency})",
        html_body=html,
    )


def notify_warranty_complete(ticket: dict, client_id: str, under_warranty: bool = False) -> bool:
    """Email DMs when PSP completes the warranty review — ticket is now in their queue.

    Triggered: pages/warranty_review.py after both under-warranty and not-under-warranty
    completion paths call update_ticket with status='submitted'.
    """
    recipients = _get_dm_recipients(client_id)
    if not recipients:
        print(f"[NOTIFICATION] No DMs found for client {client_id} — skipping warranty email")
        return False

    ticket_num = ticket.get("ticket_number", "—")
    store = ticket.get("stores") or {}
    store_num = store.get("store_number", "")
    store_name_str = store.get("name", "")
    store_display = f"{store_num} – {store_name_str}".strip(" –") or "—"
    app_link = APP_URL or "#"

    warranty_note = (
        "✅ Equipment is <strong>under warranty</strong> — claim instructions have been provided to the store."
        if under_warranty
        else "No active warranty found — PSP will obtain a contractor bid for your review."
    )

    body_rows = "".join([
        _intro_row(
            "PSP has completed the warranty review for the ticket below. "
            "A contractor bid will follow shortly for your approval."
        ),
        _detail_row("Ticket #", ticket_num),
        _ticket_core_rows(ticket),
        _detail_row("Warranty Status", warranty_note),
    ])

    html = _base_html(
        title=f"Warranty Review Complete — Ticket #{ticket_num}",
        body_rows=body_rows,
        cta_url=app_link,
        cta_label="View Ticket →",
    )

    return _send_email(
        to_emails=recipients,
        subject=f"Ticket #{ticket_num} in Your Queue — {store_display}",
        html_body=html,
    )


def notify_approval_needed(ticket: dict, bid_amount: float, client_id: str) -> bool:
    """Email all DMs when a contractor bid needs their approval.

    Triggered: pages/ticket_dashboard.py after initiate_approval_chain succeeds.
    """
    recipients = _get_dm_recipients(client_id)
    if not recipients:
        print(f"[NOTIFICATION] No DMs found for client {client_id} — skipping approval email")
        return False

    ticket_num = ticket.get("ticket_number", "—")
    store = ticket.get("stores") or {}
    store_num = store.get("store_number", "")
    store_name_str = store.get("name", "")
    store_display = f"{store_num} – {store_name_str}".strip(" –") or "—"
    bid_str = f"${bid_amount:,.2f}"
    app_link = APP_URL or "#"

    body_rows = "".join([
        _intro_row("A contractor bid has been submitted and requires your approval."),
        _detail_row("Ticket #", ticket_num),
        _ticket_core_rows(ticket),
        _detail_row("Contractor Bid",
                    f"<strong style='color:#C4A04D; font-size:16px;'>{bid_str}</strong>"),
    ])

    html = _base_html(
        title=f"Approval Required — Ticket #{ticket_num}",
        body_rows=body_rows,
        cta_url=app_link,
        cta_label="Review & Approve →",
    )

    return _send_email(
        to_emails=recipients,
        subject=f"Action Required: Ticket #{ticket_num} — {store_display} ({bid_str} bid)",
        html_body=html,
    )


def notify_ticket_approved(ticket: dict, client_id: str) -> bool:
    """Email DM (confirmation) + GM (their repair is approved) on final approval.

    Triggered: pages/approval_queue.py after check_all_approved returns True.
    """
    store_id = ticket.get("store_id") or ""
    dm_recipients = _get_dm_recipients(client_id)
    gm_recipients = _get_store_gm_recipients(client_id, store_id)
    recipients = dm_recipients + gm_recipients
    if not recipients:
        print(f"[NOTIFICATION] No DM/GM recipients for approved ticket — skipping")
        return False

    ticket_num = ticket.get("ticket_number", "—")
    store = ticket.get("stores") or {}
    store_num = store.get("store_number", "")
    store_name_str = store.get("name", "")
    store_display = f"{store_num} – {store_name_str}".strip(" –") or "—"
    bid = ticket.get("contractor_bid") or 0
    bid_str = f"${bid:,.2f}" if bid else "—"
    app_link = APP_URL or "#"

    body_rows = "".join([
        _intro_row(
            "This repair request has been fully approved. "
            "Plaza Street Partners will issue a work order and coordinate with the contractor."
        ),
        _detail_row("Ticket #", ticket_num),
        _ticket_core_rows(ticket),
        _detail_row("Approved Bid",
                    f"<strong style='color:#27AE60; font-size:16px;'>{bid_str}</strong>"),
    ])

    html = _base_html(
        title=f"Repair Approved — Ticket #{ticket_num}",
        body_rows=body_rows,
        cta_url=app_link,
        cta_label="View Ticket →",
    )

    return _send_email(
        to_emails=recipients,
        subject=f"Approved — Ticket #{ticket_num} ({store_display})",
        html_body=html,
    )


def notify_ticket_rejected(ticket: dict, client_id: str, notes: str = "") -> bool:
    """Email PSP when a DM rejects a ticket so they can follow up.

    Triggered: pages/approval_queue.py after reject_ticket succeeds.
    """
    recipients = _get_psp_recipients(client_id)
    if not recipients:
        print(f"[NOTIFICATION] No PSP recipients for rejected ticket — skipping")
        return False

    ticket_num = ticket.get("ticket_number", "—")
    store = ticket.get("stores") or {}
    store_num = store.get("store_number", "")
    store_name_str = store.get("name", "")
    store_display = f"{store_num} – {store_name_str}".strip(" –") or "—"
    app_link = APP_URL or "#"
    reason_display = notes.strip() if notes and notes.strip() else "No reason provided."

    body_rows = "".join([
        _intro_row("A DM has rejected this ticket. Review the reason below and follow up as needed."),
        _detail_row("Ticket #", ticket_num),
        _ticket_core_rows(ticket),
        _detail_row("Rejection Reason",
                    f"<span style='color:#C0392B;'>{reason_display}</span>"),
    ])

    html = _base_html(
        title=f"Ticket Rejected — #{ticket_num}",
        body_rows=body_rows,
        cta_url=app_link,
        cta_label="View Ticket →",
    )

    return _send_email(
        to_emails=recipients,
        subject=f"Rejected — Ticket #{ticket_num} ({store_display})",
        html_body=html,
    )


def notify_work_order_issued(ticket: dict, client_id: str, contractor_name: str) -> bool:
    """Email the store GM when a work order is issued so they expect the contractor.

    Triggered: pages/ticket_dashboard.py after create_work_order succeeds.
    """
    store_id = ticket.get("store_id") or ""
    recipients = _get_store_gm_recipients(client_id, store_id)
    if not recipients:
        print(f"[NOTIFICATION] No GM found for store {store_id} — skipping work order email")
        return False

    ticket_num = ticket.get("ticket_number", "—")
    store = ticket.get("stores") or {}
    store_num = store.get("store_number", "")
    store_name_str = store.get("name", "")
    store_display = f"{store_num} – {store_name_str}".strip(" –") or "—"
    app_link = APP_URL or "#"

    body_rows = "".join([
        _intro_row(
            "A work order has been issued for your repair request. "
            "The contractor below will be in contact to schedule the repair."
        ),
        _detail_row("Ticket #", ticket_num),
        _ticket_core_rows(ticket),
        _detail_row("Contractor",
                    f"<strong style='color:#333;'>{contractor_name or '—'}</strong>"),
    ])

    html = _base_html(
        title=f"Work Order Issued — Ticket #{ticket_num}",
        body_rows=body_rows,
        cta_url=app_link,
        cta_label="Track Ticket →",
    )

    return _send_email(
        to_emails=recipients,
        subject=f"Work Order Issued — Ticket #{ticket_num} ({store_display})",
        html_body=html,
    )


def notify_contractor_info(ticket_id: str, contractor_name: str, contractor_phone: str):
    """Placeholder — not yet wired up."""
    print(f"[NOTIFICATION] Contractor info: {contractor_name} - {contractor_phone}")
