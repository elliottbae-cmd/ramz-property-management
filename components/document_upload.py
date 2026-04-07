"""Document upload component for ticket attachments (estimates, invoices, etc.)."""

import streamlit as st
from database.ticket_documents import save_document, get_ticket_documents

ALLOWED_TYPES = ["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx"]
MAX_FILE_MB = 10
DOC_TYPE_LABELS = {
    "estimate": "📋 Estimate",
    "invoice": "🧾 Invoice",
    "warranty": "🛡️ Warranty Doc",
    "photo": "📷 Photo",
    "other": "📎 Other",
}


def render_document_upload(
    ticket_id: str,
    client_id: str,
    user_id: str,
    allowed_types: list[str] | None = None,
    label: str = "Attach Document",
):
    """Render an upload widget and save on submission.

    Parameters
    ----------
    ticket_id   : ticket UUID
    client_id   : client UUID
    user_id     : uploading user UUID
    allowed_types : restrict to subset of document_type values (None = all)
    label       : widget label
    """
    type_options = {k: v for k, v in DOC_TYPE_LABELS.items()
                    if allowed_types is None or k in allowed_types}

    uploaded = st.file_uploader(
        label,
        type=ALLOWED_TYPES,
        help=f"Supported: PDF, images, Word, Excel. Max {MAX_FILE_MB}MB.",
        key=f"docupload_{ticket_id}_{label.replace(' ', '_')}",
    )

    if uploaded:
        file_size_mb = len(uploaded.getvalue()) / (1024 * 1024)
        if file_size_mb > MAX_FILE_MB:
            st.error(f"File too large ({file_size_mb:.1f}MB). Maximum is {MAX_FILE_MB}MB.")
            return

        doc_type = st.selectbox(
            "Document type",
            options=list(type_options.keys()),
            format_func=lambda x: type_options[x],
            key=f"doctype_{ticket_id}_{label.replace(' ', '_')}",
        )
        doc_notes = st.text_input(
            "Notes (optional)",
            key=f"docnotes_{ticket_id}_{label.replace(' ', '_')}",
            placeholder="e.g. Acme HVAC estimate dated 4/7/26",
        )

        if st.button(f"Upload {uploaded.name}", key=f"docsubmit_{ticket_id}_{label.replace(' ', '_')}", width="stretch"):
            with st.spinner("Uploading..."):
                result = save_document(
                    file_bytes=uploaded.getvalue(),
                    file_name=uploaded.name,
                    ticket_id=ticket_id,
                    client_id=client_id,
                    document_type=doc_type,
                    uploaded_by=user_id,
                    notes=doc_notes or None,
                )
            if result:
                st.success(f"Uploaded: {uploaded.name}")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Upload failed. Check that the 'ticket-documents' storage bucket exists in Supabase.")


def render_document_list(ticket_id: str, show_delete: bool = False, user_id: str = None):
    """Render a list of documents attached to a ticket."""
    docs = get_ticket_documents(ticket_id)
    if not docs:
        st.caption("No documents attached yet.")
        return

    for doc in docs:
        doc_type = doc.get("document_type", "other")
        icon = DOC_TYPE_LABELS.get(doc_type, "📎")
        file_name = doc.get("file_name", "Unknown")
        file_url = doc.get("file_url", "")
        size_kb = (doc.get("file_size_bytes") or 0) // 1024
        uploaded = (doc.get("created_at") or "")[:10]
        notes = doc.get("notes", "")

        col_info, col_link = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"{icon} **{file_name}**"
                f"<span style='color:#9E9E9E; font-size:0.8rem;'>"
                f"  ·  {doc_type.title()}  ·  {size_kb}KB  ·  {uploaded}"
                f"{('  ·  ' + notes) if notes else ''}"
                f"</span>",
                unsafe_allow_html=True,
            )
        with col_link:
            if file_url:
                st.markdown(f"[Open]({file_url})", unsafe_allow_html=False)
