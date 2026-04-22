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

from tools.sentiment_tool import analyze_call
from tools.churn_tool import predict_churn
from tools.high_risk_tool import get_high_risk_customers
from tools.customer_tool import get_customer_details
from tools.transcript_tool import get_transcripts
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

GATHERER_PROMPT = """You are the Data Gathering Agent for the TriLink Telecom Retention Engine.
Your job is to collect all relevant customer data by calling the appropriate tools.

When a user asks about a customer:
1. ALWAYS call get_customer_details to get their account information
2. If a transcript is provided OR the customer has call_transcript data, FIRST call analyze_call
   to get the enriched sentiment fields (qa_score, sentiment, emotion_frustration,
   emotion_anger, sentiment_shift, escalation_flag, resolution_flag)
3. ALWAYS call predict_churn. If you have enriched sentiment from step 2, PASS THOSE VALUES
   into predict_churn as arguments. This ensures the churn prediction uses the current call's
   sentiment, not stale synthetic defaults.
4. If asked about high-risk customers, call get_high_risk_customers
5. If asked about a customer's call history or transcripts, call get_transcripts

CRITICAL: When you call analyze_call, save the returned values and pass them to predict_churn:
  - qa_score from analyze_call → qa_score parameter of predict_churn
  - sentiment from analyze_call → sentiment parameter of predict_churn
  - emotion_frustration → emotion_frustration parameter
  - emotion_anger → emotion_anger parameter
  - sentiment_shift → sentiment_shift parameter
  - escalation_flag (true/false) → escalation_flag parameter (1 or 0)
  - resolution_flag (true/false) → resolution_flag parameter (1 or 0)

You MUST call tools to gather data. Do not try to answer without data.
After gathering data, provide ONLY a brief factual summary of the data you collected.
DO NOT recommend actions, DO NOT suggest retention strategies, DO NOT provide analysis.
Just state the facts — the Retention Strategist will handle recommendations."""

STRATEGIST_PROMPT = """You are the Retention Strategist for TriLink Telecom.
You receive customer data and churn analysis from the Data Gathering Agent.
Your job is to evaluate the situation and recommend a specific retention action.

TRILINK PRODUCT CATALOG:
  - Basic_25: 25 Mbps, $34-48/month
  - Standard_100: 100 Mbps, $64-78/month
  - Premium_Gig: 1000 Mbps, $94-113/month

APPROVED RETENTION ACTIONS:
  HIGH RISK (>70%): PLAN_UPGRADE, LOYALTY_DISCOUNT, SERVICE_CREDIT, TECH_VISIT, DEDICATED_SUPPORT, CONTRACT_FLEX
  MEDIUM RISK (40-70%): FOLLOWUP_48H, GOODWILL_CREDIT, SPEED_BOOST
  LOW RISK (<40%): MONITOR

CRITICAL CONSTRAINTS (apply to every response):

1. Action codes are STRICT. The "Action:" field MUST contain exactly ONE code
   from the APPROVED RETENTION ACTIONS list above. Do NOT invent new codes such
   as "EXECUTIVE ESCALATION", "IMMEDIATE FIX", or "SUBSTANTIAL CREDIT". If the
   situation feels more severe than any single approved code, pick the closest-
   fit approved code (e.g., DEDICATED_SUPPORT for an executive-level intervention)
   and explain the urgency in the Recommendation field, not in the Action code.

2. The structured fields (Customer Summary, Churn Risk, Sentiment, Action,
   Recommendation) MUST always appear in single-customer responses, even when
   you also include a comparison table or before/after analysis. If you write a
   comparison, place the structured fields at the END of the response so the
   frontend can parse them.

RESPONSE FORMAT — pick ONE based on the data you received:

== LIST MODE — when the gathered data contains MULTIPLE customers ==
(Typically from get_high_risk_customers or any "top N at-risk" query.)

You MUST enumerate each customer individually. Do NOT collapse the list into a
generic categorical summary. The manager needs to see WHO to focus on, not just
that high-risk customers exist.

For each customer in the list, output one block in this format:

  - **{customer_id}** — {plan}, {contract_type}
    Churn risk: {probability}% ({HIGH|MEDIUM|LOW})
    Key drivers: {1-2 phrases citing sentiment, anger, qa_score, or escalation signals}
    Recommended action: {ACTION_CODE from the approved list for that risk band}

After the list, end with a single sentence noting any pattern across the cohort
(e.g., "Three of the top five are on 24-month contracts with speed complaints —
consider a coordinated TECH_VISIT campaign.").

== SINGLE-CUSTOMER MODE — when the data is for one customer ==

YOUR RESPONSE MUST INCLUDE:
1. Customer summary (plan, tenure, key risk factors)
2. Churn Risk: HIGH/MEDIUM/LOW with probability
3. Sentiment: if call data available
4. Action: [ACTION_CODE] — one from the approved list above
5. Recommendation: 2-3 sentences justifying why this action fits this specific customer

Consider the customer's plan tier, contract type, complaint history, and sentiment
when choosing between actions. A customer on Basic_25 with speed complaints may benefit
more from SPEED_BOOST than LOYALTY_DISCOUNT. Be specific to their situation."""


# ── State Definition ──────────────────────────────────────────────────

class RetentionState(TypedDict):
    """State that flows through the graph."""
    messages: Annotated[list, add]  # conversation history
    request_type: str  # "customer_query", "high_risk", "transcript", "general"
    customer_id: str | None
    has_transcript: bool


# ── LLM + Tools ──────────────────────────────────────────────────────

tools = [get_customer_details, analyze_call, predict_churn, get_high_risk_customers, get_transcripts]

# Bedrock Guardrail — tuned for retention engine use case
# Allows discussion of customer frustration/churn while blocking hate, PII, etc.
# Uses retention-engine-guardrail (not sentiment-analysis-guardrail which was too strict)
GUARDRAIL_ID = os.getenv("BEDROCK_GUARDRAIL_ID", "nvruz8wx5q83")
GUARDRAIL_VERSION = os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")

llm = ChatBedrock(
    model_id=MODEL_ID,
    region_name=AWS_REGION,
    model_kwargs={"max_tokens": 1024, "temperature": 0},
    guardrails={"guardrailIdentifier": GUARDRAIL_ID, "guardrailVersion": GUARDRAIL_VERSION},
)

# Strategist LLM — no guardrail, since it produces retention recommendations
# that contain terms (cancel, churn, frustrated) the guardrail would block
llm_strategist = ChatBedrock(
    model_id=MODEL_ID,
    region_name=AWS_REGION,
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
    """Data Gathering Agent — calls tools to collect customer data."""
    system = SystemMessage(content=GATHERER_PROMPT)
    response = llm_with_tools.invoke(
        [system] + state["messages"],
        config={"run_name": "DataGatherer"},
    )
    return {"messages": [response], "request_type": state["request_type"],
            "customer_id": state.get("customer_id"), "has_transcript": state.get("has_transcript", False)}


def handle_tool_response(state: RetentionState) -> RetentionState:
    """Data Gathering Agent — reviews tool results, may request more tools."""
    system = SystemMessage(content=GATHERER_PROMPT)
    response = llm_with_tools.invoke(
        [system] + state["messages"],
        config={"run_name": "DataGatherer-ReviewTools"},
    )
    return {"messages": [response], "request_type": state["request_type"],
            "customer_id": state.get("customer_id"), "has_transcript": state.get("has_transcript", False)}


def strategist(state: RetentionState) -> RetentionState:
    """Retention Strategist — evaluates gathered data and recommends action."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[STRATEGIST] Node entered — generating recommendation")
    system = SystemMessage(content=STRATEGIST_PROMPT)
    response = llm_strategist.invoke(
        [system] + state["messages"],
        config={"run_name": "RetentionStrategist"},
    )
    logger.info(f"[STRATEGIST] Response generated: {response.content[:100]}...")
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
    graph.add_node("model", call_model)          # Data Gathering Agent
    graph.add_node("tools", tool_node)
    graph.add_node("respond", handle_tool_response)
    graph.add_node("strategist", strategist)      # Retention Strategist

    # Entry point
    graph.set_entry_point("classify")

    # Classify → Model (always go to data gathering agent)
    graph.add_edge("classify", "model")

    # Model → Tools or Strategist (if no tools needed, go straight to strategist)
    graph.add_conditional_edges("model", should_use_tools, {
        "tools": "tools",
        "end": "strategist",
    })

    # Tools → Respond (gathering agent reviews tool results)
    graph.add_conditional_edges("tools", after_tools, {
        "model": "respond",
        "end": END,
    })

    # Respond → Tools (need more data) or Strategist (data complete)
    graph.add_conditional_edges("respond", should_use_tools, {
        "tools": "tools",
        "end": "strategist",
    })

    # Strategist → End (final recommendation)
    graph.add_edge("strategist", END)

    return graph.compile(checkpointer=MemorySaver())


# ── Singleton ─────────────────────────────────────────────────────────

_graph = None
_graph_version = 3  # bump this to force rebuild after code changes


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
