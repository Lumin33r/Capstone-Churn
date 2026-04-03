# services/agent-service/chains/retention_agent.py
# The main LangChain agent that orchestrates the full retention analysis
# George (gvill0576) — Capstone-Churn

from langchain_aws import ChatBedrock
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from tools.qa_tool import analyze_call
from tools.churn_tool import predict_churn
from dotenv import load_dotenv
import os

load_dotenv()

MODEL_ID: str = os.getenv(key="MODEL_ID", default="us.anthropic.claude-haiku-4-5-20251001-v1:0")
AWS_REGION: str = os.getenv(key="AWS_REGION", default="us-east-1")

SYSTEM_PROMPT = """You are the Retention Engine AI for a customer support team.
Your job is to analyze customer support calls and identify at-risk customers.

When given a call transcript or customer inquiry:
1. Always use the analyze_call tool first to get the QA score and sentiment
2. Then use the predict_churn tool with the QA score to get churn probability
3. If churn_probability is above 0.70, the customer is HIGH RISK
   - Generate a specific retention offer based on the call context
   - Be specific: offer a discount, upgrade, or dedicated support line
4. If churn_probability is between 0.40 and 0.70, the customer is MEDIUM RISK
   - Recommend a follow-up call and note the specific concerns raised
5. If churn_probability is below 0.40, the customer is LOW RISK
   - Note any positive feedback for the agent's performance review

Always end your response in exactly this format:
QA Score: X/10
Sentiment: [sentiment from analyze_call]
Churn Risk: [LOW/MEDIUM/HIGH] ([probability as percentage]%)
Recommendation: [specific action for this customer]
"""


def create_retention_agent() -> AgentExecutor:
    """Creates and returns the configured LangChain agent executor."""
    llm = ChatBedrock(
        model=MODEL_ID,
        region=AWS_REGION,
        model_kwargs={"max_tokens": 1024, "temperature": 0},
    )

    tools = [analyze_call, predict_churn]

    prompt = ChatPromptTemplate.from_messages(messages=[
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True,
    )


# Singleton pattern — create once, reuse across requests
_agent_executor: AgentExecutor | None = None

def get_agent() -> AgentExecutor:
    """Returns the shared agent instance, creating it on first call."""
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = create_retention_agent()
    return _agent_executor