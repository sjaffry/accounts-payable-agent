"""
Tools for the XeroBillAgent.

Local Python tools (direct Xero API calls):
  - map_account_code     -- assign a Xero account code to each line item (local logic)
  - attach_invoice_pdf   -- upload the source PDF to the Xero bill (no MCP equivalent)

The following operations are handled via the Xero MCP server:
  - create-invoice       -- POST a draft ACCPAY invoice in Xero
  - update-invoice       -- move a draft bill to AUTHORISED (Bills to Pay)
  - list-invoices        -- retrieve current bill status from Xero
"""

from __future__ import annotations

import json
from pathlib import Path

from ...shared_libraries.xero_client import XeroClient

_CHART_PATH = Path(__file__).resolve().parent.parent.parent / "shared_libraries" / "chart_of_accounts.json"
_chart: dict | None = None


def _load_chart() -> dict:
    global _chart
    if _chart is None:
        with open(_CHART_PATH) as f:
            _chart = json.load(f)
    return _chart


# ---------------------------------------------------------------------------
# Tool: map_account_code
# ---------------------------------------------------------------------------


def map_account_code(description: str) -> dict:
    """Assign a Xero account code and tax type to a line item description.

    Performs deterministic keyword matching against chart_of_accounts.json.
    The LlmAgent (XeroBillAgent) should call this for each line item and
    override the result if domain context makes a different code appropriate.

    Args:
        description: Line item description text (e.g. "Printer paper x 5 reams").

    Returns:
        dict with keys:
            - account_code: str (e.g. "420")
            - account_name: str (e.g. "Office Supplies")
            - tax_type: str ("INPUT" for GST on Expenses, "NONE" for no GST)
            - tax_display_name: str
            - match_method: "keyword" | "default"
    """
    chart = _load_chart()
    desc_lower = description.lower()

    for account in chart["accounts"]:
        for kw in account["keywords"]:
            if kw in desc_lower:
                tax_info = chart["tax_rates"].get(account["tax_type"], {})
                return {
                    "account_code": account["account_code"],
                    "account_name": account["account_name"],
                    "tax_type": account["tax_type"],
                    "tax_display_name": tax_info.get("display_name", ""),
                    "match_method": "keyword",
                }

    default = chart["default"]
    tax_info = chart["tax_rates"].get(default["tax_type"], {})
    return {
        "account_code": default["account_code"],
        "account_name": default["account_name"],
        "tax_type": default["tax_type"],
        "tax_display_name": tax_info.get("display_name", ""),
        "match_method": "default",
    }


# ---------------------------------------------------------------------------
# Tool: attach_invoice_pdf
# ---------------------------------------------------------------------------


def attach_invoice_pdf(xero_invoice_id: str, pdf_path: str) -> dict:
    """Attach the source PDF to a Xero bill for audit trail purposes.

    This uses the Xero Attachments API directly (not available via MCP server).

    Args:
        xero_invoice_id: The Xero InvoiceID (UUID) of the bill.
        pdf_path: Absolute or relative path to the invoice PDF.

    Returns:
        dict with keys:
            - success: bool
            - AttachmentID: str (if success)
            - FileName: str
            - error: str (if not success)
    """
    pdf = Path(pdf_path)
    if not pdf.exists():
        return {"success": False, "error": f"File not found: {pdf_path}"}

    client = XeroClient()
    try:
        file_bytes = pdf.read_bytes()
        result = client.post_attachment(
            resource="Invoices",
            resource_id=xero_invoice_id,
            filename=pdf.name,
            file_bytes=file_bytes,
            mime_type="application/pdf",
        )
        attachments = result.get("Attachments", [{}])
        attachment = attachments[0] if attachments else {}
        return {
            "success": True,
            "AttachmentID": attachment.get("AttachmentID"),
            "FileName": attachment.get("FileName"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
