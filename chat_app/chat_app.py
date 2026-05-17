"""
Streamlit chat interface for the Accounts Payable Agent on Vertex AI Agent Engine.

Setup:
    pip install streamlit google-cloud-aiplatform

Configure the three constants below, then run:
    streamlit run chat_app.py
"""

import streamlit as st
import streamlit_authenticator as stauth
import vertexai
import yaml
from yaml.loader import SafeLoader
try:
    from vertexai import agent_engines
except ImportError:
    from vertexai.preview import reasoning_engines as agent_engines

# ── Configuration ────────────────────────────────────────────────────────────
PROJECT = "theta-window-344723"       # GCP project ID
REGION = "us-central1"             # Agent Engine region
RESOURCE_ID = "3302717975315873792"   # numeric ID from `adk deploy agent_engine` output
# ─────────────────────────────────────────────────────────────────────────────

RESOURCE_NAME = (
    f"projects/{PROJECT}/locations/{REGION}/reasoningEngines/{RESOURCE_ID}"
)

st.set_page_config(page_title="Accounts Payable Agent", page_icon="🧾")

# ── Authentication ────────────────────────────────────────────────────────────
with open("auth_config.yaml") as f:
    auth_cfg = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    auth_cfg["credentials"],
    auth_cfg["cookie"]["name"],
    auth_cfg["cookie"]["key"],
    auth_cfg["cookie"]["expiry_days"],
)

authenticator.login()

if st.session_state.get("authentication_status") is False:
    st.error("Incorrect username or password")
    st.stop()
elif st.session_state.get("authentication_status") is None:
    st.warning("Please enter your username and password")
    st.stop()

# Logged in — show logout button in sidebar
authenticator.logout("Logout", "sidebar")
# ─────────────────────────────────────────────────────────────────────────────

st.title("Accounts Payable Agent")


@st.cache_resource
def get_agent():
    vertexai.init(project=PROJECT, location=REGION)
    return agent_engines.get(RESOURCE_NAME)


try:
    agent = get_agent()
except Exception as e:
    st.error(f"Failed to connect to Agent Engine: {e}")
    st.stop()

# Create a session once per browser session
if "session_id" not in st.session_state:
    try:
        session = agent.create_session(user_id="streamlit-user")
        # create_session may return a dict or an object depending on SDK version
        if isinstance(session, dict):
            st.session_state.session_id = session["id"]
        else:
            st.session_state.session_id = session.id
    except Exception as e:
        st.error(f"Failed to create session: {e}")
        st.stop()

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
            try:
                reply = ""
                for event in agent.stream_query(
                    user_id="streamlit-user",
                    session_id=st.session_state.session_id,
                    message=prompt,
                ):
                    if isinstance(event, dict):
                        # ADK final turn has "output" key
                        if "output" in event:
                            reply = event["output"]
                        # Accumulate text chunks if streamed as "content"
                        elif "content" in event:
                            parts = event["content"].get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    reply += part["text"]
                if not reply:
                    reply = "(No response received)"
            except Exception as e:
                reply = f"Error: {e}"
        st.write(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
