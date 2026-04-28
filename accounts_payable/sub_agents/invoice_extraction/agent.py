"""
InvoiceExtractionAgent

Reads a supplier invoice PDF (or image) and returns structured data
ready for entry into Xero.

Pipeline:
  1. classify_document  -- confirm it is an INVOICE, not a quote/remittance
  2. extract_invoice_data -- extract supplier, amounts, dates, line items
  3. validate_extraction  -- check required fields and totals consistency
"""

from google.adk.agents import LlmAgent
from google.genai import types

from .tools import classify_document, extract_invoice_data, validate_extraction

INVOICE_EXTRACTION_INSTRUCTION = """
You are an invoice extraction specialist. Your job is to read supplier invoice PDFs
and return clean, validated data for Xero entry.

## Workflow
Follow these steps IN ORDER for every invoice:

1. Call classify_document(pdf_path) to confirm the document type.
   - If document_type is NOT "INVOICE", stop and report the issue.
   - If confidence is LOW, warn the user but continue.

2. Call extract_invoice_data(pdf_path) to extract all invoice fields.

3. Call validate_extraction(extracted_data_json) with the JSON string of the extracted data.
   - If is_valid is False, report each error clearly.
   - Always report any warnings.

4. Return a consolidated summary:
   - Supplier name and ABN
   - Invoice number and dates
   - Subtotal, GST, and total
   - List of line items
   - Validation status and any issues requiring attention

## Important rules
- Always complete all three steps before responding.
- If extraction_confidence is LOW, recommend manual review.
- Be precise with amounts — never round or alter extracted figures.
- Present dates in DD/MM/YYYY format in your summary (even though internally stored as YYYY-MM-DD).
"""

invoice_extraction_agent = LlmAgent(
    name="invoice_extraction_agent",
    model="gemini-2.5-flash",
    generate_content_config=types.GenerateContentConfig(temperature=0),
    instruction=INVOICE_EXTRACTION_INSTRUCTION,
    tools=[
        classify_document,
        extract_invoice_data,
        validate_extraction,
    ],
    description="Reads a supplier invoice PDF and returns structured, validated data for Xero entry.",
)
