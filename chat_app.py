"""
Streamlit chat interface for the Accounts Payable Agent on Vertex AI Agent Engine.

Setup:
    pip install streamlit google-cloud-aiplatform

Configure the three constants below, then run:
    streamlit run chat_app.py
"""

import streamlit as st
import vertexai
from vertexai.preview import reasoning_engines

# ── Configuration ────────────────────────────────────────────────────────────
PROJECT = "theta-window-344723"       # GCP project ID
REGION = "us-central1"             # Agent Engine region
RESOURCE_ID = "your-resource-id"   # numeric ID from `adk deploy agent_engine` output
# ─────────────────────────────────────────────────────────────────────────────

RESOURCE_NAME = (
    f"projects/{PROJECT}/locations/{REGION}/reasoningEngines/{RESOURCE_ID}"
)

st.set_page_config(page_title="Accounts Payable Agent", page_icon="🧾")
st.title("Accounts Payable Agent")


@st.cache_resource
def get_agent():
    vertexai.init(project=PROJECT, location=REGION)
    return reasoning_engines.ReasoningEngine(RESOURCE_NAME)


agent = get_agent()

# Create a session once per browser session
if "session_id" not in st.session_state:
    session = agent.create_session(user_id="streamlit-user")
    st.session_state.session_id = session["id"]

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
if prompt := st.chat_input("e.g. Process the invoice at invoices/acme_invoice_001.pdf"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Working..."):
            response = agent.query(
                user_id="streamlit-user",
                session_id=st.session_state.session_id,
                message=prompt,
            )
        reply = response.get("output", str(response))
        st.write(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
