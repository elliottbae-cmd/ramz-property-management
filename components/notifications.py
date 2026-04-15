"""Email notification helpers — SendGrid integration.

Each public function handles one notification event.
Falls back to console logging if SendGrid is not configured.
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
                <td style="padding:32px; color:#888; font-size:12px; border-top:1px solid #eee; margin-top:24px;">
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
        f'<td style="padding:4px 32px; color:#555; font-size:14px; width:140px;">'
        f'<strong>{label}</strong></td>'
        f'<td style="padding:4px 8px; color:#333; font-size:14px;">{value}</td>'
        f'</tr>'
    )


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------

def notify_approval_needed(ticket: dict, bid_amount: float, client_id: str) -> bool:
    """Email all DMs for the client when a contractor bid needs their approval.

    Args:
        ticket:     full ticket dict (from get_ticket — includes stores/equipment joins)
        bid_amount: the contractor bid amount in dollars
        client_id:  UUID of the client org (used to look up DM users)

    Returns True if at least one email was sent successfully.
    """
    from database.users import get_users_by_role

    dms = get_users_by_role(client_id, "dm")
    if not dms:
        print(f"[NOTIFICATION] No DMs found for client {client_id} — skipping approval email")
        return False

    recipients = [
        {"email": u["email"], "name": u.get("full_name", "")}
        for u in dms
        if u.get("email")
    ]
    if not recipients:
        return False

    store = ticket.get("stores") or {}
    equipment = ticket.get("equipment") or {}
    ticket_num = ticket.get("ticket_number", "—")
    store_name = f"{store.get('store_number', '')} – {store.get('name', '')}".strip(" –")
    equip_name = equipment.get("name") or ticket.get("category") or "—"
    description = ticket.get("description") or "—"
    urgency = (ticket.get("urgency") or "").replace("_", " ").title()
    bid_str = f"${bid_amount:,.2f}"

    app_link = APP_URL or "#"

    body_rows = "".join([
        '<tr><td colspan="2" style="padding:8px 32px 16px; color:#555; font-size:14px;">'
        'A contractor bid has been submitted and requires your approval.</td></tr>',
        _detail_row("Ticket #", ticket_num),
        _detail_row("Store", store_name or "—"),
        _detail_row("Equipment", equip_name),
        _detail_row("Issue", description[:200] + ("…" if len(description) > 200 else "")),
        _detail_row("Urgency", urgency or "—"),
        _detail_row("Contractor Bid", f"<strong style='color:#C4A04D; font-size:16px;'>{bid_str}</strong>"),
    ])

    html = _base_html(
        title=f"Approval Required — Ticket #{ticket_num}",
        body_rows=body_rows,
        cta_url=app_link,
        cta_label="Review in App →",
    )

    return _send_email(
        to_emails=recipients,
        subject=f"Action Required: Ticket #{ticket_num} — {store_name} ({bid_str} bid)",
        html_body=html,
    )


def notify_ticket_approved(ticket: dict, client_id: str) -> bool:
    """Email PSP staff when all approval steps are complete and a work order can be issued.

    Args:
        ticket:    full ticket dict
        client_id: UUID of the client org
    """
    from database.users import get_users_by_role

    # Notify PSP project managers assigned to this client
    psp_users = get_users_by_role(client_id, "project_manager")
    if not psp_users:
        # Fall back to any PSP admin
        psp_users = get_users_by_role(client_id, "admin")

    recipients = [
        {"email": u["email"], "name": u.get("full_name", "")}
        for u in psp_users
        if u.get("email")
    ]
    if not recipients:
        print(f"[NOTIFICATION] No PSP recipients found for approved ticket — skipping")
        return False

    store = ticket.get("stores") or {}
    equipment = ticket.get("equipment") or {}
    ticket_num = ticket.get("ticket_number", "—")
    store_name = f"{store.get('store_number', '')} – {store.get('name', '')}".strip(" –")
    equip_name = equipment.get("name") or ticket.get("category") or "—"
    bid = ticket.get("contractor_bid") or 0
    bid_str = f"${bid:,.2f}" if bid else "—"
    app_link = APP_URL or "#"

    body_rows = "".join([
        '<tr><td colspan="2" style="padding:8px 32px 16px; color:#555; font-size:14px;">'
        'The DM has approved this ticket. You can now issue a work order.</td></tr>',
        _detail_row("Ticket #", ticket_num),
        _detail_row("Store", store_name or "—"),
        _detail_row("Equipment", equip_name),
        _detail_row("Approved Bid", f"<strong style='color:#27AE60; font-size:16px;'>{bid_str}</strong>"),
    ])

    html = _base_html(
        title=f"Ready for Work Order — Ticket #{ticket_num}",
        body_rows=body_rows,
        cta_url=app_link,
        cta_label="Issue Work Order →",
    )

    return _send_email(
        to_emails=recipients,
        subject=f"Approved — Ticket #{ticket_num} ready for work order ({store_name})",
        html_body=html,
    )


def notify_new_ticket(ticket: dict, store_name: str):
    """Placeholder — notify PSP about a new ticket. Not yet wired up."""
    print(f"[NOTIFICATION] New ticket #{ticket.get('ticket_number')} at {store_name}")


def notify_ticket_assigned(ticket_id: str, assignee_name: str):
    """Placeholder — not yet wired up."""
    print(f"[NOTIFICATION] Ticket {ticket_id} assigned to {assignee_name}")


def notify_contractor_info(ticket_id: str, contractor_name: str, contractor_phone: str):
    """Placeholder — not yet wired up."""
    print(f"[NOTIFICATION] Contractor info: {contractor_name} - {contractor_phone}")
