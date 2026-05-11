"""
Xero OAuth2 token lifecycle manager — Custom Connection (client credentials).

Xero Custom Connections use the OAuth2 client_credentials grant: no browser,
no redirect URI, no user login. The app authenticates directly with its
client ID and secret to obtain a short-lived access token (30 minutes).
Tokens are cached in-memory and re-requested automatically when expired.

Environment variables required (via .env or shell):
    XERO_CLIENT_ID      - from your Xero Custom Connection app
    XERO_CLIENT_SECRET  - from your Xero Custom Connection app
    XERO_TENANT_ID      - your Xero organisation/tenant ID
    XERO_SCOPES         - (optional) space-separated accounting scopes

Note: openid, profile, email, and offline_access are NOT valid scopes for
the client_credentials grant and are automatically excluded.
"""

import base64
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

XERO_TOKEN_URL = "https://identity.xero.com/connect/token"

# In-memory token cache — survives for the lifetime of the process.
# Safe for Agent Engine (no writable filesystem required).
_token_cache: dict = {}

# Scopes valid for the client_credentials grant (no OIDC or offline_access)
_DEFAULT_SCOPES = (
    "accounting.transactions accounting.contacts accounting.settings "
    "accounting.reports.read accounting.attachments"
)

# Scopes that are only valid for authorization_code flow — must be excluded
_UNSUPPORTED_SCOPES = {"openid", "profile", "email", "offline_access"}


def _get_scopes() -> str:
    """Return accounting scopes from XERO_SCOPES env var, filtering out any
    OIDC / offline_access scopes that are invalid for client_credentials."""
    raw = os.environ.get("XERO_SCOPES", _DEFAULT_SCOPES)
    valid = [s for s in raw.split() if s not in _UNSUPPORTED_SCOPES]
    return " ".join(valid) if valid else _DEFAULT_SCOPES


def _is_expired(tokens: dict) -> bool:
    expires_at = tokens.get("expires_at", 0)
    # Re-request 60 seconds before actual expiry
    return time.time() >= expires_at - 60


def _load_tokens() -> dict:
    return _token_cache.copy()


def _save_tokens(tokens: dict) -> None:
    _token_cache.clear()
    _token_cache.update(tokens)


def _request_token() -> dict:
    """Request a new access token using the client_credentials grant."""
    client_id = os.environ["XERO_CLIENT_ID"]
    client_secret = os.environ["XERO_CLIENT_SECRET"]

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = requests.post(
        XERO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "scope": _get_scopes(),
        },
        timeout=30,
    )
    if not resp.ok:
        raise requests.HTTPError(
            f"Token request failed {resp.status_code}: {resp.text}", response=resp
        )
    tokens = resp.json()
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 1800)
    _save_tokens(tokens)
    return tokens


def get_access_token() -> str:
    """Return a valid access token, requesting a new one if expired or missing.

    Raises:
        KeyError: if XERO_CLIENT_ID or XERO_CLIENT_SECRET are not set.
        requests.HTTPError: if the token request fails.
    """
    tokens = _load_tokens()
    if not tokens or _is_expired(tokens):
        tokens = _request_token()
    return tokens["access_token"]


def get_tenant_id() -> str:
    """Return the configured Xero tenant/organisation ID."""
    tenant_id = os.environ.get("XERO_TENANT_ID", "")
    if not tenant_id:
        raise KeyError(
            "XERO_TENANT_ID environment variable is not set. "
            "Find your tenant ID in the Xero Developer Portal under your Custom Connection app."
        )
    return tenant_id


# ---------------------------------------------------------------------------
# CLI helper: verify the connection is working
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Testing Xero Custom Connection...")
    token = get_access_token()
    print(f"Access token obtained (expires in ~30 min).")
    print(f"Tenant ID: {get_tenant_id()}")
    print("Connection OK.")
