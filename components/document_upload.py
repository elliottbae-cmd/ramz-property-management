"""Document upload and display component for tickets."""

import streamlit as st
from database.ticket_documents import save_document, get_ticket_documents

MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx"]

DOC_TYPE_LABELS = {
    "estimate": "Estimate",
    "invoice": "Invoice",
    "warranty": "Warranty Doc",
    "photo": "Photo",
    "other": "Other",
}

DOC_ICONS = {
    "estimate": "📋",
    "invoice": "🧾",
    "warranty": "🛡️",
    "photo": "📷",
    "other": "📄",
}


def render_document_upload(
    ticket_id: str,
    client_id: str,
    user_id: str,
    allowed_types: list[str] | None = None,
    label: str = "Attach Document",
) -> None:
    """Render a file uploader widget for attaching documents to a ticket."""
    if allowed_types is None:
        allowed_types = list(DOC_TYPE_LABELS.keys())

    type_options = {t: DOC_TYPE_LABELS.get(t, t.title()) for t in allowed_types}

    uploaded_file = st.file_uploader(
        label,
        type=ALLOWED_EXTENSIONS,
        key=f"doc_upload_{ticket_id}_{label.replace(' ', '_')}",
        help=f"PDF, images, Word, or Excel — max {MAX_FILE_SIZE_MB}MB",
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()

        # Size check
        size_mb = len(file_bytes) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            st.error(f"File is {size_mb:.1f}MB — maximum allowed is {MAX_FILE_SIZE_MB}MB.")
            return

        col_type, col_notes = st.columns([1, 2])
        with col_type:
            selected_type = st.selectbox(
                "Document Type",
                options=list(type_options.keys()),
                format_func=lambda x: type_options[x],
                key=f"doc_type_{ticket_id}_{label.replace(' ', '_')}",
            )
        with col_notes:
            notes = st.text_input(
                "Notes (optional)",
                placeholder="e.g., Acme Plumbing estimate dated 4/5/26",
                key=f"doc_notes_{ticket_id}_{label.replace(' ', '_')}",
            )

        if st.button(
            f"Save {type_options.get(selected_type, 'Document')}",
            key=f"doc_save_{ticket_id}_{label.replace(' ', '_')}",
            width="stretch",
        ):
            result = save_document(
                file_bytes=file_bytes,
                file_name=uploaded_file.name,
                ticket_id=ticket_id,
                client_id=client_id,
                document_type=selected_type,
                uploaded_by=user_id,
                notes=notes,
            )
            if result:
                st.success(f"{type_options.get(selected_type, 'Document')} saved: **{uploaded_file.name}**")
                # Clear the cache so the document list refreshes
                get_ticket_documents.clear()
                st.rerun()
            else:
                st.error("Failed to save document. Check that the 'ticket-documents' storage bucket exists in Supabase.")


def render_document_list(ticket_id: str) -> None:
    """Render the list of documents attached to a ticket."""
    docs = get_ticket_documents(ticket_id)
    if not docs:
        st.caption("No documents attached yet.")
        return

    for doc in docs:
        doc_type = doc.get("document_type", "other")
        icon = DOC_ICONS.get(doc_type, "📄")
        label = DOC_TYPE_LABELS.get(doc_type, doc_type.title())
        name = doc.get("file_name", "Unknown")
        url = doc.get("file_url", "")
        size_bytes = doc.get("file_size_bytes") or 0
        size_str = f"{size_bytes / 1024:.0f} KB" if size_bytes < 1_048_576 else f"{size_bytes / 1_048_576:.1f} MB"
        created = (doc.get("created_at") or "")[:10]
        notes = doc.get("notes") or ""

        col_icon, col_info, col_link = st.columns([0.08, 0.72, 0.20])
        with col_icon:
            st.markdown(f"<div style='font-size:1.5rem; padding-top:4px;'>{icon}</div>", unsafe_allow_html=True)
        with col_info:
            st.markdown(f"**{name}**  \n{label} · {size_str} · {created}" + (f"  \n_{notes}_" if notes else ""))
        with col_link:
            if url:
                st.markdown(
                    f'<a href="{url}" target="_blank" style="display:inline-block; margin-top:8px; '
                    f'padding:4px 12px; background:#1B3A4B; color:white; border-radius:4px; '
                    f'text-decoration:none; font-size:0.8rem;">Open</a>',
                    unsafe_allow_html=True,
                )
