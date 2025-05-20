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
            "capture": True,
            "get": True
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


# LlmAgent(
#         model="gemini-2.0-flash-001", 
#         name='orders_handler',
#         description="Helps customers with their product orders and shipments via the PayPal API",
#         instruction=prompt.ORDERS_INSTR,
#         tools=tk.get_tools(),
#         generate_content_config=types.GenerateContentConfig(temperature=0.3),        
#     ) 

agent = Agent(
    name="paypal_checkout_helper",
    model="gemini-2.0-flash-001", 
    instruction=(
        "You are a PayPal checkout assistant. "
        "When the user wants to pay, call create_order with USD."
    ),
    tools=tk.get_tools(),
)

# ------------------------------------------------------------------ #
# 3)  Runner + session
# ------------------------------------------------------------------ #
runner  = Runner(app_name="checkout-demo",
                 agent=agent,
                 session_service=InMemorySessionService())

runner.session_service.create_session(
    app_name="checkout-demo",
    user_id="alice",
    session_id="test-session"
)

# ------------------------------------------------------------------ #
# 4)  Send user message (note the correct Content syntax)
# ------------------------------------------------------------------ #
user_msg = types.Content(
    role="user",
    parts=[types.Part(text="I want to buy a hoodie for $49.99.")]
)

for ev in runner.run(user_id="alice",
                     session_id="test-session",
                     new_message=user_msg):
    # skip streaming chunks
    if ev.partial:
        continue

    # print every final chunk or tool call/result
    if ev.get_function_calls():
        print("LLM called tool:", ev.get_function_calls())
    elif ev.get_function_responses():
        print("Tool returned:", ev.get_function_responses())
    else:
        print(f"[{ev.author}] {ev.content.parts[0].text}")