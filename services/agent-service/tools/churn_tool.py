# services/agent-service/tools/churn_tool.py
# LangChain Tool that calls Kathleen's Churn Predictor API
# Updated to match Kathleen's PredictRequest schema
# George (gvill0576) — Capstone-Churn

import httpx
import os
from langchain.tools import tool

CHURN_URL = os.getenv("CHURN_PREDICTOR_URL", "http://localhost:8001")


@tool
def predict_churn(
    customer_id: str,
    qa_score: float,
    sentiment: str = "Neutral",
    frustration_level: float = 5.0,
) -> str:
    """
    Predicts the probability that a customer will cancel their service.
    Use this tool after analyzing a call transcript to determine churn risk.
    Requires the customer_id to look up account data internally.
    Returns churn_probability, prediction, and risk_level.

    Args:
        customer_id: The unique customer identifier for account lookup
        qa_score: Quality score from the sentiment analysis, between 0 and 10
        sentiment: Sentiment from the call analysis, one of Positive, Negative, Neutral
        frustration_level: Frustration level detected in the call, between 0 and 10

    Returns:
        JSON string with churn_probability, prediction, risk_level, and customer_id
    """
    try:
        response = httpx.post(
            f"{CHURN_URL}/predict",
            json={
                "customer_id": customer_id,
                "qa_score": qa_score,
                "sentiment": sentiment,
                "frustration_level": frustration_level,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return str(response.json())
    except httpx.TimeoutException:
        return '{"error": "Churn service timeout", "churn_probability": 0.5, "risk_level": "MEDIUM"}'
    except httpx.HTTPStatusError as e:
        return f'{{"error": "Churn service returned {e.response.status_code}", "churn_probability": 0.5, "risk_level": "MEDIUM"}}'
    except Exception as e:
        return f'{{"error": "{str(e)}", "churn_probability": 0.5, "risk_level": "MEDIUM"}}'

