"""
Deploy the Accounts Payable Agent to Vertex AI Agent Engine.

This script uses the Vertex AI Python SDK directly, which gives explicit
control over the requirements list — more reliable than `adk deploy agent_engine`.

Usage:
    python deploy.py

The script prints the deployed resource name and numeric resource ID.
Update RESOURCE_ID in chat_app.py with the printed value.
"""

import sys

import vertexai
from vertexai.preview import reasoning_engines

from accounts_payable.agent import root_agent

# ── Configuration ────────────────────────────────────────────────────────────
PROJECT = "theta-window-344723"
REGION = "us-central1"
DISPLAY_NAME = "accounts-payable-agent"
# ─────────────────────────────────────────────────────────────────────────────

REQUIREMENTS = [
    "google-adk>=1.0.0",
    "google-cloud-aiplatform>=1.38.0",
    "vertexai>=1.38.0",
    "pydantic>=2.8.0",
    "pdfplumber>=0.10.0",
    "python-dotenv>=1.0.0",
    "requests>=2.31.0",
    "requests-oauthlib>=1.3.1",
]


def main():
    print(f"Initialising Vertex AI — project={PROJECT}, region={REGION}")
    vertexai.init(project=PROJECT, location=REGION)

    app = reasoning_engines.AdkApp(
        agent=root_agent,
        enable_tracing=False,
    )

    print(f"Deploying '{DISPLAY_NAME}' to Agent Engine …")
    remote_app = reasoning_engines.ReasoningEngine.create(
        app,
        requirements=REQUIREMENTS,
        display_name=DISPLAY_NAME,
    )

    resource_name = remote_app.resource_name
    resource_id = resource_name.split("/")[-1]

    print("\nDeployment complete!")
    print(f"  Resource name : {resource_name}")
    print(f"  Resource ID   : {resource_id}")
    print(f"\nUpdate RESOURCE_ID in chat_app.py to: {resource_id!r}")


if __name__ == "__main__":
    sys.exit(main())
