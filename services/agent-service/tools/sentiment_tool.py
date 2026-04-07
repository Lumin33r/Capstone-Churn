# services/agent-service/tools/sentiment_tool.py
# LangChain Tool that calls Okino's QA Evaluator SageMaker endpoint


import httpx
import os
from langchain.tools import tool

SENTIMENT_URL = os.getenv(key="SENTIMENT_URL", default="http://localhost:8000")


@tool
def analyze_call(transcript: str) -> str:
    """
    Analyzes a customer support call transcript for quality and sentiment.
    Use this tool when given a call transcript to evaluate.
    Returns a sentiment classification along with other fields.

    Args:
        transcript: The full text of the customer support call

    Returns:
        JSON string with qa_score and sentiment fields
    """
    try:
        response = httpx.post(
            url=f"{SENTIMENT_URL}/predict",
            json={"text": transcript},
            timeout=30.0,
        )
        response.raise_for_status()
        return str(object=response.json())
    except httpx.TimeoutException:
        return '{"error": "QA service timeout"}'
    except httpx.HTTPStatusError as e:
        return f'{{"error": "QA service returned {e.response.status_code}"}}'
    except Exception as e:
        return f'{{"error": "{str(object=e)}"}}'