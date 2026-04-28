"""
Thin HTTP client for the Xero Accounting API (v2).

All sub-agents should import and use `XeroClient` rather than calling
`requests` directly, so authentication and error handling are consistent.

Usage:
    from accounts_payable.shared_libraries.xero_client import XeroClient

    client = XeroClient()
    contacts = client.get("Contacts", params={"where": 'Name=="Acme Corp"'})
"""

from __future__ import annotations

from typing import Any

import requests

from .xero_auth import get_access_token, get_tenant_id

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"


class XeroApiError(Exception):
    """Raised when the Xero API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Xero API error {status_code}: {message}")


class XeroClient:
    """Wrapper around the Xero Accounting REST API."""

    def __init__(self):
        self._session = requests.Session()

    def _headers(self, content_type: str = "application/json") -> dict:
        return {
            "Authorization": f"Bearer {get_access_token()}",
            "Xero-Tenant-Id": get_tenant_id(),
            "Accept": "application/json",
            "Content-Type": content_type,
        }

    def _raise_for_status(self, resp: requests.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise XeroApiError(resp.status_code, str(detail))

    # ------------------------------------------------------------------
    # Generic CRUD methods
    # ------------------------------------------------------------------

    def get(self, resource: str, resource_id: str = "", params: dict | None = None) -> dict:
        """GET /resource or /resource/{id}"""
        url = f"{XERO_API_BASE}/{resource}"
        if resource_id:
            url = f"{url}/{resource_id}"
        resp = self._session.get(url, headers=self._headers(), params=params or {}, timeout=30)
        self._raise_for_status(resp)
        return resp.json()

    def post(self, resource: str, payload: dict, params: dict | None = None) -> dict:
        """POST /resource"""
        import json
        url = f"{XERO_API_BASE}/{resource}"
        resp = self._session.post(
            url,
            headers=self._headers(),
            data=json.dumps(payload),
            params=params or {},
            timeout=30,
        )
        self._raise_for_status(resp)
        return resp.json()

    def put(self, resource: str, resource_id: str, payload: dict) -> dict:
        """PUT /resource/{id}"""
        import json
        url = f"{XERO_API_BASE}/{resource}/{resource_id}"
        resp = self._session.put(
            url,
            headers=self._headers(),
            data=json.dumps(payload),
            timeout=30,
        )
        self._raise_for_status(resp)
        return resp.json()

    def post_attachment(
        self,
        resource: str,
        resource_id: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str = "application/pdf",
    ) -> dict:
        """POST binary attachment to /resource/{id}/Attachments/{filename}"""
        url = f"{XERO_API_BASE}/{resource}/{resource_id}/Attachments/{filename}"
        headers = self._headers(content_type=mime_type)
        resp = self._session.post(url, headers=headers, data=file_bytes, timeout=60)
        self._raise_for_status(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Convenience helpers used by multiple sub-agents
    # ------------------------------------------------------------------

    def list_bank_accounts(self) -> list[dict]:
        """Return all bank accounts from the chart of accounts."""
        data = self.get("Accounts", params={"where": 'Type=="BANK"'})
        return data.get("Accounts", [])

    def get_invoice(self, invoice_id: str) -> dict:
        data = self.get("Invoices", invoice_id)
        invoices = data.get("Invoices", [])
        return invoices[0] if invoices else {}
