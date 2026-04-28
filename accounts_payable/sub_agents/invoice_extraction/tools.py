"""
Tools for the InvoiceExtractionAgent.

Uses Gemini multimodal capabilities to:
  1. classify_document    -- confirm the PDF is an invoice (not a quote/remittance)
  2. extract_invoice_data -- pull structured fields from the PDF
  3. validate_extraction  -- sanity-check the extracted data before Xero entry
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pdfplumber
from google import genai
from google.genai import types as genai_types

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MODEL_NAME = "gemini-2.5-flash"


def _pdf_to_base64(pdf_path: str) -> str:
    """Return the raw PDF bytes as a base64 string for Gemini."""
    return base64.b64encode(Path(pdf_path).read_bytes()).decode()


def _pdf_to_text(pdf_path: str) -> str:
    """Extract plain text from each page of the PDF (fallback for text-based PDFs)."""
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _call_gemini(prompt: str, pdf_path: str) -> str:
    """Send the PDF + prompt to Gemini and return the raw text response."""
    client = genai.Client()  # reads GOOGLE_API_KEY from environment
    pdf_bytes = Path(pdf_path).read_bytes()
    response = client.models.generate_content(
        model=_MODEL_NAME,
        contents=[
            genai_types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ],
    )
    return response.text.strip()


def _extract_json(text: str) -> dict:
    """Extract the first JSON object or array from a Gemini response string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model response: {text[:300]}")
    return json.loads(match.group())


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def classify_document(pdf_path: str) -> dict:
    """Classify the document type of a PDF.

    Confirms whether the document is an invoice vs. quote, remittance,
    receipt, or unrecognised document.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        dict with keys:
            - document_type: "INVOICE" | "QUOTE" | "RECEIPT" | "REMITTANCE" | "CREDIT_NOTE" | "UNKNOWN"
            - confidence: "HIGH" | "MEDIUM" | "LOW"
            - reason: short explanation
    """
    prompt = """You are a document classification expert.

Examine this document and classify it. Respond ONLY with valid JSON matching this schema:
{
  "document_type": "<INVOICE|QUOTE|RECEIPT|REMITTANCE|CREDIT_NOTE|UNKNOWN>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "reason": "<one sentence explaining your classification>"
}

- INVOICE: a request for payment from a supplier for goods/services already delivered
- QUOTE: a price estimate, not yet a request for payment
- RECEIPT: proof of payment already made
- REMITTANCE: a payment advice/notification
- CREDIT_NOTE: a document reducing a liability
"""
    try:
        response_text = _call_gemini(prompt, pdf_path)
        return _extract_json(response_text)
    except Exception as e:
        return {
            "document_type": "UNKNOWN",
            "confidence": "LOW",
            "reason": f"Classification failed: {e}",
        }


def extract_invoice_data(pdf_path: str) -> dict:
    """Extract structured invoice fields from a PDF using Gemini.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        dict with keys:
            - supplier_name: str
            - supplier_abn: str or null
            - invoice_number: str
            - invoice_date: str (YYYY-MM-DD)
            - due_date: str (YYYY-MM-DD) or null
            - currency: str (default "AUD")
            - line_items: list of {description, quantity, unit_price, amount}
            - subtotal: float (ex-GST)
            - gst_amount: float
            - total: float (inc-GST)
            - payment_terms: str or null
            - notes: str or null
            - extraction_confidence: "HIGH" | "MEDIUM" | "LOW"
    """
    prompt = """You are an expert accounts payable data extractor for Australian businesses.

Extract all invoice data from this document. Respond ONLY with valid JSON matching this exact schema:
{
  "supplier_name": "<string>",
  "supplier_abn": "<string or null>",
  "invoice_number": "<string>",
  "invoice_date": "<YYYY-MM-DD or null>",
  "due_date": "<YYYY-MM-DD or null>",
  "currency": "<string, default AUD>",
  "line_items": [
    {
      "description": "<string>",
      "quantity": <number>,
      "unit_price": <number>,
      "amount": <number>
    }
  ],
  "subtotal": <number>,
  "gst_amount": <number>,
  "total": <number>,
  "payment_terms": "<string or null>",
  "notes": "<string or null>",
  "extraction_confidence": "<HIGH|MEDIUM|LOW>"
}

Rules:
- All monetary amounts must be numbers (no currency symbols).
- subtotal is the amount BEFORE GST.
- gst_amount is the GST component (for AU invoices this is typically 10% of subtotal).
- total = subtotal + gst_amount.
- Dates must be in YYYY-MM-DD format.
- If a field is not present, use null.
- extraction_confidence should reflect how clearly the document presents the data.
"""
    try:
        response_text = _call_gemini(prompt, pdf_path)
        return _extract_json(response_text)
    except Exception as e:
        return {
            "supplier_name": None,
            "supplier_abn": None,
            "invoice_number": None,
            "invoice_date": None,
            "due_date": None,
            "currency": "AUD",
            "line_items": [],
            "subtotal": None,
            "gst_amount": None,
            "total": None,
            "payment_terms": None,
            "notes": None,
            "extraction_confidence": "LOW",
            "extraction_error": str(e),
        }


def validate_extraction(extracted_data_json: str) -> dict:
    """Validate extracted invoice data for completeness and consistency.

    Checks:
      - All required fields are present and non-null
      - GST amount is approximately 10% of subtotal (±2% tolerance)
      - total ≈ subtotal + gst_amount
      - Line items sum ≈ subtotal

    Args:
        extracted_data_json: JSON string of extracted invoice data
                             (as returned by extract_invoice_data).

    Returns:
        dict with keys:
            - is_valid: bool
            - errors: list of error strings (empty if valid)
            - warnings: list of warning strings
    """
    try:
        data = json.loads(extracted_data_json) if isinstance(extracted_data_json, str) else extracted_data_json
    except json.JSONDecodeError as e:
        return {"is_valid": False, "errors": [f"Invalid JSON: {e}"], "warnings": []}

    errors = []
    warnings = []

    required_fields = ["supplier_name", "invoice_number", "invoice_date", "total"]
    for field in required_fields:
        if not data.get(field):
            errors.append(f"Missing required field: {field}")

    subtotal = data.get("subtotal")
    gst = data.get("gst_amount")
    total = data.get("total")

    if subtotal is not None and gst is not None and total is not None:
        # Check total = subtotal + gst
        expected_total = round(subtotal + gst, 2)
        if abs(expected_total - total) > 0.05:
            errors.append(
                f"Total mismatch: subtotal ({subtotal}) + gst ({gst}) = {expected_total}, "
                f"but total is {total}"
            )

        # Check GST ≈ 10% of subtotal (only warn, some items may be GST-free)
        if subtotal > 0:
            gst_rate = round(gst / subtotal, 3)
            if gst_rate < 0.0 or gst_rate > 0.15:
                warnings.append(
                    f"Unusual GST rate: {gst_rate:.1%} of subtotal. "
                    "Verify the invoice includes GST-free items or is from an overseas supplier."
                )

    # Check line items sum
    line_items = data.get("line_items", [])
    if line_items and subtotal is not None:
        line_total = round(sum(item.get("amount", 0) for item in line_items), 2)
        if abs(line_total - subtotal) > 0.05:
            warnings.append(
                f"Line items sum ({line_total}) does not match subtotal ({subtotal}). "
                "Check for missing or partial line items."
            )

    if data.get("extraction_confidence") == "LOW":
        warnings.append(
            "Extraction confidence is LOW. Manual review recommended before approving."
        )

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
