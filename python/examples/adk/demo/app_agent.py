import os
import sys
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from paypal_agent_toolkit.adk.toolkit import PayPalToolkit
from paypal_agent_toolkit.shared.configuration import Configuration, Context
from google.adk.agents.llm_agent import LlmAgent

# ------------------------------------------------------------------
# 1.   ADK PayPal Toolkit Setup
# ------------------------------------------------------------------
#uncomment after setting the env file
# load_dotenv()
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")

configuration = Configuration(
    actions={
        "orders": {
            "create": True,
            # "capture": True,
            # "get": True
        },
    },
    context=Context(
        sandbox=True,
    )
)

tk = PayPalToolkit(
    client_id = PAYPAL_CLIENT_ID,
    secret    = PAYPAL_SECRET,
    configuration = configuration,
)


agent = Agent(
    name="paypal_checkout_helper",
    model="gemini-2.0-flash-001", 
    instruction=(
        "You are a PayPal checkout assistant. "
        "When the user wants to pay, call create_order with USD."
    ),
    tools=tk.get_tools(),
)