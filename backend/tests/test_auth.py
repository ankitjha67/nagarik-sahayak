"""The authentication layer, end to end, without a database.

Covers: TOTP; hashed single-use OTP with lockout; signed access tokens;
refresh rotation and reuse detection; revocation; the one enforcement rule
on a small app; the edge middleware; and the hash-chained audit.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
from fastapi import Request  # module level: nested handlers resolve the string annotation here

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("AUTH_JWT_SECRET", "unit-test-secret-which-is-long-enough-0123456789")
os.environ.setdefault("ADMIN_SECRET", "test-secret")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("APP_ENV", "development")
# DEMO_MODE and OTP_MOCK_CODE are set per test with monkeypatch: a module-level
# assignment would leak into the other test modules in this process.

from auth import audit, otp, settings, tokens, totp  # noqa: E402
from auth.store import MemorySessionStore, set_store  # noqa: E402


@pytest.fixture(autouse=True)
def memory_store():
    store = MemorySessionStore()
    set_store(store)
    tokens._active_cache.clear()
    yield store
    set_store(None)


# ── TOTP ───────────────────────────────────────────────────────────────────

def test_totp_round_trip_and_drift():
    secret = totp.generate_secret()
    now = time.time()
    code = totp.totp(secret, at=now)
    assert totp.verify(secret, code, at=now)
    assert totp.verify(secret, code, at=now + 30)          # one step of drift
    assert not totp.verify(secret, code, at=now + 120)     # too old
    assert not totp.verify(secret, "000000", at=now) or code == "000000"
    assert totp.otpauth_uri(secret, "admin").startswith("otpauth://totp/")


# ── OTP ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_otp_is_hashed_single_use_and_locks(memory_store, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("OTP_MOCK_CODE", "")
    issued = await otp.issue("9876543210")
    assert not issued.mocked and len(issued.code) == 6
    stored = memory_store.otps["9876543210"]
    assert issued.code not in str(stored)                  # never stored in clear

    with pytest.raises(otp.OtpError) as e:
        await otp.verify("9876543210", "000000" if issued.code != "000000" else "111111")
    assert e.value.status == 401 and "attempt" in e.value.reason

    await otp.verify("9876543210", issued.code)            # correct: consumed
    with pytest.raises(otp.OtpError):
        await otp.verify("9876543210", issued.code)        # second use refused

    issued = await otp.issue("9876543210")
    wrong = "000000" if issued.code != "000000" else "111111"
    for _ in range(settings.otp_max_attempts() - 1):
        with pytest.raises(otp.OtpError):
            await otp.verify("9876543210", wrong)
    with pytest.raises(otp.OtpError) as e:
        await otp.verify("9876543210", wrong)
    assert e.value.status == 429 and e.value.retry_after > 0
    with pytest.raises(otp.OtpError) as e:                # even the right code, while locked
        await otp.verify("9876543210", issued.code)
    assert e.value.status == 429


@pytest.mark.asyncio
async def test_otp_expires(memory_store, monkeypatch):
    monkeypatch.setenv("OTP_TTL_SECONDS", "1")
    issued = await otp.issue("9876543211")
    memory_store.otps["9876543211"]["expires_at"] = time.time() - 1
    with pytest.raises(otp.OtpError) as e:
        await otp.verify("9876543211", issued.code)
    assert "expired" in e.value.reason


def test_mock_code_never_in_production(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("APP_ENV", "development")
    assert settings.otp_mock_code() == "123456"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OTP_MOCK_CODE", "999999")
    assert settings.otp_mock_code() == ""


# ── Tokens and sessions ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_access_token_round_trip_and_expiry():
    s = await tokens.create_session("64b15bf4c3a58e12cb335ec0", "citizen", phone="9876543210")
    claims = tokens.decode_access(s["access_token"])
    assert claims.user_id == "64b15bf4c3a58e12cb335ec0" and claims.role == "citizen"
    assert await tokens.session_active(claims.sid)
    assert s["expires_in"] <= 3600

    expired = tokens.issue_access(tokens.Claims("u", "citizen", "sid"), ttl=-1)
    with pytest.raises(tokens.TokenError):
        tokens.decode_access(expired)
    with pytest.raises(tokens.TokenError):
        tokens.decode_access(s["access_token"][:-3] + "abc")


@pytest.mark.asyncio
async def test_refresh_rotates_and_reuse_revokes_session():
    s = await tokens.create_session("u1", "citizen")
    r1 = await tokens.refresh_session(s["refresh_token"])
    assert r1["refresh_token"] != s["refresh_token"]
    assert await tokens.session_active(s["sid"])

    # The first refresh token was retired; presenting it again is theft.
    with pytest.raises(tokens.TokenError) as e:
        await tokens.refresh_session(s["refresh_token"])
    assert "revoked" in e.value.reason.lower()
    tokens.forget_session(s["sid"])
    assert not await tokens.session_active(s["sid"])
    with pytest.raises(tokens.TokenError):
        await tokens.refresh_session(r1["refresh_token"])   # whole session is dead


@pytest.mark.asyncio
async def test_logout_revokes_within_cache_window():
    s = await tokens.create_session("u2", "citizen")
    await tokens.revoke_session(s["sid"])
    assert not await tokens.session_active(s["sid"])


# ── The enforcement rule, on a small app ────────────────────────────────────

def _app():
    from fastapi import Depends, FastAPI, Request
    from fastapi.testclient import TestClient
    from api.middleware import (BodySizeLimitMiddleware, RateLimitMiddleware,
                                RequestIdMiddleware, SecurityHeadersMiddleware)
    from fastapi import APIRouter
    from auth.deps import enforce

    app = FastAPI()
    api_router = APIRouter(prefix="/api")      # a private router: never the shared one

    @api_router.get("/schemes")
    async def public():
        return {"ok": True}

    @api_router.post("/v2/smart-profiler")
    async def named(body: dict):
        return {"user_id": body.get("user_id")}

    @api_router.get("/profile/{user_id}")
    async def profile(user_id: str):
        return {"user_id": user_id}

    @api_router.post("/chat")
    async def chat(body: dict, request: Request):
        p = getattr(request.state, "principal", None)
        return {"principal": p.user_id if p else None}

    @api_router.get("/pdf/{pdf_id}")
    async def pdf(pdf_id: str, request: Request):
        from auth.deps import principal_of
        return {"who": principal_of(request).user_id}

    app.include_router(api_router, dependencies=[Depends(enforce)])
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client():
    return _app()


@pytest.fixture
def bearer():
    import asyncio
    s = asyncio.run(
        tokens.create_session("64b15bf4c3a58e12cb335ec0", "citizen"))
    return {"Authorization": f"Bearer {s['access_token']}"}


UID = "64b15bf4c3a58e12cb335ec0"
OTHER = "64b15bf4c3a58e12cb335ec1"


def test_public_route_needs_no_token(client):
    assert client.get("/api/schemes").status_code == 200


def test_protected_route_requires_token(client, bearer):
    assert client.get(f"/api/pdf/abc").status_code == 401
    assert client.get(f"/api/pdf/abc", headers=bearer).status_code == 200


def test_named_user_must_match_token(client, bearer):
    assert client.post("/api/v2/smart-profiler", json={"user_id": UID}).status_code == 401
    assert client.post("/api/v2/smart-profiler", json={"user_id": UID}, headers=bearer).status_code == 200
    assert client.post("/api/v2/smart-profiler", json={"user_id": OTHER}, headers=bearer).status_code == 403
    assert client.get(f"/api/profile/{OTHER}", headers=bearer).status_code == 403
    assert client.get(f"/api/profile/{UID}", headers=bearer).status_code == 200
    # A stale X-User-Id header from an old client cannot widen access either.
    assert client.get("/api/schemes", headers={**bearer, "X-User-Id": OTHER}).status_code == 403


def test_admin_secret_is_an_admin_principal(client, monkeypatch):
    import config
    monkeypatch.setattr(config, "ADMIN_SECRET", "test-secret")   # whatever the shell's .env says
    r = client.get(f"/api/profile/{OTHER}", headers={"X-Admin-Secret": "test-secret"})
    assert r.status_code == 200
    assert client.get(f"/api/profile/{OTHER}", headers={"X-Admin-Secret": "wrong"}).status_code == 401


def test_demo_placeholders_only_in_demo_mode(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEMO_MODE", "false")
    assert client.post("/api/chat", json={"user_id": "test-user", "content": "hi"}).status_code == 401
    monkeypatch.setenv("DEMO_MODE", "true")
    assert client.post("/api/chat", json={"user_id": "test-user", "content": "hi"}).status_code == 200
    # A real-looking id is never a demo placeholder.
    assert client.post("/api/chat", json={"user_id": UID, "content": "hi"}).status_code == 401


def test_revoked_session_is_refused(client):
    import asyncio
    s = asyncio.run(tokens.create_session(UID, "citizen"))
    h = {"Authorization": f"Bearer {s['access_token']}"}
    assert client.get(f"/api/profile/{UID}", headers=h).status_code == 200
    asyncio.run(tokens.revoke_session(s["sid"]))
    assert client.get(f"/api/profile/{UID}", headers=h).status_code == 401


# ── Edge middleware ─────────────────────────────────────────────────────────

def test_security_headers_and_request_id(client):
    r = client.get("/api/schemes", headers={"X-Request-Id": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_body_size_limit(client, bearer, monkeypatch):
    monkeypatch.setenv("MAX_JSON_BODY_BYTES", "100")
    r = client.post("/api/v2/smart-profiler", json={"user_id": UID, "pad": "x" * 500}, headers=bearer)
    assert r.status_code == 413


def test_rate_limit_answers_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "3")
    c = _app()
    codes = [c.get("/api/schemes").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes[3:]
    r = c.get("/api/schemes")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


# ── Audit chain ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_chain_detects_tampering(memory_store):
    for i in range(5):
        await audit.record("login", actor=f"u{i}", subject=f"u{i}", ip="127.0.0.1")
    ok = await audit.verify_chain()
    assert ok["ok"] and ok["checked"] == 5
    memory_store.audit[2]["actor"] = "attacker"
    bad = await audit.verify_chain()
    assert not bad["ok"] and bad["broken_at_seq"] == 3
