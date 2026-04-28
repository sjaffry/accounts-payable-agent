"""
Tools for the ReconciliationAgent.

Local Python tools (direct Xero API calls):
  - get_unreconciled_transactions -- list unreconciled SPEND transactions
    (MCP list-bank-transactions does not support IsReconciled filter)
  - suggest_matches               -- local fuzzy matching logic; no Xero API
  - reconcile_transaction         -- marks a bank transaction as IsReconciled=True
    (MCP update-bank-transaction does not support the IsReconciled field)

The following operation is handled via the Xero MCP server:
  - create-bank-transaction -- create a Spend Money transaction for
    unmatched bank transactions (direct expenses)
"""

from __future__ import annotations

import json

from accounts_payable.shared_libraries.xero_client import XeroClient


def get_unreconciled_transactions(bank_account_id: str) -> dict:
    """Retrieve unreconciled bank feed transactions for a given bank account.

    Uses the Xero API directly because the MCP list-bank-transactions tool
    does not support filtering by IsReconciled.

    Args:
        bank_account_id: Xero AccountID for the bank account.

    Returns:
        dict with keys:
            - transactions: list of [{BankTransactionID, Date, Amount,
              Description, Reference, IsReconciled}]
            - count: int
    """
    client = XeroClient()
    try:
        data = client.get(
            "BankTransactions",
            params={
                "where": f'BankAccount.AccountID=="{bank_account_id}" AND IsReconciled==false AND Type=="SPEND"',
                "order": "Date DESC",
            },
        )
        txns = data.get("BankTransactions", [])
        simplified = [
            {
                "BankTransactionID": t.get("BankTransactionID"),
                "Date": t.get("Date"),
                "Amount": t.get("Total"),
                "Description": t.get("Narrative", ""),
                "Reference": t.get("Reference", ""),
                "IsReconciled": t.get("IsReconciled", False),
            }
            for t in txns
        ]
        return {"transactions": simplified, "count": len(simplified)}
    except Exception as e:
        return {"transactions": [], "count": 0, "error": str(e)}


def suggest_matches(transaction_json: str) -> dict:
    """Suggest matching bills or payments for an unreconciled bank transaction.

    Searches authorised bills and recorded payments by amount and approximate
    date to surface likely matches for the accountant to confirm.

    Args:
        transaction_json: JSON string with transaction fields:
            {
              "Amount": <float>,
              "Date": "<YYYY-MM-DD>",
              "Description": "<str>",
              "Reference": "<str>"
            }

    Returns:
        dict with keys:
            - bill_matches: list of matching bills [{InvoiceID, InvoiceNumber,
              ContactName, AmountDue, DueDate, match_score}]
            - payment_matches: list of matching payments [{PaymentID, Amount,
              Date, InvoiceNumber, ContactName, match_score}]
    """
    try:
        txn = json.loads(transaction_json) if isinstance(transaction_json, str) else transaction_json
    except json.JSONDecodeError as e:
        return {"bill_matches": [], "payment_matches": [], "error": f"Invalid JSON: {e}"}

    amount = abs(float(txn.get("Amount", 0)))
    description = (txn.get("Description", "") + " " + txn.get("Reference", "")).lower()

    client = XeroClient()
    bill_matches = []
    payment_matches = []

    # Search bills with matching amount
    try:
        data = client.get(
            "Invoices",
            params={
                "where": f'Type=="ACCPAY" AND AmountDue>={amount * 0.99} AND AmountDue<={amount * 1.01}',
            },
        )
        for inv in data.get("Invoices", []):
            contact_name = inv.get("Contact", {}).get("Name", "").lower()
            score = "HIGH" if contact_name and contact_name in description else "MEDIUM"
            bill_matches.append({
                "InvoiceID": inv.get("InvoiceID"),
                "InvoiceNumber": inv.get("InvoiceNumber"),
                "ContactName": inv.get("Contact", {}).get("Name"),
                "AmountDue": inv.get("AmountDue"),
                "DueDate": inv.get("DueDate"),
                "match_score": score,
            })
    except Exception:
        pass

    # Search payments with matching amount
    try:
        data = client.get(
            "Payments",
            params={
                "where": f'Amount>={amount * 0.99} AND Amount<={amount * 1.01} AND IsReconciled==false',
            },
        )
        for pmt in data.get("Payments", []):
            payment_matches.append({
                "PaymentID": pmt.get("PaymentID"),
                "Amount": pmt.get("Amount"),
                "Date": pmt.get("Date"),
                "InvoiceNumber": pmt.get("Invoice", {}).get("InvoiceNumber"),
                "ContactName": pmt.get("Invoice", {}).get("Contact", {}).get("Name"),
                "match_score": "HIGH",
            })
    except Exception:
        pass

    # Sort: HIGH matches first
    bill_matches.sort(key=lambda x: 0 if x["match_score"] == "HIGH" else 1)

    return {"bill_matches": bill_matches, "payment_matches": payment_matches}


def reconcile_transaction(bank_transaction_id: str, invoice_id: str) -> dict:
    """Reconcile a bank transaction against a Xero invoice/bill.

    Marks the bank transaction as reconciled by setting IsReconciled=True.
    Uses the Xero API directly because the MCP update-bank-transaction tool
    does not support the IsReconciled field.

    Args:
        bank_transaction_id: Xero BankTransactionID of the unreconciled bank transaction.
        invoice_id: Xero InvoiceID of the bill being matched.

    Returns:
        dict with keys:
            - success: bool
            - BankTransactionID: str
            - IsReconciled: bool
            - error: str (if not success)
    """
    client = XeroClient()
    try:
        result = client.put(
            "BankTransactions",
            bank_transaction_id,
            {
                "BankTransactionID": bank_transaction_id,
                "IsReconciled": True,
            },
        )
        txns = result.get("BankTransactions", [{}])
        txn = txns[0] if txns else {}
        return {
            "success": True,
            "BankTransactionID": txn.get("BankTransactionID"),
            "IsReconciled": txn.get("IsReconciled", False),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
