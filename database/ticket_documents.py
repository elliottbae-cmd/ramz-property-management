"""Ticket document storage — estimates, invoices, warranty docs, etc."""

import streamlit as st
from database.supabase_client import get_client

BUCKET = "ticket-documents"


def _mime_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return mime_map.get(ext, "application/octet-stream")


def upload_document(file_bytes: bytes, file_name: str, ticket_id: str) -> str | None:
    """Upload a file to Supabase Storage and return the public URL."""
    try:
        sb = get_client()
        path = f"{ticket_id}/{file_name}"
        sb.storage.from_(BUCKET).upload(
            path,
            file_bytes,
            {"content-type": _mime_type(file_name), "upsert": "true"},
        )
        result = sb.storage.from_(BUCKET).get_public_url(path)
        return result
    except Exception:
        return None


def save_document(
    file_bytes: bytes,
    file_name: str,
    ticket_id: str,
    client_id: str,
    document_type: str,
    uploaded_by: str,
    notes: str = "",
) -> dict | None:
    """Upload file to storage and insert a record into ticket_documents."""
    url = upload_document(file_bytes, file_name, ticket_id)
    if not url:
        return None
    try:
        sb = get_client()
        row = {
            "ticket_id": ticket_id,
            "client_id": client_id,
            "document_type": document_type,
            "file_name": file_name,
            "file_url": url,
            "file_size_bytes": len(file_bytes),
            "uploaded_by": uploaded_by,
            "notes": notes or None,
        }
        result = sb.table("ticket_documents").insert(row).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


@st.cache_data(ttl=60)
def get_ticket_documents(ticket_id: str) -> list[dict]:
    """Fetch all documents attached to a ticket, newest first."""
    try:
        sb = get_client()
        result = (
            sb.table("ticket_documents")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def delete_document(doc_id: str) -> bool:
    """Delete a document record (does not remove storage file)."""
    try:
        sb = get_client()
        sb.table("ticket_documents").delete().eq("id", doc_id).execute()
        return True
    except Exception:
        return False
