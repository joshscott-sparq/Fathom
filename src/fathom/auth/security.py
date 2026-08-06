"""Password hashing and JWT tokens.

Passwords use PBKDF2-HMAC-SHA256 (stdlib, salted, high iteration count) stored as
`pbkdf2_sha256$iterations$salt_hex$hash_hex`. Tokens are JWT (HS256) signed with
FATHOM_SECRET. A dev fallback secret is used when the env var is unset, with
a warning — production MUST set FATHOM_SECRET.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import warnings
from datetime import datetime, timedelta, timezone

import jwt

_PBKDF2_ITERATIONS = 200_000
_ALGO = "HS256"
_TOKEN_TTL_HOURS = 12

_DEV_SECRET = "dev-only-insecure-secret-change-me"


def _secret() -> str:
    secret = os.environ.get("FATHOM_SECRET")
    if not secret:
        warnings.warn(
            "FATHOM_SECRET is not set; using an insecure dev secret. "
            "Set it in production.",
            stacklevel=2,
        )
        return _DEV_SECRET
    return secret


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def create_access_token(*, user_id: str, email: str, role: str, ttl_hours: int = _TOKEN_TTL_HOURS) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def decode_access_token(token: str) -> dict:
    """Return the token claims, or raise jwt.PyJWTError on invalid/expired."""
    return jwt.decode(token, _secret(), algorithms=[_ALGO])
