"""Ticket document CRUD — estimates, invoices, and other attachments."""

import uuid
import streamlit as st
from database.supabase_client import get_client

STORAGE_BUCKET = "ticket-documents"


def upload_document(file_bytes: bytes, file_name: str, ticket_id: str) -> str:
    """Upload a document to Supabase Storage and return the public URL."""
    sb = get_client()
    path = f"{ticket_id}/{uuid.uuid4().hex}_{file_name}"
    sb.storage.from_(STORAGE_BUCKET).upload(path, file_bytes, {"content-type": _mime_type(file_name)})
    return sb.storage.from_(STORAGE_BUCKET).get_public_url(path)


def _mime_type(filename: str) -> str:
    """Return MIME type based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(ext, "application/octet-stream")


def save_document(
    file_bytes: bytes,
    file_name: str,
    ticket_id: str,
    client_id: str,
    document_type: str,
    uploaded_by: str,
    notes: str = None,
) -> dict | None:
    """Upload file to storage and record metadata in ticket_documents table."""
    try:
        url = upload_document(file_bytes, file_name, ticket_id)
        sb = get_client()
        row = {
            "ticket_id": ticket_id,
            "client_id": client_id,
            "document_type": document_type,
            "file_name": file_name,
            "file_url": url,
            "file_size_bytes": len(file_bytes),
            "uploaded_by": uploaded_by,
        }
        if notes:
            row["notes"] = notes
        result = sb.table("ticket_documents").insert(row).execute()
        return result.data[0] if result.data else None
    except Exception as e:
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
    """Delete a document record (does not remove from storage)."""
    try:
        sb = get_client()
        sb.table("ticket_documents").delete().eq("id", doc_id).execute()
        return True
    except Exception:
        return False
