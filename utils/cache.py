"""Caching helpers that avoid poisoning the cache with transient failures.

Streamlit's ``st.cache_data`` caches whatever a function returns — including an
empty list/dict returned by an internal ``try/except``. A single transient
error (network blip, brief RLS/auth hiccup) then sticks as "no data" for the
full TTL, which is how queues, switchers, and forms silently go blank.

``cached_query`` caches only *successful* results: the decorated function lets
exceptions propagate (so nothing is memoized), and the failure is converted to
a safe default at the boundary. The wrapped function still exposes ``.clear()``
just like ``st.cache_data`` so existing invalidation calls keep working.
"""

import functools
import streamlit as st


def cached_query(ttl: int, default_factory=list):
    """Cache successful results only; return ``default_factory()`` on error.

    Parameters
    ----------
    ttl : int
        Cache time-to-live in seconds (passed through to ``st.cache_data``).
    default_factory : callable
        Zero-arg callable producing the fallback value on error
        (e.g. ``list``, ``dict``, or ``lambda: None``).

    The decorated function MUST let exceptions propagate (no internal
    ``try/except`` returning a fallback) — that is what keeps failures out of
    the cache.
    """
    def decorator(fn):
        cached_fn = st.cache_data(ttl=ttl)(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return cached_fn(*args, **kwargs)
            except Exception:
                return default_factory()

        # Preserve the st.cache_data API used for invalidation elsewhere
        wrapper.clear = cached_fn.clear
        return wrapper

    return decorator
