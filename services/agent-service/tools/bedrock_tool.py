
import os
import httpx
from langchain.tools import tool
from bedrock_guardrail import get_guardrail_info

BEDROCK_URL = os.getenv(key="BEDROCK_URL", default="http://localhost:8001")

@tool
def bedrock_chat(prompt: str) -> str:
    """
    Sends a general chat request to a Bedrock model with guardrails applied.
    Use this tool for open-ended conversation, rewriting, summarization,
    or general reasoning tasks.
    """
    guardrail_id, guardrail_version = get_guardrail_info()

    payload = {
        "input": prompt,
        "guardrail_id": guardrail_id,
        "guardrail_version": guardrail_version,
    }

    try:
        response = httpx.post(
            url=f"{BEDROCK_URL}/chat",
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return str(object=response.json())

    except httpx.TimeoutException:
        return '{"error": "Bedrock chat service timeout"}'

    except httpx.HTTPStatusError as e:
        return f'{{"error": "Bedrock chat returned {e.response.status_code}"}}'

    except Exception as e:
        return f'{{"error": "{str(object=e)}"}}'
