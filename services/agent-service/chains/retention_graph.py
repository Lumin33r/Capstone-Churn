# services/agent-service/chains/retention_graph.py
# LangGraph-based retention analysis pipeline
# Replaces AgentExecutor with explicit state graph + conditional routing

import os
from typing import TypedDict, Literal, Annotated
from operator import add

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from tools.qa_tool import analyze_call
from tools.churn_tool import predict_churn
from tools.high_risk_tool import get_high_risk_customers
from tools.customer_tool import get_customer_details
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

SYSTEM_MESSAGE = """You are the Retention Engine AI for TriLink Telecom.
You help retention managers analyze customer risk and take action.

WORKFLOW:
1. When asked about a customer, use get_customer_details first to understand their account
2. Then use predict_churn to get the risk score
3. Based on the risk level, select the BEST action from the approved list below
4. Explain WHY you chose that specific action based on the customer's situation

When asked for high-risk customers, use get_high_risk_customers.
When given a transcript, use analyze_call first, then predict_churn.

TRILINK PRODUCT CATALOG:
  - Basic_25: 25 Mbps, $34-48/month
  - Standard_100: 100 Mbps, $64-78/month
  - Premium_Gig: 1000 Mbps, $94-113/month

APPROVED RETENTION ACTIONS — you MUST select from these lists only:

  HIGH RISK (churn_probability > 0.70):
    - PLAN_UPGRADE: Free upgrade to next tier for 3 months
    - LOYALTY_DISCOUNT: 15% off monthly bill for 6 months
    - SERVICE_CREDIT: One-time $50 bill credit
    - TECH_VISIT: Priority technician visit within 24 hours
    - DEDICATED_SUPPORT: Assign dedicated support representative
    - CONTRACT_FLEX: Waive early termination fee
    Select 1-2 actions. Flag: IMMEDIATE MANAGER REVIEW REQUIRED.

  MEDIUM RISK (churn_probability 0.40 - 0.70):
    - FOLLOWUP_48H: Schedule follow-up call within 48 hours
    - GOODWILL_CREDIT: One-time $20 bill credit
    - SPEED_BOOST: Free speed boost trial for 1 month
    Select 1 action.

  LOW RISK (churn_probability < 0.40):
    - MONITOR: No retention action needed

Always end your response with:
---
Action: [ACTION_CODE]
Reason: [1 sentence why this action fits this customer]
---

Be conversational but precise. Reference the customer's specific issues."""


# ── State Definition ──────────────────────────────────────────────────

class RetentionState(TypedDict):
    """State that flows through the graph."""
    messages: Annotated[list, add]  # conversation history
    request_type: str  # "customer_query", "high_risk", "transcript", "general"
    customer_id: str | None
    has_transcript: bool


# ── LLM + Tools ──────────────────────────────────────────────────────

tools = [get_customer_details, analyze_call, predict_churn, get_high_risk_customers]

llm = ChatBedrock(
    model=MODEL_ID,
    region=AWS_REGION,
    model_kwargs={"max_tokens": 1024, "temperature": 0},
)

llm_with_tools = llm.bind_tools(tools)


# ── Node Functions ────────────────────────────────────────────────────

def classify_request(state: RetentionState) -> RetentionState:
    """Classify the user's request to determine routing."""
    last_message = state["messages"][-1].content.lower() if state["messages"] else ""

    # Detect customer ID
    import re
    cid_match = re.search(r"C\d{8}", state["messages"][-1].content if state["messages"] else "")
    customer_id = cid_match.group(0) if cid_match else state.get("customer_id")

    # Detect request type
    if any(kw in last_message for kw in ["high risk", "leaderboard", "top customer", "who should", "at risk"]):
        request_type = "high_risk"
    elif any(kw in last_message for kw in ["transcript", "call recording", "conversation:"]):
        request_type = "transcript"
        has_transcript = True
    elif customer_id:
        request_type = "customer_query"
    else:
        request_type = "general"

    return {
        "messages": [],  # no new messages from classifier
        "request_type": request_type,
        "customer_id": customer_id,
        "has_transcript": state.get("has_transcript", False) or ("transcript" in last_message),
    }


def call_model(state: RetentionState) -> RetentionState:
    """Call the LLM with tools bound. It decides which tools to use."""
    system = SystemMessage(content=SYSTEM_MESSAGE)
    response = llm_with_tools.invoke([system] + state["messages"])
    return {"messages": [response], "request_type": state["request_type"],
            "customer_id": state.get("customer_id"), "has_transcript": state.get("has_transcript", False)}


def handle_tool_response(state: RetentionState) -> RetentionState:
    """Process tool results and call LLM again for final response."""
    system = SystemMessage(content=SYSTEM_MESSAGE)
    response = llm_with_tools.invoke([system] + state["messages"])
    return {"messages": [response], "request_type": state["request_type"],
            "customer_id": state.get("customer_id"), "has_transcript": state.get("has_transcript", False)}


# ── Routing Functions ─────────────────────────────────────────────────

def should_use_tools(state: RetentionState) -> Literal["tools", "end"]:
    """Check if the LLM wants to call a tool."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "end"


def after_tools(state: RetentionState) -> Literal["model", "end"]:
    """After tool execution, go back to model for interpretation."""
    return "model"


# ── Build Graph ───────────────────────────────────────────────────────

def build_retention_graph():
    """Build the LangGraph workflow."""

    tool_node = ToolNode(tools)

    graph = StateGraph(RetentionState)

    # Add nodes
    graph.add_node("classify", classify_request)
    graph.add_node("model", call_model)
    graph.add_node("tools", tool_node)
    graph.add_node("respond", handle_tool_response)

    # Entry point
    graph.set_entry_point("classify")

    # Classify → Model (always go to model after classification)
    graph.add_edge("classify", "model")

    # Model → Tools or End
    graph.add_conditional_edges("model", should_use_tools, {
        "tools": "tools",
        "end": END,
    })

    # Tools → Respond (model interprets tool results)
    graph.add_conditional_edges("tools", after_tools, {
        "model": "respond",
        "end": END,
    })

    # Respond → Tools or End (may need more tool calls)
    graph.add_conditional_edges("respond", should_use_tools, {
        "tools": "tools",
        "end": END,
    })

    return graph.compile(checkpointer=MemorySaver())


# ── Singleton ─────────────────────────────────────────────────────────

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_retention_graph()
    return _graph


def invoke_graph(user_message: str, customer_id: str | None = None, session_id: str = "default") -> str:
    """Invoke the graph with conversation memory via thread_id."""
    graph = get_graph()

    initial_state: RetentionState = {
        "messages": [HumanMessage(content=user_message)],
        "request_type": "",
        "customer_id": customer_id,
        "has_transcript": False,
    }

    config = {"configurable": {"thread_id": session_id}}
    result = graph.invoke(initial_state, config=config)

    # Extract the last AI message
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content

    return "I wasn't able to process that request. Please try again."
