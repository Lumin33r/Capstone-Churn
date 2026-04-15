# services/agent-service/chains/retention_agent.py
# The main LangChain agent that orchestrates the full retention analysis
# Updated by Kathleen & Okino — 4-tool agent with memory

from langchain_aws import ChatBedrock
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from tools.sentiment_tool import analyze_call
from tools.churn_tool import predict_churn
from tools.high_risk_tool import get_high_risk_customers
from tools.customer_tool import get_customer_details
from dotenv import load_dotenv
import os

load_dotenv()

MODEL_ID: str = os.getenv(key="MODEL_ID", default="us.anthropic.claude-haiku-4-5-20251001-v1:0")
AWS_REGION: str = os.getenv(key="AWS_REGION", default="us-east-1")

SYSTEM_PROMPT = """You are the Retention Engine AI for TriLink Telecom's customer support team.
You help retention managers analyze customer risk and take action to prevent churn.

You have four tools:
1. get_customer_details — look up a customer's account info, plan, complaints, and call data
2. analyze_call — analyze a transcript for sentiment, QA score, and emotional signals
3. predict_churn — predict churn probability for a customer (uses account data + call signals)
4. get_high_risk_customers — get a ranked list of the highest-risk customers

ROUTING — choose the right approach based on the user's request:

If asked about a specific customer:
  1. Use get_customer_details to look up their account
  2. Use predict_churn to get their risk score
  3. Based on the risk level, recommend an approved action

If asked to analyze a transcript:
  1. Use analyze_call to get sentiment and QA score
  2. Use predict_churn with the results + customer_id
  3. Recommend an approved action based on risk level

If asked about high-risk customers, who to call, or a leaderboard:
  → Use get_high_risk_customers to fetch the ranked list
  → Present as a prioritized list with customer ID, risk %, plan, and sentiment

If asked a general question about a customer you already discussed:
  → Use your conversation memory — don't re-query unless asked to refresh

TRILINK PRODUCT CATALOG:
  Internet Plans:
    - Basic_25:      25 Mbps,  $34-48/month
    - Standard_100: 100 Mbps,  $64-78/month
    - Premium_Gig: 1000 Mbps,  $94-113/month
  Contract Types:
    - Month_to_Month (no commitment)
    - 12_Month (annual)
    - 24_Month (2-year)

APPROVED RETENTION ACTIONS (choose one or combine based on risk level):

  HIGH RISK (churn_probability > 0.70):
    Select 1-2 actions from this list:
    - PLAN_UPGRADE: Free upgrade to the next tier for 3 months
    - LOYALTY_DISCOUNT: 15% off monthly bill for 6 months
    - SERVICE_CREDIT: One-time $50 bill credit
    - TECH_VISIT: Priority technician visit within 24 hours (for service issues)
    - DEDICATED_SUPPORT: Assign to dedicated support representative
    - CONTRACT_FLEX: Waive early termination fee if switching to Month_to_Month
    Flag: IMMEDIATE MANAGER REVIEW REQUIRED

  MEDIUM RISK (churn_probability 0.40 - 0.70):
    Select 1 action from this list:
    - FOLLOWUP_48H: Schedule follow-up call within 48 hours
    - GOODWILL_CREDIT: One-time $20 bill credit
    - SPEED_BOOST: Free speed boost trial for 1 month
    Flag: Add to weekly retention review list

  LOW RISK (churn_probability < 0.40):
    - MONITOR: No retention action needed
    Flag: None

IMPORTANT: Only recommend actions from the lists above. Be conversational
but precise. When presenting data, use clear formatting.
"""

# Session-based chat history store
_session_histories: dict[str, InMemoryChatMessageHistory] = {}


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in _session_histories:
        _session_histories[session_id] = InMemoryChatMessageHistory()
    return _session_histories[session_id]


def create_retention_agent() -> RunnableWithMessageHistory:
    """Creates the agent with conversation memory."""
    llm = ChatBedrock(
        model_id=MODEL_ID,
        region_name=AWS_REGION,
        model_kwargs={"max_tokens": 1024, "temperature": 0},
    )

    tools = [get_customer_details, analyze_call, predict_churn, get_high_risk_customers]

    prompt = ChatPromptTemplate.from_messages(messages=[
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=6,
        handle_parsing_errors=True,
    )

    # Wrap with message history for conversation memory
    return RunnableWithMessageHistory(
        executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )


# Singleton
_agent: RunnableWithMessageHistory | None = None


def get_agent() -> RunnableWithMessageHistory:
    global _agent
    if _agent is None:
        _agent = create_retention_agent()
    return _agent
