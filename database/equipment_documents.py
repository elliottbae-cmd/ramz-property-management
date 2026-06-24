"""Equipment warranty document storage.

Reuses the existing public `ticket-documents` bucket (no new bucket / RLS
policies needed) under an `equipment/<equipment_id>/` path prefix. Document
URLs are stored on the warranty record's `document_urls` TEXT[] column.
"""

import re
import streamlit as st
from database.supabase_client import get_client, get_admin_client
from database.ticket_documents import _mime_type

BUCKET = "ticket-documents"


def _safe_name(file_name: str) -> str:
    """Sanitize a filename for use in a storage path.

    Keeps the extension, replaces spaces and unsafe characters with
    underscores so the storage path and public URL stay clean.
    """
    name = file_name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name or "document"


def upload_warranty_document(file_bytes: bytes, file_name: str, equipment_id: str) -> str:
    """Upload a warranty file to storage and return its public URL.

    Uses the admin client for storage so the upload is not blocked by RLS
    (get_client() only sets the JWT on PostgREST, not on the storage client).
    Raises on error so the caller can surface the real message.
    """
    safe = _safe_name(file_name)
    sb = get_admin_client()
    path = f"equipment/{equipment_id}/{safe}"
    sb.storage.from_(BUCKET).upload(
        path,
        file_bytes,
        {"content-type": _mime_type(safe), "upsert": "true"},
    )
    return sb.storage.from_(BUCKET).get_public_url(path)


def add_warranty_document(warranty_id: str, equipment_id: str,
                          file_bytes: bytes, file_name: str) -> bool:
    """Upload a document and append its URL to the warranty's document_urls.

    Raises on error so the caller can surface the real message.
    """
    url = upload_warranty_document(file_bytes, file_name, equipment_id)
    sb = get_client()

    # Read the current array, append, write back (Postgres array update)
    current = (
        sb.table("equipment_warranties")
        .select("document_urls")
        .eq("id", warranty_id)
        .single()
        .execute()
    )
    urls = (current.data or {}).get("document_urls") or []
    if url not in urls:
        urls.append(url)

    sb.table("equipment_warranties").update(
        {"document_urls": urls}
    ).eq("id", warranty_id).execute()
    return True


def remove_warranty_document(warranty_id: str, url: str) -> bool:
    """Remove a document URL from a warranty's document_urls array.

    Removes only the DB reference, not the underlying storage file.
    """
    try:
        sb = get_client()
        current = (
            sb.table("equipment_warranties")
            .select("document_urls")
            .eq("id", warranty_id)
            .single()
            .execute()
        )
        urls = (current.data or {}).get("document_urls") or []
        urls = [u for u in urls if u != url]
        sb.table("equipment_warranties").update(
            {"document_urls": urls}
        ).eq("id", warranty_id).execute()
        return True
    except Exception:
        return False
