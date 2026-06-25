"""Storage URL helpers — short-lived signed URLs for private buckets.

Documents/photos are stored in the DB as Supabase **public** object URLs:
    {SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}

``signed_url`` parses the (bucket, path) back out and mints a time-limited
signed URL so the buckets can be made private without breaking access. Signing
works on public buckets too, so this is SAFE to deploy *before* flipping the
bucket to private — there is no window where access breaks:

    1. Deploy this (documents still load via signed URLs on the public bucket).
    2. Verify documents/photos open normally.
    3. Flip the bucket to private in Supabase — public URLs die, signed URLs
       keep working.

A non-Supabase or unparseable URL (e.g. a logo in a bucket left public) is
returned unchanged.
"""

import streamlit as st
from database.supabase_client import get_admin_client

SIGNED_URL_TTL = 3600  # seconds the signed URL stays valid


def _parse_public_url(url: str) -> tuple[str, str]:
    """Return (bucket, path) from a Supabase public object URL, or ('', '')."""
    if not url:
        return "", ""
    marker = "/object/public/"
    idx = url.find(marker)
    if idx == -1:
        return "", ""
    rest = url[idx + len(marker):].split("?", 1)[0]
    parts = rest.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return "", ""
    return parts[0], parts[1]  # (bucket, path)


@st.cache_data(ttl=SIGNED_URL_TTL - 300)
def _sign(bucket: str, path: str) -> str:
    """Mint a signed URL (cached just under its lifetime). Raises on failure so
    a transient error isn't cached as a dead fallback."""
    sb = get_admin_client()
    res = sb.storage.from_(bucket).create_signed_url(path, SIGNED_URL_TTL)
    url = (res or {}).get("signedURL") or (res or {}).get("signedUrl")
    if not url:
        raise RuntimeError("no signed URL returned")
    return url


def signed_url(stored_url: str) -> str:
    """Convert a stored public URL into a short-lived signed URL.

    Returns the original URL unchanged if it can't be parsed or signing fails
    (so non-Supabase URLs and transient errors degrade gracefully).
    """
    bucket, path = _parse_public_url(stored_url)
    if not bucket or not path:
        return stored_url
    try:
        return _sign(bucket, path)
    except Exception:
        return stored_url
