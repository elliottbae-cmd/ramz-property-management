"""Photo upload handler for repair request evidence."""

import streamlit as st
import uuid
from database.supabase_client import upload_photo, add_ticket_photo


def render_photo_upload(ticket_id: str = None):
    """Render photo upload UI. Returns list of uploaded file objects if no ticket_id (pre-submit)."""
    st.markdown("**Upload Photos** (take a picture or choose from gallery)")

    uploaded_files = st.file_uploader(
        "Upload photos of the issue",
        type=["jpg", "jpeg", "png", "heic"],
        accept_multiple_files=True,
        help="You can upload multiple photos. Use your phone camera for best results.",
        label_visibility="collapsed",
    )

    if uploaded_files:
        cols = st.columns(min(len(uploaded_files), 3))
        for i, file in enumerate(uploaded_files):
            with cols[i % 3]:
                st.image(file, caption=file.name, use_container_width=True)

    return uploaded_files


def save_photos(uploaded_files, ticket_id: str) -> list:
    """Upload photos to Supabase Storage and link to ticket. Returns list of URLs."""
    urls = []
    for file in uploaded_files:
        file_ext = file.name.split(".")[-1] if "." in file.name else "jpg"
        unique_name = f"{uuid.uuid4().hex}.{file_ext}"
        try:
            url = upload_photo(file.getvalue(), unique_name, ticket_id)
            add_ticket_photo(ticket_id, url)
            urls.append(url)
        except Exception as e:
            st.warning(f"Failed to upload {file.name}: {str(e)}")
    return urls
