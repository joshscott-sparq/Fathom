"""OIDC providers (Google now, JumpCloud later).

Real Authorization Code flow, gated behind env config. Not exercised in the
sandbox (no client credentials / public redirect); wired so it works once
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI are set. JumpCloud
is the same OIDC shape with its own issuer + client creds.
"""

from __future__ import annotations

import os
from urllib.parse import urlencode

_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


def google_enabled() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def google_redirect_uri() -> str:
    return os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")


def google_auth_url(state: str) -> str:
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH}?{urlencode(params)}"


def exchange_google_code(code: str) -> dict:  # pragma: no cover - needs live creds
    """Exchange an auth code for the user's email + name."""
    import httpx

    token_resp = httpx.post(
        _GOOGLE_TOKEN,
        data={
            "code": code,
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]
    info = httpx.get(_GOOGLE_USERINFO, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    info.raise_for_status()
    data = info.json()
    return {"email": data["email"], "name": data.get("name", data["email"])}
