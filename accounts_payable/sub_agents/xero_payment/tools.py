"""
Tools for the XeroPaymentAgent.

All payment operations are handled via the Xero MCP server tools:
  - list-invoices   (filter ACCPAY AUTHORISED to find bills to pay)
  - list-accounts   (retrieve available bank accounts)
  - create-payment  (record a payment against an approved bill)
  - list-payments   (retrieve payment confirmation)

No local Python tools are needed for this sub-agent.
"""
