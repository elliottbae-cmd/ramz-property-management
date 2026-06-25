"""Ticket document storage — estimates, invoices, warranty docs, etc."""

from database.supabase_client import get_client, get_admin_client
from utils.cache import cached_query

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
    """Upload a file to Supabase Storage and return the public URL.

    Uses the admin client for storage so the upload is not blocked by RLS
    (get_client() only sets the JWT on PostgREST, not on the storage client).
    Raises on error so the caller can surface the real message.
    """
    sb = get_admin_client()
    path = f"{ticket_id}/{file_name}"
    sb.storage.from_(BUCKET).upload(
        path,
        file_bytes,
        {"content-type": _mime_type(file_name), "upsert": "true"},
    )
    result = sb.storage.from_(BUCKET).get_public_url(path)
    return result


def save_document(
    file_bytes: bytes,
    file_name: str,
    ticket_id: str,
    client_id: str,
    document_type: str,
    uploaded_by: str,
    notes: str = "",
) -> dict | None:
    """Upload file to storage and insert a record into ticket_documents.

    Raises on error so the caller can surface the real message.
    """
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
        "notes": notes or None,
    }
    result = sb.table("ticket_documents").insert(row).execute()
    saved = result.data[0] if result.data else None
    if saved:
        get_ticket_documents.clear()
    return saved


@cached_query(ttl=60, default_factory=list)
def get_ticket_documents(ticket_id: str) -> list[dict]:
    """Fetch all documents attached to a ticket, newest first."""
    sb = get_client()
    result = (
        sb.table("ticket_documents")
        .select("*")
        .eq("ticket_id", ticket_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def delete_document(doc_id: str) -> bool:
    """Delete a document record AND remove its storage file.

    Looks up the row first to recover the storage path so the underlying file
    is removed too (otherwise it lingers — and stays publicly reachable).
    """
    try:
        sb = get_client()
        # Recover the storage path from the stored public URL before deleting
        try:
            existing = (
                sb.table("ticket_documents")
                .select("file_url")
                .eq("id", doc_id)
                .single()
                .execute()
            )
            file_url = (existing.data or {}).get("file_url", "")
            path = _storage_path_from_url(file_url)
            if path:
                get_admin_client().storage.from_(BUCKET).remove([path])
        except Exception:
            pass  # best-effort file cleanup — still remove the DB row

        sb.table("ticket_documents").delete().eq("id", doc_id).execute()
        get_ticket_documents.clear()
        return True
    except Exception:
        return False


def _storage_path_from_url(file_url: str) -> str:
    """Extract the in-bucket object path from a Supabase public URL.

    e.g. .../object/public/ticket-documents/<ticket_id>/<file> → <ticket_id>/<file>
    """
    if not file_url:
        return ""
    marker = f"/public/{BUCKET}/"
    idx = file_url.find(marker)
    if idx == -1:
        return ""
    return file_url[idx + len(marker):].split("?", 1)[0]
