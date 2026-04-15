# services/agent-service/tools/sentiment_tool.py
# LangChain Tool that calls the Sentiment Analysis API

import httpx
import os
from langchain.tools import tool

SENTIMENT_URL = os.getenv("SENTIMENT_URL", "http://localhost:8002")


@tool
def analyze_call(transcript: str) -> str:
    """
    Analyzes a customer support call transcript for sentiment, emotions, and quality.
    Use this tool when given a call transcript to evaluate.
    Returns qa_score, sentiment, emotion scores, escalation/resolution flags.

    Args:
        transcript: The full text of the customer support call

    Returns:
        JSON string with qa_score, sentiment, emotion_frustration, emotion_anger,
        sentiment_shift, escalation_flag, resolution_flag
    """
    try:
        response = httpx.post(
            url=f"{SENTIMENT_URL}/predict",
            json={"transcript": transcript},
            timeout=30.0,
        )
        response.raise_for_status()
        return str(response.json())
    except httpx.TimeoutException:
        return '{"error": "Sentiment service timeout", "qa_score": 5, "sentiment": "unknown"}'
    except httpx.HTTPStatusError as e:
        return f'{{"error": "Sentiment service returned {e.response.status_code}", "qa_score": 5, "sentiment": "unknown"}}'
    except Exception as e:
        return f'{{"error": "{str(e)}", "qa_score": 5, "sentiment": "unknown"}}'
