# services/agent-service/tools/transcript_tool.py
# LangChain Tool that retrieves transcripts from S3 via the churn predictor API

import httpx
import os
from langchain_core.tools import tool

CHURN_URL = os.getenv("CHURN_PREDICTOR_URL", "http://localhost:8001")


@tool
def get_transcripts(customer_id: str) -> str:
    """
    Retrieves call transcripts for a specific customer.
    Use this tool when asked about a customer's call history or transcripts.

    Args:
        customer_id: The customer ID

    Returns:
        JSON list of transcripts with text and speaker segments
    """
    try:
        # List transcripts for this customer
        response = httpx.get(
            f"{CHURN_URL}/transcripts",
            params={"customer_id": customer_id},
            timeout=30.0,
        )
        response.raise_for_status()
        transcript_list = response.json()

        if not transcript_list:
            return f'{{"message": "No transcripts found for customer {customer_id}"}}'

        # Fetch the full text of each transcript
        results = []
        for t in transcript_list[:5]:  # limit to 5 most recent
            detail_resp = httpx.get(
                f"{CHURN_URL}/transcripts/{t['name']}",
                timeout=30.0,
            )
            if detail_resp.status_code == 200:
                detail = detail_resp.json()
                results.append({
                    "name": t["name"],
                    "customer_id": t.get("customer_id"),
                    "date": t.get("last_modified", ""),
                    "transcript": detail.get("transcript", ""),
                    "segments": detail.get("segments", []),
                })

        import json
        return json.dumps(results, indent=2)

    except httpx.HTTPStatusError as e:
        return f'{{"error": "Transcript service returned {e.response.status_code}"}}'
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'
