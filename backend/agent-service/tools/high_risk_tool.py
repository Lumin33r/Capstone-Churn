# services/agent-service/tools/high_risk_tool.py
# LangChain Tool that fetches high-risk customers from the churn predictor

import httpx
import os
from langchain.tools import tool

CHURN_URL = os.getenv(key="CHURN_PREDICTOR_URL", default="http://localhost:8001")


@tool
def get_high_risk_customers(limit: int = 10) -> str:
    """
    Returns a list of the highest-risk customers who are most likely to churn.
    Use this when asked about high-risk customers, who to call, or the churn leaderboard.

    Args:
        limit: Number of customers to return, default 10

    Returns:
        JSON list of high-risk customers with churn probability, plan, and sentiment
    """
    try:
        response = httpx.get(
            url=f"{CHURN_URL}/high-risk",
            params={"limit": limit, "min_risk": 0.5},
            timeout=60.0,
        )
        response.raise_for_status()
        return str(object=response.json())
    except httpx.TimeoutException:
        return '{"error": "High-risk query timed out"}'
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'
