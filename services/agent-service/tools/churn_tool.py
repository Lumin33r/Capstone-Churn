# services/agent-service/tools/churn_tool.py
# LangChain Tool that calls Kathleen's Churn Predictor endpoint
# Updated by Kathleen — matches new /predict contract

import httpx
import os
from langchain.tools import tool

CHURN_URL = os.getenv("CHURN_PREDICTOR_URL", "http://localhost:8001")


@tool
def predict_churn(
    customer_id: str,
    qa_score: float = 5.0,
    sentiment: str = "Neutral",
    emotion_frustration: float = 0.0,
    emotion_anger: float = 0.0,
    sentiment_shift: float = 0.0,
    escalation_flag: int = 0,
    resolution_flag: int = 1,
) -> str:
    """
    Predicts the probability that a customer will cancel their service.
    Use this tool after analyzing a call to determine churn risk.
    The tool looks up account data internally by customer_id.

    Args:
        customer_id: The customer ID (e.g., C00077940)
        qa_score: Quality score from the call analysis, between 1 and 10
        sentiment: Sentiment from call analysis: Positive, Neutral, or Negative
        emotion_frustration: Frustration score from 0 to 1
        emotion_anger: Anger score from 0 to 1
        sentiment_shift: How sentiment changed during the call, -1 to 1
        escalation_flag: Whether the call was escalated, 0 or 1
        resolution_flag: Whether the issue was resolved, 0 or 1

    Returns:
        JSON string with churn_probability, prediction, and risk_level
    """
    try:
        response = httpx.post(
            f"{CHURN_URL}/predict",
            json={
                "customer_id": customer_id,
                "qa_score": qa_score,
                "sentiment": sentiment,
                "emotion_frustration": emotion_frustration,
                "emotion_anger": emotion_anger,
                "sentiment_shift": sentiment_shift,
                "escalation_flag": escalation_flag,
                "resolution_flag": resolution_flag,
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
