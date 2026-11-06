"""ASGI middleware for the API edge.

  RequestIdMiddleware      - X-Request-Id in, generated if absent, echoed out
  SecurityHeadersMiddleware- the headers every API response should carry
  BodySizeLimitMiddleware  - 413 before a large body is read, chunked included
  RateLimitMiddleware      - per-client token bucket, 429 with Retry-After

All four are pure ASGI (no BaseHTTPMiddleware), so streaming responses and
file downloads pass through untouched and nothing buffers a body twice.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections import defaultdict
from typing import Callable

from auth import settings


def _header(scope, name: str) -> str:
    target = name.lower().encode()
    for k, v in scope.get("headers", []):
        if k == target:
            return v.decode("latin-1")
    return ""


def client_ip(scope) -> str:
    """The client address, trusting X-Forwarded-For only from listed proxies."""
    peer = (scope.get("client") or ("", 0))[0] or ""
    if peer in settings.trusted_proxies():
        fwd = _header(scope, "x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return peer


async def _send_json(send, status: int, body: dict, extra_headers=()) -> None:
    payload = json.dumps(body).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
    headers.extend(extra_headers)
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": payload})


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = _header(scope, "x-request-id")[:64] or secrets.token_hex(8)
        scope.setdefault("state", {})["request_id"] = rid

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        await self.app(scope, receive, send_with_id)


class SecurityHeadersMiddleware:
    HEADERS = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
        (b"permissions-policy", b"camera=(), geolocation=(), microphone=(self)"),
        (b"cross-origin-resource-policy", b"same-site"),
        (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
        (b"cache-control", b"no-store"),
    ]

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        https = scope.get("scheme") == "https" or _header(scope, "x-forwarded-proto") == "https"

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {k for k, _ in headers}
                for k, v in self.HEADERS:
                    if k not in present:
                        headers.append((k, v))
                if https and b"strict-transport-security" not in present:
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Refuse oversized bodies: by Content-Length up front, and by counting
    chunks for a request that sends none."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        ctype = _header(scope, "content-type")
        limit = settings.max_upload_body_bytes() if ctype.startswith("multipart/") else settings.max_json_body_bytes()
        declared = _header(scope, "content-length")
        if declared.isdigit() and int(declared) > limit:
            return await _send_json(send, 413, {"detail": f"Request body too large (limit {limit} bytes)."})

        seen = 0
        tripped = False

        async def counting_receive():
            nonlocal seen, tripped
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit and not tripped:
                    tripped = True
                    # Drain nothing more; the app will see a truncated body and fail to parse.
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        await self.app(scope, counting_receive, send)


class RateLimitMiddleware:
    """A token bucket per client (bearer token hash when present, else IP)."""

    def __init__(self, app, per_minute: Callable[[], int] | None = None):
        self.app = app
        self.per_minute = per_minute or settings.api_rate_limit_per_minute
        self.buckets: dict[str, list[float]] = defaultdict(list)   # key -> [tokens, last]
        self._last_prune = time.time()

    def _key(self, scope) -> str:
        auth = _header(scope, "authorization")
        if auth.lower().startswith("bearer "):
            return "t:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:24]
        return "ip:" + client_ip(scope)

    def _take(self, key: str) -> tuple[bool, int]:
        rate = max(1, self.per_minute())
        now = time.time()
        bucket = self.buckets.get(key)
        if bucket is None:
            bucket = [float(rate), now]
            self.buckets[key] = bucket
        tokens, last = bucket
        tokens = min(float(rate), tokens + (now - last) * rate / 60.0)
        if tokens >= 1.0:
            bucket[0], bucket[1] = tokens - 1.0, now
            return True, 0
        bucket[0], bucket[1] = tokens, now
        retry = int((1.0 - tokens) * 60.0 / rate) + 1
        if now - self._last_prune > 300:
            self._prune(now)
        return False, retry

    def _prune(self, now: float) -> None:
        self._last_prune = now
        for k in [k for k, (_, last) in self.buckets.items() if now - last > 600]:
            self.buckets.pop(k, None)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        ok, retry = self._take(self._key(scope))
        if not ok:
            return await _send_json(send, 429, {"detail": "Too many requests. Please slow down."},
                                    [(b"retry-after", str(retry).encode())])
        await self.app(scope, receive, send)
