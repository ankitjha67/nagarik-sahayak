"""Every authentication tunable, read from the environment when asked.

Read on demand rather than at import so a test can set a variable and see it
honoured, and so a misconfiguration is reported at the moment it matters with
a message that names the variable.
"""
from __future__ import annotations

import logging
import os
import secrets

logger = logging.getLogger(__name__)

_EPHEMERAL_SECRET: str | None = None


def app_env() -> str:
    return os.environ.get("APP_ENV", "development").strip().lower()


def is_production() -> bool:
    return app_env() in ("production", "prod")


def demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "").lower() in ("true", "1", "yes") and not is_production()


def jwt_secret() -> str:
    """The key that signs access tokens.

    Production refuses to start without one. Development gets a per-process
    random key, so a token never survives a restart and nobody ships the
    placeholder by accident.
    """
    global _EPHEMERAL_SECRET
    configured = os.environ.get("AUTH_JWT_SECRET", "").strip()
    if configured:
        if len(configured) < 32:
            raise RuntimeError("AUTH_JWT_SECRET must be at least 32 characters")
        return configured
    if is_production():
        raise RuntimeError("AUTH_JWT_SECRET is required in production")
    if _EPHEMERAL_SECRET is None:
        _EPHEMERAL_SECRET = secrets.token_hex(32)
        logger.warning("AUTH_JWT_SECRET not set: using an ephemeral key for this process")
    return _EPHEMERAL_SECRET


def access_ttl_seconds() -> int:
    """At most 60 minutes, which is what NeGD's API criteria allow."""
    minutes = int(os.environ.get("AUTH_ACCESS_TTL_MIN", "30"))
    return max(1, min(minutes, 60)) * 60


def refresh_ttl_seconds() -> int:
    days = int(os.environ.get("AUTH_REFRESH_TTL_DAYS", "30"))
    return max(1, min(days, 90)) * 86400


def otp_ttl_seconds() -> int:
    return int(os.environ.get("OTP_TTL_SECONDS", "300"))


def otp_max_attempts() -> int:
    return int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))


def otp_lock_seconds() -> int:
    return int(os.environ.get("OTP_LOCK_SECONDS", "900"))


def otp_mock_code() -> str:
    """A fixed code, only ever outside production.

    Explicit OTP_MOCK_CODE wins; a demo build defaults to 123456 so the demo
    flows keep working. Production always returns "", meaning a real code.
    """
    if is_production():
        return ""
    explicit = os.environ.get("OTP_MOCK_CODE", "").strip()
    if explicit:
        return explicit
    return "123456" if demo_mode() else ""


def _phones(var: str) -> set[str]:
    raw = os.environ.get(var, "")
    return {p.strip() for p in raw.replace(";", ",").split(",") if p.strip()}


def role_for_phone(phone: str) -> str:
    """Bootstrap roles from the environment: admins, reviewers, operators.

    A directory-backed role store can replace this later; the token carries
    the role either way.
    """
    if phone in _phones("AUTH_ADMIN_PHONES"):
        return "admin"
    if phone in _phones("AUTH_REVIEWER_PHONES"):
        return "reviewer"
    if phone in _phones("AUTH_OPERATOR_PHONES"):
        return "operator"
    return "citizen"


def admin_mfa_required() -> bool:
    return os.environ.get("AUTH_ADMIN_MFA", "true").lower() not in ("false", "0", "no")


def trusted_proxies() -> set[str]:
    return _phones("TRUSTED_PROXIES")


def max_json_body_bytes() -> int:
    return int(os.environ.get("MAX_JSON_BODY_BYTES", str(256 * 1024)))


def max_upload_body_bytes() -> int:
    return int(os.environ.get("MAX_UPLOAD_BODY_BYTES", str(25 * 1024 * 1024)))


def api_rate_limit_per_minute() -> int:
    return int(os.environ.get("API_RATE_LIMIT_PER_MINUTE", "300"))
