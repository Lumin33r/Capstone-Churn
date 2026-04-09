import boto3
import os
from typing import Any
from dotenv import load_dotenv

load_dotenv()

AWS_REGION: str = os.getenv(key="AWS_REGION", default="us-east-1")
GUARDRAIL_NAME: str = os.getenv(key="GUARDRAIL_NAME", default="sentiment-analysis-guardrail")

def get_guardrail_info() -> dict[str, Any]:
    """
    Retrieve the guardrail_id and guardrail_version for a given Bedrock Guardrail name.
    """

    bedrock = boto3.client("bedrock", region_name=AWS_REGION)

    response = bedrock.list_guardrails()

    for item in response.get("guardrails", []):
        if item.get("name") == GUARDRAIL_NAME:
            return {
                "guardrail_id": item.get("id"),
                "guardrail_version": item.get("version"),
                "status": item.get("status"),
                "description": item.get("description"),
            }

    raise ValueError(f"Guardrail '{GUARDRAIL_NAME}' not found in region {AWS_REGION}.")

