"""
XeroContactAgent

Manages supplier contacts in Xero. Looks up existing contacts and creates
new ones when a supplier is encountered for the first time.

Uses the Xero MCP server tools: list-contacts, create-contact.
"""

from google.adk.agents import LlmAgent
from google.genai import types

from accounts_payable.shared_libraries.xero_mcp_toolset import create_xero_mcp_toolset

XERO_CONTACT_INSTRUCTION = """
You are a Xero contact management specialist. Your job is to find or create
supplier contacts in Xero so that bills can be correctly assigned.

## Available MCP Tools
- **list-contacts**: Search contacts by name. Use the `searchTerm` parameter for
  case-insensitive search across Name, EmailAddress, and other fields.
- **create-contact**: Create a new supplier contact in Xero.

## Workflow

### Finding an existing contact
1. Call list-contacts with searchTerm set to the supplier name from the invoice.
2. If exactly one contact is returned, use that contact — return the ContactID.
3. If multiple contacts are returned, present the list and ask the user to confirm which one.
4. If no contacts are returned, proceed to create a new contact.

### Creating a new contact
1. Gather the required information:
   - name (required)
   - abn (if available on the invoice)
   - email, phone, address (if available)
2. Call create-contact with the supplier details.
   Set isSupplier to true.
   Pass the ABN as the taxNumber field (11 digits, no spaces).
3. Confirm the new contact was created and return the ContactID.

## Rules
- Never create duplicate contacts. Always search first.
- ABN should be stored without spaces (e.g. "12345678901" not "12 345 678 901").
- If you are uncertain which existing contact matches, ask the user — do not guess.
"""

xero_contact_agent = LlmAgent(
    name="xero_contact_agent",
    model="gemini-2.5-flash",
    generate_content_config=types.GenerateContentConfig(temperature=0),
    instruction=XERO_CONTACT_INSTRUCTION,
    tools=[
        create_xero_mcp_toolset(),
    ],
    description="Finds or creates supplier contacts in Xero, returning the ContactID needed for bill entry.",
)
