import os
import json
import logging
import time
import random
import pandas as pd
from typing import Any


import boto3
import botocore
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from io import StringIO


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
GUARDRAIL_NAME = os.getenv(key="GUARDRAIL_NAME", default="sentiment-analysis-guardrail")
S3_BUCKET = os.getenv(key="S3_BUCKET", default="retention-engine-bucket")
AWS_REGION = os.getenv(key="AWS_REGION", default="us-east-1")

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=AWS_REGION)

FEATURE_COLUMNS = [
    "call_id",
    "customer_id",
    "call_date",
    "call_time",
    "agent_id",
    "agent_name",
    "primary_scenario",
    "call_transcript",
    "overall_rating",
    "call_successful",
    "customer_monthly_spend",
    "customer_service_count",
    "customer_issue_history",
]

_customer_data: pd.DataFrame | None = None

def download_csv_from_s3() -> pd.DataFrame:
    """Download a CSV file from S3 with full error handling and validation."""
    global _customer_data
    s3 = boto3.client("s3")
    KEY = "data/call_transcripts.csv"

    # Download file 
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=KEY)
        csv_str = obj["Body"].read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"Failed to download file from S3: {e}")

    # Parse CSV into DataFrame 
    try:
        _customer_data = pd.read_csv(filepath_or_buffer=StringIO(initial_value=csv_str))
    except Exception as e:
        raise ValueError(f"Failed to parse CSV into DataFrame: {e}")

    return _customer_data


def find_record(df: pd.DataFrame | None, call_id: str | None = None, customer_id: str | None = None) -> pd.DataFrame:
    """Unified search method."""
    if df is None:
        df = download_csv_from_s3()
        
    if "call_id" not in df.columns:
        raise ValueError("CSV missing 'call_id' column")
    
    if "customer_id" not in df.columns:
        raise ValueError("CSV missing 'customer_id' column")
    
    if call_id:
        return df[df["call_id"] == call_id]
    
    if customer_id:
        return df[df["customer_id"] == customer_id]
    
    raise ValueError("Provide either call_id or customer_id")


# File Loaders
def load_model_files() -> dict[str, Any]:
    """Load model metadata files dynamically at request time."""
    with open(file=os.path.join(os.path.dirname(__file__), "model/label_encoder.json"), mode="r") as f:
        RESULTS = json.load(fp=f)

    with open(file=os.path.join(os.path.dirname(__file__), "model/example_output.json"), mode="r") as f:
        EXAMPLE = json.load(fp=f)

    return {"results": RESULTS, "example": EXAMPLE}


def load_notebook() -> Any:
    """Load notebook content dynamically."""
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
Analyze the provided customer service transcript provided by the user input to determine the sentiment,
primary category, a confidence score, and other data fields based on the output format. 

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
) -> Any:
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
    chunks = chunk_text(text=combined_text)

   
    # Evaluate each chunk
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

            def call() -> Any:
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


def encode_features(raw: dict, label_encoders: dict) -> str:
    """Encode a raw feature dict to a CSV string for SageMaker."""
    LABEL_ENCODERS = label_encoders
    for col, mapping in LABEL_ENCODERS.items():
        raw[col] = mapping.get(str(raw.get(col, "")), 0)

    return ",".join(str(float(raw.get(col, 0))) for col in FEATURE_COLUMNS)

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

def extract_customer_fields(customer: pd.Series) -> dict:
    """Extract only the fields required for feature building."""
    return {
        "call_id": customer["call_id"],
        "customer_id": customer["customer_id"],
        "call_date": customer["call_date"],
        "call_time": customer["call_time"],
        "agent_id": customer["agent_id"],
        "agent_name": customer["agent_name"],
        "primary_scenario": customer["primary_scenario"],
        "call_transcript": customer["call_transcript"],
        "overall_rating": int(customer["overall_rating"]),
        "call_successful": int(customer["call_successful"]),
        "customer_monthly_spend": float(customer["customer_monthly_spend"]),
        "customer_service_count": int(customer["customer_service_count"]),
        "customer_issue_history": customer["customer_issue_history"]
    }

# Data Models
class CallRecord(BaseModel):
    call_id: str
    customer_id: str
    call_date: str
    call_time: str
    agent_id: str
    agent_name: str
    primary_scenario: str
    call_transcript: str
    overall_rating: int
    call_successful: int
    customer_monthly_spend: float
    customer_service_count: int
    customer_issue_history: str
    
class CallResponse(BaseModel):
    customer_id: str
    qa_score: float 
    sentiment: str 
    emotion_frustration: float 
    emotion_anger: float 
    sentiment_shift: float 
    escalation_flag: int 
    resolution_flag: int 


# API Endpoints
@app.get(path="/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "endpoint": SENTIMENT_ENDPOINT_NAME}


@app.post(path="/sentiment", response_model=CallResponse)
def analyze_sentiment(req: CallRecord, input: str | None = None) -> dict[str, Any] | dict[str, Any] | dict[str, str]:

    customer_data = download_csv_from_s3()
    
    if req.customer_id not in customer_data.index:
        raise HTTPException(status_code=404, detail=f"Customer {req.customer_id} not found")
    
    customer = customer_data.req.customer_id 
    # Validate transcript length
    char_count = len(customer.call_transcript.encode(encoding="utf-8"))
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
        input = input or ""
    )

    # Guardrail check
    guardrail = run_guardrails(prompt=prompt, transcript=customer.transcript)
    if guardrail["blocked"]:
        return {
            "error": guardrail["reason"],
            "blocked": True,
            "source": guardrail["source"]
        }

    # Invoke Sagemaker
    try:
        return invoke_sagemaker(prompt=prompt, transcript=customer.transcript)
    except Exception as e:
        logger.exception(msg="Sagemaker invocation failed")
        return {"error": str(object=e), "status": "failure"}
