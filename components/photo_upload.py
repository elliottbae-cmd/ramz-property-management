"""Photo upload handler for repair request evidence with auto-compression."""

import io
import streamlit as st
import uuid
from PIL import Image
from database.supabase_client import upload_photo, get_client

MAX_DIMENSION = 1200  # px — longest side
JPEG_QUALITY = 75     # 1-100, lower = smaller file
MAX_PHOTOS = 3


def _compress_photo(file_bytes: bytes, filename: str) -> tuple[bytes, str]:
    """Compress and resize a photo. Returns (compressed_bytes, new_filename)."""
    try:
        img = Image.open(io.BytesIO(file_bytes))

        # Convert RGBA/palette to RGB for JPEG
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # Auto-rotate based on EXIF
        try:
            from PIL import ExifTags
            exif = img._getexif()
            if exif:
                for tag, value in exif.items():
                    if ExifTags.TAGS.get(tag) == "Orientation":
                        if value == 3:
                            img = img.rotate(180, expand=True)
                        elif value == 6:
                            img = img.rotate(270, expand=True)
                        elif value == 8:
                            img = img.rotate(90, expand=True)
                        break
        except Exception:
            pass

        # Resize if larger than MAX_DIMENSION
        w, h = img.size
        if max(w, h) > MAX_DIMENSION:
            ratio = MAX_DIMENSION / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Save as JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        compressed = buffer.getvalue()

        # New filename with .jpg extension
        base = filename.rsplit(".", 1)[0] if "." in filename else filename
        return compressed, f"{base}.jpg"
    except Exception:
        # If compression fails, return original
        return file_bytes, filename


def render_photo_upload(ticket_id: str = None):
    """Render photo upload UI. Returns list of uploaded file objects if no ticket_id (pre-submit)."""
    st.markdown(f"**Upload Photos** (take a picture or choose from gallery, max {MAX_PHOTOS})")

    uploaded_files = st.file_uploader(
        "Upload photos of the issue",
        type=["jpg", "jpeg", "png", "heic"],
        accept_multiple_files=True,
        help=f"Max {MAX_PHOTOS} photos. Photos are automatically compressed to save storage.",
        label_visibility="collapsed",
    )

    if uploaded_files and len(uploaded_files) > MAX_PHOTOS:
        st.warning(f"Maximum {MAX_PHOTOS} photos allowed. Only the first {MAX_PHOTOS} will be uploaded.")
        uploaded_files = uploaded_files[:MAX_PHOTOS]

    if uploaded_files:
        cols = st.columns(min(len(uploaded_files), 3))
        for i, file in enumerate(uploaded_files):
            with cols[i % 3]:
                st.image(file, caption=file.name, width="stretch")

    return uploaded_files


def save_photos(uploaded_files, ticket_id: str) -> list:
    """Compress, upload photos to Supabase Storage, and link to ticket. Returns list of URLs."""
    urls = []
    files_to_upload = uploaded_files[:MAX_PHOTOS]

    for file in files_to_upload:
        # Compress the photo
        raw_bytes = file.getvalue()
        original_size = len(raw_bytes)
        compressed_bytes, new_filename = _compress_photo(raw_bytes, file.name)
        compressed_size = len(compressed_bytes)

        unique_name = f"{uuid.uuid4().hex}.jpg"
        try:
            url = upload_photo(compressed_bytes, unique_name, ticket_id)
            # Record the photo in the ticket_photos table
            sb = get_client()
            sb.table("ticket_photos").insert({
                "ticket_id": ticket_id,
                "photo_url": url,
            }).execute()
            urls.append(url)

            # Show compression savings
            if original_size > 0:
                savings = ((original_size - compressed_size) / original_size) * 100
                if savings > 5:
                    st.caption(f"Photo compressed: {original_size // 1024}KB → {compressed_size // 1024}KB ({savings:.0f}% smaller)")
        except Exception as e:
            st.warning(f"Failed to upload {file.name}: {str(e)}")
    return urls
