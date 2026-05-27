"""Shared httpx.AsyncClient with connection pooling.

All LLM API calls should use get_client() instead of creating a new
AsyncClient each time. This reuses TCP connections and prevents
connection pool exhaustion under concurrent requests.

Note: Not thread-safe — safe in Reflex's single-threaded async event loop,
but add a lock if multi-threaded access is ever needed.
"""

import httpx

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the shared async HTTP client (lazy-init, thread-safe)."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=120, write=10, pool=5),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30,
            ),
        )
    return _client


async def close_client() -> None:
    """Gracefully close the shared client. Call at app shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
