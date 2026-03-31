# services/agent-service/app.py
# FastAPI entry point for the LangChain agentic harness
# George (gvill0576) — Capstone-Churn

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os, re

load_dotenv()

app = FastAPI(title="Retention Engine Agent Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    customer_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    qa_score: float | None = None
    churn_probability: float | None = None
    risk_level: str | None = None
    retention_recommendation: str | None = None


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agent-service"}


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    from chains.retention_agent import get_agent
    try:
        agent = get_agent()
        result = agent.invoke({"input": body.message})
        output = result.get("output", "")

        qa_match    = re.search(r"QA Score:\s*([\d.]+)", output)
        churn_match = re.search(r"([\d.]+)%", output)
        risk_match  = re.search(r"Churn Risk:\s*(LOW|MEDIUM|HIGH)", output)
        rec_match   = re.search(r"Recommendation:\s*(.+?)(?:\n|$)", output)

        return ChatResponse(
            response=output,
            qa_score=float(qa_match.group(1)) if qa_match else None,
            churn_probability=float(churn_match.group(1)) / 100 if churn_match else None,
            risk_level=risk_match.group(1) if risk_match else None,
            retention_recommendation=rec_match.group(1).strip() if rec_match else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))