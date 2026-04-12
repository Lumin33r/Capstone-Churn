import os
import json
import logging
import time
import random
from typing import Any

import boto3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from botocore.exceptions import ClientError


# Initialization
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name=__name__)

app = FastAPI(title="Sentiment Analysis API")

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SENTIMENT_ENDPOINT_NAME = os.getenv(key="SENTIMENT_ENDPOINT_NAME", default="sentiment-analysis-endpoint")
AWS_REGION = os.getenv(key="AWS_REGION", default="us-east-1")
GUARDRAIL_NAME = os.getenv(key="GUARDRAIL_NAME", default="sentiment-analysis-guardrail")

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=AWS_REGION)


# File Loaders
def load_model_files() -> dict[str, Any]:
    """Load model metadata files dynamically at request time."""
    with open(file=os.path.join(os.path.dirname(__file__), "model/label_encoder.json"), mode="r") as f:
        results = json.load(fp=f)

    with open(file=os.path.join(os.path.dirname(__file__), "model/example_output.json"), mode="r") as f:
        example = json.load(fp=f)

    return {"results": results, "example": example}


def load_notebook() -> Any:
    """
        Load notebook content dynamically.
    """
    notebook_path = os.path.abspath(
        path=os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "sagemaker",
            "sentiment",
            "sentiment_training.ipynb",
        )
    )

    with open(file=notebook_path, mode="r", encoding="utf-8") as f:
        return json.load(fp=f)


# Prompt Builder
def build_prompt(results: dict, example: dict, notebook: dict, user_input: str) -> str:
    return f"""
AGENT INSTRUCTIONS: TRANSCRIPT SENTIMENT ANALYZER

PERSONA
You are a Senior Customer Experience Analyst specializing in linguistic sentiment analysis. 
Your role is to serve as the initial intelligence layer in the Retention Engine pipeline.

GOAL
Analyze the provided customer service transcript to determine the sentiment, primary category, 
and a confidence score.

CONSTRAINTS
1. Transcript must be 0–20,000 UTF-8 characters.
2. Do not invent customer details.
3. Sentiment must be Positive, Negative, or Neutral.
4. Identify the primary call category.

CONTEXT:
Notebook tools:
{json.dumps(obj=notebook)}

USER_INPUT:
{user_input}

OUTPUT FORMAT:
results: {json.dumps(obj=results)}
example: {json.dumps(obj=example)}
"""


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

def invoke_with_retries(
    func,
    max_retries: int = 10,
    base_delay: float = 0.2,
    max_delay: float = 8.0,
    retryable_errors: tuple = ("ThrottlingException", "TooManyRequestsException")
):
    """
    Generic retry wrapper with exponential backoff + jitter.
    Works for Bedrock, Guardrails, SageMaker, DynamoDB, etc.
    """

    for attempt in range(max_retries):
        try:
            return func()

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            # Only retry throttling‑type errors
            if error_code not in retryable_errors:
                raise

            # Exponential backoff with full jitter
            sleep_time = min(max_delay, base_delay * (2 ** attempt))
            sleep_time = random.uniform(0, sleep_time)

            # Optional: log throttling event
            print(f"[Retry {attempt+1}/{max_retries}] Throttled ({error_code}). "
                  f"Sleeping {sleep_time:.2f}s")

            time.sleep(sleep_time)

    raise RuntimeError("Exceeded max retries due to throttling")

def chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

def run_guardrails(prompt: str, transcript: str) -> dict[str, Any]:
    guardrail = get_guardrail_info()
    runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    # Combine everything into ONE guardrail call
    combined_text = f"PROMPT:\n{prompt}\n\nTRANSCRIPT:\n{transcript}"

    # Chunk if needed to avoid text‑unit throttling
    chunks = chunk_text(combined_text)

    # -----------------------------
    # Evaluate each chunk
    # -----------------------------
    for idx, chunk in enumerate(chunks):
        def check(text: str) -> dict[str, Any] | dict[str, bool]:
            payload = {
                # "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": text}]
                    }
                ],
                "inferenceConfig": {
                    "max_new_tokens": 200,
                    "temperature": 0.1
                }
            }

            def call():
                return runtime.invoke_model(
                    modelId="amazon.nova-micro-v1:0",
                    guardrailIdentifier=guardrail["guardrail_id"],
                    guardrailVersion=guardrail["guardrail_version"],
                    body=json.dumps(obj=payload)
                )
        
            response = invoke_with_retries(func=call)
            output = json.loads(s=response["body"].read())
            if output.get("amazon-bedrock-guardrailAction") == "INTERVENED":
                return {"blocked": True, "reason": "Guardrail intervention triggered.", "trace": output.get("amazon-bedrock-guardrailTrace")}
            
            time.sleep(0.05)

            return {"blocked": False}

    return {"blocked": False}



# Sagemaker Invocation
def invoke_sagemaker(prompt: str, transcript: str) -> dict[str, Any]:
    payload = {
        "inputs": f"{prompt}\n\nTranscript:\n{transcript}",
        "parameters": {"temperature": 0.1, "max_new_tokens": 512}
    }

    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SENTIMENT_ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(obj=payload)
    )

    return json.loads(s=response["Body"].read().decode())

# Data Models
class EmotionScores(BaseModel):
    anger: float = 0.71
    sadness: float = 0.33
    frustration: float = 0.82
    fear: float = 0.12
    disgust: float = 0.18
    joy: float = 0.05
    surprise: float = 0.09
    confusion: float = 0.41
    neutral: float = 0.22


class CallRecord(BaseModel):
    call_id: str = "CALL_000001"
    customer_id: str = "C00008949"
    primary_scenario: str = "contract_renewal"
    qa_score: float = 3.2
    sentiment: str = "Negative"
    category: str = "payment_assistance"
    confidence: float = 0.91
    frustration_level: int = 8
    call_duration_indicator: str = "long"
    escalation_flag: bool = True
    customer_age: int = 16
    income_bracket: str = "low"
    plan_type: str = "Limited_10GB"
    recent_overages_count: int = 6
    customer_service_count: int = 1
    customer_issue_history: int = 6
    call_duration_seconds: int = 585
    num_turns: int = 32
    customer_talk_ratio: float = 0.58
    agent_talk_ratio: float = 0.42
    interruptions_count: int = 3
    sentiment_shift: float = -0.42
    word_count: int = 1240
    avg_word_length: float = 4.7
    num_negative_words: int = 18
    num_positive_words: int = 4
    num_exclamation_marks: int = 3
    toxicity_score: float = 0.12
    emotion_scores: EmotionScores = EmotionScores()
    billing_dispute_flag: bool = False
    outage_history_flag: bool = False
    overage_amount_last_cycle: int = 20
    agent_experience: float = 0.6
    transfer_count: int = 0
    resolution_flag: bool = False


# API Endpoints
@app.get(path="/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "endpoint": SENTIMENT_ENDPOINT_NAME}


@app.post(path="/sentiment", response_model=CallRecord)
def analyze_sentiment(transcript: str, input: str | None = None) -> dict[str, Any] | dict[str, Any] | dict[str, str]:

    # Validate transcript length
    char_count = len(transcript.encode(encoding="utf-8"))
    if char_count < 0:
        return {"error": "Insufficient data for analysis.", "char_count": char_count}
    if char_count > 20000:
        return {"error": "Transcript exceeds maximum processing limit.", "char_count": char_count}

    # Load dynamic files
    files = load_model_files()
    notebook = load_notebook()

    # Build prompt
    prompt = build_prompt(
        results=files["results"],
        example=files["example"],
        notebook=notebook,
        user_input=input or ""
    )

    # Guardrail check
    guardrail = run_guardrails(prompt=prompt, transcript=transcript)
    if guardrail["blocked"]:
        return {
            "error": guardrail["reason"],
            "blocked": True,
            "source": guardrail["source"]
        }

    # Invoke Sagemaker
    try:
        return invoke_sagemaker(prompt=prompt, transcript=transcript)
    except Exception as e:
        logger.exception(msg="Sagemaker invocation failed")
        return {"error": str(object=e), "status": "failure"}

if __name__ == "__main__":
    # Example Usage
    sample_transcript = """
    Customer: I am extremely frustrated with my billing statement this month. 
    I was promised a discount that isn't showing up, and if this isn't fixed, 
    I'm going to look for another provider by the end of the week.
    Agent: I'm very sorry to hear that, let me look into your account immediately.
    """
    
    result = analyze_sentiment(transcript=sample_transcript)
    print(json.dumps(obj=result, indent=2))