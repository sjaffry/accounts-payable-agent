"""
Accounts Payable Agent — Root Orchestrator

Coordinates the full AP workflow for small business clients using Xero.
Delegates to specialist sub-agents for each stage of the procedure.

Usage:
    adk web agents/accounts_payable/accounts_payable

Steps covered:
    1. Check supplier invoices         (invoice_extraction_agent)
    2. Enter the bill in Xero          (xero_contact_agent + xero_bill_agent)
    3. Attach the invoice              (xero_bill_agent)
    4. Approve the bill                (xero_bill_agent)
    5. Record payment                  (xero_payment_agent)
    6. Bank reconciliation             (reconciliation_agent)
"""

import sys
from pathlib import Path

# Ensure the package root is importable when running via `adk web`
AGENT_PKG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENT_PKG_DIR.parent))

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.tools.agent_tool import AgentTool  # noqa: E402
from google.genai import types  # noqa: E402

from .prompt import AP_ORCHESTRATOR_INSTRUCTION  # noqa: E402
from .sub_agents.invoice_extraction.agent import invoice_extraction_agent  # noqa: E402
from .sub_agents.reconciliation.agent import reconciliation_agent  # noqa: E402
from .sub_agents.xero_bill.agent import xero_bill_agent  # noqa: E402
from .sub_agents.xero_contact.agent import xero_contact_agent  # noqa: E402
from .sub_agents.xero_payment.agent import xero_payment_agent  # noqa: E402

root_agent = LlmAgent(
    name="accounts_payable_agent",
    model="gemini-2.5-flash",
    generate_content_config=types.GenerateContentConfig(temperature=0),
    instruction=AP_ORCHESTRATOR_INSTRUCTION,
    tools=[
        AgentTool(agent=invoice_extraction_agent),
        AgentTool(agent=xero_contact_agent),
        AgentTool(agent=xero_bill_agent),
        AgentTool(agent=xero_payment_agent),
        AgentTool(agent=reconciliation_agent),
    ],
)
