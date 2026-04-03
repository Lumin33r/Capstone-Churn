# services/agent-service/tools/churn_tool.py
# LangChain Tool that calls Kathleen's Churn Predictor SageMaker endpoint
# George (gvill0576) — Capstone-Churn

import httpx
import os
from langchain.tools import tool

CHURN_URL = os.getenv(key="CHURN_PREDICTOR_URL", default="http://localhost:8001")


@tool
def predict_churn(
    qa_score: float,
    contract_length: int = 12,
    monthly_bill: float = 65.0,
    support_calls: int = 2,
) -> str:
    """
    Predicts the probability that a customer will cancel their service.
    Use this tool after analyzing a call to determine churn risk.
    Returns churn probability between 0 and 1 and a risk level.

    Args:
        qa_score: Quality score from the call analysis, between 0 and 10
        contract_length: Customer contract length in months, default 12
        monthly_bill: Customer monthly bill amount in USD, default 65.0
        support_calls: Number of support calls in the last 30 days, default 2

    Returns:
        JSON string with churn_probability and risk_level fields
    """
    try:
        response = httpx.post(
            url=f"{CHURN_URL}/predict",
            json={
                "qa_score": qa_score,
                "contract_length": contract_length,
                "monthly_bill": monthly_bill,
                "support_calls": support_calls,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return str(object=response.json())
    except httpx.TimeoutException:
        return '{"error": "Churn service timeout", "churn_probability": 0.5, "risk_level": "MEDIUM"}'
    except httpx.HTTPStatusError as e:
        return f'{{"error": "Churn service returned {e.response.status_code}", "churn_probability": 0.5, "risk_level": "MEDIUM"}}'
    except Exception as e:
        return f'{{"error": "{str(object=e)}", "churn_probability": 0.5, "risk_level": "MEDIUM"}}'