"""Test-harness support.

The live integration tests predate authentication: they call `requests.*`
with a `user_id` in the body, path, query or an X-User-Id header, and never
send a token. Rather than rewrite 180 call sites, this hook does exactly what
a real client does: it remembers the access token that `/api/auth/verify-otp`
returned for a user, and attaches it as a bearer to later requests that name
that user. A request that names a user the suite never signed in as gets no
token, so the server's 401/403 still mean what they say.

Only active when REACT_APP_BACKEND_URL is set; unit tests are untouched.
"""
from __future__ import annotations

import os
import re
import threading

import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
_OBJECT_ID = re.compile(r"^[0-9a-fA-F]{24}$")
_tokens: dict[str, str] = {}
_lock = threading.Lock()
_original_request = requests.Session.request


def _named_user(url: str, kwargs: dict) -> str | None:
    headers = kwargs.get("headers") or {}
    for key in ("X-User-Id", "x-user-id"):
        if headers.get(key):
            return headers[key]
    for field in ("json", "data", "params"):
        value = kwargs.get(field)
        if isinstance(value, dict) and isinstance(value.get("user_id"), str) and value["user_id"]:
            return value["user_id"]
    path = url[len(BASE):] if url.startswith(BASE) else url
    for segment in path.split("?")[0].split("/"):
        if _OBJECT_ID.match(segment):
            return segment
    m = re.search(r"[?&]user_id=([0-9a-fA-F]{24})", url)
    return m.group(1) if m else None


def _patched_request(self, method, url, **kwargs):
    if BASE and isinstance(url, str) and url.startswith(BASE):
        headers = dict(kwargs.get("headers") or {})
        if not any(k.lower() == "authorization" for k in headers):
            uid = _named_user(url, kwargs)
            token = _tokens.get(uid) if uid else None
            if token:
                headers["Authorization"] = f"Bearer {token}"
                kwargs["headers"] = headers
    response = _original_request(self, method, url, **kwargs)
    if BASE and isinstance(url, str) and url.startswith(BASE) and url.endswith("/api/auth/verify-otp") \
            and response.ok:
        try:
            data = response.json()
            if data.get("access_token") and data.get("user_id"):
                with _lock:
                    _tokens[data["user_id"]] = data["access_token"]
        except ValueError:
            pass
    return response


if BASE:
    requests.Session.request = _patched_request


def token_for(user_id: str) -> str | None:
    """For tests that want to build an Authorization header explicitly."""
    return _tokens.get(user_id)


# ── Unit mode (no live server): an in-memory auth store and a bearer minter ──

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _memory_auth_store():
    """Every test gets a fresh in-memory session store in this process.

    In-process tests (TestClient) must never reach Mongo for sessions: a Motor
    client bound to one test's event loop fails in the next with "Event loop
    is closed". Live tests talk to the server over HTTP and never touch this
    process's store, so installing it is harmless for them too."""
    try:
        from auth import tokens
        from auth.store import MemorySessionStore, set_store
    except Exception:  # noqa: BLE001 — a test that cannot import auth is not using it
        yield
        return
    set_store(MemorySessionStore())
    tokens._active_cache.clear()
    yield
    set_store(None)


@pytest.fixture
def bearer_for():
    """bearer_for(user_id, role="citizen") -> {"Authorization": "Bearer …"}."""
    import asyncio
    from auth import tokens

    def _mint(user_id: str, role: str = "citizen") -> dict:
        session = asyncio.run(tokens.create_session(user_id, role))
        return {"Authorization": f"Bearer {session['access_token']}"}

    return _mint
