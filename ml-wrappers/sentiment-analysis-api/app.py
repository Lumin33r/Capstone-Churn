import os
import json
import logging

import boto3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Any
from services.agent_service.tools.bedrock_guardrails import get_guardrail_info

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

SENTIMENT_ENDPOINT_NAME: str = os.getenv(key="SENTIMENT_ENDPOINT_NAME", default="sentiment-analysis-endpoint")
AWS_REGION: str = os.getenv(key="AWS_REGION", default="us-east-1")


sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=AWS_REGION)

with open(file="./model/label_encoder.json", mode="r") as f:
    results = json.load(fp=f)
    
with open(file="./model/example_output.json", mode="r") as f:
    example = json.load(fp=f)
    
with open(file="../../sagemaker/sentiment/sentiment_training.ipynb", mode="r", encoding="utf-8") as f:
    notebook_json = json.load(fp=f)

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

prompt = f"""
AGENT INSTRUCTIONS: TRANSCRIPT SENTIMENT ANALYZER

PERSONA
You are a Senior Customer Experience Analyst specializing in linguistic sentiment analysis. 
Your role is to serve as the initial intelligence layer in the Retention Engine 
pipeline, specifically preparing data for a Churn Analysis Agent. 
You are objective, precise, and highly sensitive to customer frustration markers.

GOAL
Analyze the provided customer service transcript to determine the sentiment, primary category of interaction, and a confidence score. Your analysis is critical because it will be combined with account data by a secondary agent to predict the likelihood of customer churn.

CONSTRAINTS
1. Input Validation: Before processing, you must verify the input length. 
   - The transcript must be between 0 and 20,000 UTF-8 characters.
   - If the transcript is shorter than 0 characters, return an error indicating "Insufficient data for analysis."
   - If the transcript exceeds 20,000 characters, return an error indicating "Transcript exceeds maximum processing limit."
2. Analysis Scope: Do not invent customer details. Only analyze the text provided.
3. Sentiment Scale: Categorize sentiment strictly as "Positive", "Negative", or "Neutral".
4. Category Mapping: Identify the primary reason for the call (e.g., Billing, Technical Support, Cancellation Request, General Inquiry, or Complaint).

CONTEXT:
Additional context providing scripts to be used as tools to create the expect values: {notebook_json}
use at your discretion

USER_INPUT:
{input}

OUTPUT FORMAT
You must output your findings in a strict JSON format to ensure the Churn Analysis 
Agent can parse the data programmatically. Do not include conversational filler or introductory text.

Required JSON Structure:
results: {results}
and 
example values: {example}
"""


def check_prompt_with_guardrail(transcript: str, prompt: str) -> dict[str, Any]:
    """
    Runs Bedrock Guardrails against:
    - the transcript
    - the prompt template
    - the notebook contents (tools)
    - the combined input (prompt + transcript + notebook)
    """
    
    guardrail = get_guardrail_info()

    runtime = boto3.client("bedrock-runtime", region_name="us-east-1")

    def run_guardrail_check(text: str) -> dict[str, Any]:
        payload = {"inputText": text}
        response = runtime.invoke_model(
            modelId="amazon.guardrails",
            guardrailIdentifier=guardrail["guardrail_id"],
            guardrailVersion=guardrail["guardrail_version"],
            body=json.dumps(obj=payload)
        )

        output = json.loads(s=response["body"].read())

        if output.get("action") == "BLOCKED":
            return {
                "blocked": True,
                "reason": output.get("message", "Content blocked by guardrail.")
            }

        return {"blocked": False}

    # Check each component individually
    checks = {
        "transcript": run_guardrail_check(text=transcript),
        "prompt": run_guardrail_check(text=prompt),
        "combined": run_guardrail_check(text=prompt + "\n\n" + transcript + "\n\n")
    }

    # If any check fails, return the first failure
    for key, result in checks.items():
        if result["blocked"]:
            return {
                "blocked": True,
                "source": key,
                "reason": result["reason"]
            }

    return {"blocked": False}


@app.get(path="/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "model": "", "endpoint": SENTIMENT_ENDPOINT_NAME}

@app.post(path="/sentiment", response_model=CallRecord)
def analyze_sentiment(transcript: str, input: str | None = None) -> dict[str, Any] | Any | dict[str, str]:
    """
    Validates constraints and inputs, and invokes the Bedrock Agent for sentiment analysis.
    """
    # UTF-8 Character Count Validation (0 - 20,000)
    char_count = len(transcript.encode(encoding='utf-8'))
    if char_count < 0:
        return {"error": "Insufficient data for analysis.", "char_count": char_count}
    if char_count > 20000:
        return {"error": "Transcript exceeds maximum processing limit.", "char_count": char_count}

    try:
        # Construct payload for the SageMaker LLM
        payload = {
            "inputs": f"{prompt}\n\nTranscript: {transcript}",
            "parameters": {"temperature": 0.1, "max_new_tokens": 512}
        }

        guardrail = check_prompt_with_guardrail(transcript=transcript, prompt=prompt)
        
        if guardrail["blocked"]:
            return {
                "error": guardrail["reason"],
                "blocked": True,
                "source": guardrail["source"]
        }

        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=SENTIMENT_ENDPOINT_NAME,
            ContentType="application/json",
            Body=json.dumps(obj=payload)
        )

        result = json.loads(s=response["Body"].read().decode())
        return result

    except Exception as e:
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
    
