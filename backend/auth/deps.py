"""Who is calling, and may they act on the user the request names?

One dependency, `enforce`, runs on every API request. Its rule:

    A request that names a user — in the path, in the JSON body, or in the
    X-User-Id header — must be authenticated as that user, or by a role that
    may act for them. A request that names nobody needs a token unless the
    route is public.

Roles: citizen (self only), operator (a CSC/VLE worker, for citizens who
recorded consent in the operator's session), reviewer and admin (any user).
The legacy X-Admin-Secret header is honoured as an admin principal so the
existing admin tooling keeps working while it migrates to tokens.

Demo builds: a placeholder id that is not a Mongo ObjectId can use the chat
and transcription routes without a token. Real accounts always have ObjectIds,
so a placeholder can never reach a real citizen's data, and production builds
have no demo mode at all.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request

from auth import settings, tokens
from auth.store import get_store

# Routes anyone may call without a token (catalog, language, legal notice,
# stateless checks). Everything else needs identity.
PUBLIC_EXACT = {
    "/api", "/api/", "/api/analytics/status", "/api/demo/status",
    "/api/schemes", "/api/search-schemes", "/api/eligibility-check",
    "/api/dpdp/notice", "/api/dpdp/terms", "/api/dpdp/languages", "/api/dpdp/accessibility",
    "/api/dpdp/identity-documents", "/api/dpdp/grievance-officer",
    "/api/v2/schemes", "/api/v2/form-templates", "/api/forms/catalog",
    "/api/forms/catalog-states", "/api/forms/refresh-status", "/api/stt/providers",
    "/api/llm/providers", "/api/verify/fields", "/api/verify/eligibility",
    "/api/mcp/tools", "/api/kyc/methods",
}
# The KYC *method list* is public; the verification endpoints carry identity
# documents and need a signed-in caller.
PUBLIC_PREFIXES = (
    "/api/auth/", "/api/i18n/", "/api/exams", "/api/schemes/", "/api/forms/catalog/",
    "/api/v2/form-template/", "/api/kyc/methods/", "/api/discovery/portals", "/api/discovery/status",
    "/api/discovery/stats", "/api/discovery/schemes", "/api/discovery/portal-health",
)
# Chat and voice may be tried with a placeholder identity in a demo build.
DEMO_ANON_EXACT = {"/api/chat", "/api/chat/voice", "/api/transcribe", "/api/chat/reset"}
DEMO_ANON_PREFIXES = ("/api/chat/history/",)

ROLES_ANY_USER = {"admin", "reviewer"}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    sid: str = ""
    via: str = "bearer"          # bearer | admin_secret

    def can_act_for(self, user_id: str) -> bool:
        return self.user_id == user_id or self.role in ROLES_ANY_USER


def _path(request: Request) -> str:
    p = request.url.path
    return p[:-1] if len(p) > 1 and p.endswith("/") else p


def is_public(path: str) -> bool:
    return path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES)


def _demo_anon(path: str) -> bool:
    return settings.demo_mode() and (path in DEMO_ANON_EXACT or path.startswith(DEMO_ANON_PREFIXES))


async def principal_from_request(request: Request) -> Optional[Principal]:
    """The caller's identity from the bearer token, or the admin secret."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        try:
            claims = tokens.decode_access(token)
        except tokens.TokenError as e:
            raise HTTPException(status_code=e.status, detail=e.reason)
        if not await tokens.session_active(claims.sid):
            raise HTTPException(status_code=401, detail="Session revoked or expired. Please sign in again.")
        return Principal(user_id=claims.user_id, role=claims.role, sid=claims.sid)

    from config import ADMIN_SECRET
    supplied = request.headers.get("x-admin-secret", "")
    if ADMIN_SECRET and supplied and _ct_equal(supplied, ADMIN_SECRET):
        return Principal(user_id="admin", role="admin", via="admin_secret")
    return None


def _ct_equal(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


async def named_users(request: Request) -> list[str]:
    """Every user the request is about: path, header and body alike.

    All of them are checked, so a client cannot name itself in a header and
    someone else in the body.
    """
    found: list[str] = []
    pp = request.path_params or {}
    if pp.get("user_id"):
        found.append(str(pp["user_id"]))
    header = request.headers.get("x-user-id", "").strip()
    if header:
        found.append(header)
    ctype = request.headers.get("content-type", "")
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and ctype.startswith("application/json"):
        try:
            body = await request.body()           # cached by Starlette; the handler re-reads it
            if body:
                data = json.loads(body)
                if isinstance(data, dict):
                    uid = data.get("user_id")
                    if isinstance(uid, str) and uid.strip():
                        found.append(uid.strip())
        except (ValueError, UnicodeDecodeError):
            pass
    return list(dict.fromkeys(found))


async def named_user(request: Request) -> Optional[str]:
    """The first user the request names, if any (kept for callers that want one)."""
    users = await named_users(request)
    return users[0] if users else None


async def operator_may_act(operator_id: str, citizen_id: str) -> bool:
    rec = await get_store().consent_get(operator_id, citizen_id)
    return bool(rec) and rec.get("expires_at", 0) > time.time() and not rec.get("revoked")


async def authorize_subject(principal: Principal, user_id: str) -> None:
    if principal.can_act_for(user_id):
        return
    if principal.role == "operator" and await operator_may_act(principal.user_id, user_id):
        return
    raise HTTPException(status_code=403, detail="You may not act on another person's account.")


async def enforce(request: Request) -> Optional[Principal]:
    """The one rule, applied to every request."""
    if request.method == "OPTIONS":
        return None
    path = _path(request)
    principal = await principal_from_request(request)
    request.state.principal = principal

    named = await named_users(request)
    if named:
        if principal is None:
            from database import is_object_id
            if _demo_anon(path) and not any(is_object_id(n) for n in named):
                return None
            raise HTTPException(status_code=401, detail="Sign in to continue.")
        for user_id in named:
            await authorize_subject(principal, user_id)
        return principal

    if is_public(path):
        return principal
    if principal is None:
        if _demo_anon(path):
            return None
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return principal


def principal_of(request: Request) -> Principal:
    """For handlers that must have a signed-in caller (downloads, uploads)."""
    p = getattr(request.state, "principal", None)
    if p is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return p


def subject_for(request: Request, claimed: str = "") -> str:
    """The user a multipart/form request acts for.

    The global dependency cannot read a multipart body, so handlers that take
    `user_id` as a form field pass it here: it must be the caller, or someone
    the caller's role may act for; a demo placeholder passes only in a demo
    build.
    """
    p = getattr(request.state, "principal", None)
    claimed = (claimed or "").strip()
    if p is None:
        from database import is_object_id
        if claimed and _demo_anon(_path(request)) and not is_object_id(claimed):
            return claimed
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    if not claimed or claimed == p.user_id:
        return p.user_id
    if p.role in ROLES_ANY_USER:
        return claimed
    raise HTTPException(status_code=403, detail="You may not act on another person's account.")


def require_role(*roles: str):
    """A dependency factory: the caller must hold one of the roles."""
    async def _dep(request: Request) -> Principal:
        p = principal_of(request)
        if p.role not in roles:
            raise HTTPException(status_code=403, detail="This action needs a different role.")
        return p
    return _dep
