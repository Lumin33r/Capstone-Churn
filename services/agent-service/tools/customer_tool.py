# services/agent-service/tools/customer_tool.py
# LangChain Tool that fetches customer account details

import httpx
import os
from langchain.tools import tool

CHURN_URL = os.getenv(key="CHURN_PREDICTOR_URL", default="http://localhost:8001")


@tool
def get_customer_details(customer_id: str) -> str:
    """
    Looks up account details for a customer including their plan, tenure,
    complaints, and call sentiment data if available.
    Use this when asked about a specific customer's account or history.

    Args:
        customer_id: The customer ID

    Returns:
        JSON with account details, plan info, complaints, and call data
    """
    try:
        response = httpx.get(
            url=f"{CHURN_URL}/customer-details/{customer_id}",
            timeout=10.0,
        )
        response.raise_for_status()
        return str(object=response.json())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f'{{"error": "Customer {customer_id} not found"}}'
        return f'{{"error": "Service returned {e.response.status_code}"}}'
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'
