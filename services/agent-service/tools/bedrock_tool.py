
import os
import httpx
import boto3
from langchain.tools import tool
from dotenv import load_dotenv
from typing import Any


load_dotenv()


GUARDRAIL_NAME = os.getenv(key="GUARDRAIL_NAME", default="sentiment-analysis-guardrail")
BEDROCK_URL = os.getenv(key="BEDROCK_URL", default="http://localhost:8001")
AWS_REGION = os.getenv(key="AWS_REGION", default="us-east-1")


# Guardrail Logic
def get_guardrail_info() -> dict[str, Any]:
    bedrock = boto3.client("bedrock", region_name=AWS_REGION)
    response = bedrock.list_guardrails()


    for item in response.get("guardrails", []):
        if item.get("name") == GUARDRAIL_NAME:
            return {
                "guardrail_id": item["id"],
                "guardrail_version": item["version"],
                "status": item["status"],
                "description": item["description"],
            }

    raise ValueError(f"Guardrail '{GUARDRAIL_NAME}' not found.")


@tool
def bedrock_chat(prompt: str) -> str:
    """
    Sends a general chat request to a Bedrock model with guardrails applied.
    Use this tool for open-ended conversation, rewriting, summarization,
    or general reasoning tasks.
    """
    guardrail_info = get_guardrail_info()

    payload = {
        "input": prompt,
        "guardrail_id": guardrail_info.guardrail_id,
        "guardrail_version": guardrail_info.guardrail_version,
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
