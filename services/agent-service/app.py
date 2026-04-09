# services/agent-service/app.py
# FastAPI entry point for the LangChain agentic harness
# Updated by Kathleen & Okino — passes customer_id to agent

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import re

load_dotenv()

app = FastAPI(title="Retention Engine Agent Service")

# --- Guardrails: approved retention actions by risk level ---
APPROVED_ACTIONS = {
    "HIGH": [
        "PLAN_UPGRADE", "LOYALTY_DISCOUNT", "SERVICE_CREDIT",
        "TECH_VISIT", "DEDICATED_SUPPORT", "CONTRACT_FLEX",
    ],
    "MEDIUM": ["FOLLOWUP_48H", "GOODWILL_CREDIT", "SPEED_BOOST"],
    "LOW": ["MONITOR"],
}


def validate_action(output: str, risk_level: str | None) -> str:
    """Check that the agent's recommended action is in the approved list.
    If not, append a warning and default to the safest action for that risk level."""
    action_match = re.search(pattern=r"Action:\s*(\S+)", string=output)
    if not action_match or not risk_level:
        return output

    action = action_match.group(1)
    allowed = APPROVED_ACTIONS.get(risk_level, [])

    if action not in allowed:
        default = allowed[0] if allowed else "MONITOR"
        output += (
            f"\n\n⚠ GUARDRAIL: Action '{action}' is not approved for {risk_level} risk. "
            f"Overriding to {default}."
        )
        output = output.replace(f"Action: {action}", f"Action: {default}")

    return output

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    customer_id: str | None = None
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    customer_id: str | None = None
    sentiment: str | None = None
    churn_probability: float | None = None
    risk_level: str | None = None
    retention_recommendation: str | None = None


@app.get(path="/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "agent-service"}


@app.post(path="/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    from chains.retention_agent import get_agent
    try:
        agent = get_agent()

        # Include customer_id in the agent input if provided
        agent_input = body.message
        if body.customer_id:
            agent_input = f"Customer ID: {body.customer_id}\n\n{body.message}"

        result = agent.invoke(
            {"input": agent_input},
            config={"configurable": {"session_id": body.session_id}},
        )
        output = result.get("output", "")

        # Parse structured output
        sentiment_match = re.search(pattern=r"Sentiment:\s*(Positive|Neutral|Negative)", string=output)
        churn_match    = re.search(pattern=r"([\d.]+)%", string=output)
        risk_match     = re.search(pattern=r"Churn Risk:\s*(LOW|MEDIUM|HIGH)", string=output)
        rec_match      = re.search(pattern=r"Recommendation:\s*(.+?)(?:\n|$)", string=output)
        cid_match      = re.search(pattern=r"Customer ID:\s*(C\d+)", string=output)

        # Guardrail: validate the recommended action
        risk_level = risk_match.group(1) if risk_match else None
        output = validate_action(output=output, risk_level=risk_level)

        return ChatResponse(
            response=output,
            customer_id=cid_match.group(1) if cid_match else body.customer_id,
            sentiment=sentiment_match.group(1) if sentiment_match else None,
            churn_probability=float(churn_match.group(1)) / 100 if churn_match else None,
            risk_level=risk_match.group(1) if risk_match else None,
            retention_recommendation=rec_match.group(1).strip() if rec_match else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(object=e))
